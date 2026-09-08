#!/usr/bin/env python3
import os, shutil, subprocess

BASE = os.path.expanduser("~/Projects/JARVIS-SuperServer")

# Удаляем старую папку, чтобы не было мусора
if os.path.exists(BASE):
    shutil.rmtree(BASE)
os.makedirs(os.path.join(BASE, "Sources", "JarvisServer"))
os.makedirs(os.path.join(BASE, "Resources"))

files = {
    "Package.swift": '''// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "JarvisServer",
    platforms: [.macOS(.v12)],
    products: [
        .executable(name: "JarvisServer", targets: ["JarvisServer"])
    ],
    targets: [
        .executableTarget(
            name: "JarvisServer",
            path: "Sources/JarvisServer",
            resources: [.copy("Resources")]
        )
    ]
)
''',

    "Sources/JarvisServer/Config.swift": '''import Foundation

final class Config {
    static let shared = Config()

    var apiKey = ""
    var proxy = ""
    var model = "gpt-4o"
    var externalPath = ""
    var sendpulseToken = ""
    var rusenderToken = ""
    var midiDevice = ""

    private var containerPath: String {
        return "\(NSHomeDirectory())/.jarvis"
    }

    var logDir: String {
        let p = "\(containerPath)/logs"
        try? FileManager.default.createDirectory(atPath: p, withIntermediateDirectories: true)
        return p
    }

    var logFile: String { "\(logDir)/jarvis.log" }
    var brainFile: String { "\(containerPath)/brain.json" }

    func load() {
        let path = "\(containerPath)/config.json"
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return }
        guard let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        apiKey = dict["apiKey"] as? String ?? ""
        proxy = dict["proxy"] as? String ?? ""
        model = dict["model"] as? String ?? "gpt-4o"
        externalPath = dict["externalPath"] as? String ?? ""
        sendpulseToken = dict["sendpulseToken"] as? String ?? ""
        rusenderToken = dict["rusenderToken"] as? String ?? ""
        midiDevice = dict["midiDevice"] as? String ?? ""
    }

    func save() {
        let dict: [String: Any] = [
            "apiKey": apiKey, "proxy": proxy, "model": model,
            "externalPath": externalPath, "sendpulseToken": sendpulseToken,
            "rusenderToken": rusenderToken, "midiDevice": midiDevice
        ]
        let path = "\(containerPath)/config.json"
        guard let data = try? JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted) else { return }
        try? data.write(to: URL(fileURLWithPath: path))
    }

    func brainLoad() -> [String: String] {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: brainFile)) else { return [:] }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: String]) ?? [:]
    }

    func brainSave(_ data: [String: String]) {
        guard let json = try? JSONSerialization.data(withJSONObject: data, options: .prettyPrinted) else { return }
        try? json.write(to: URL(fileURLWithPath: brainFile))
    }
}
''',

    "Sources/JarvisServer/Logger.swift": '''import Foundation

final class Logger {
    static let shared = Logger()
    private let queue = DispatchQueue(label: "jarvis.logger", qos: .utility)
    private let formatter = ISO8601DateFormatter()

    private init() { _ = Config.shared.logDir }

    func write(_ message: String) {
        let line = "[\(formatter.string(from: Date()))] \(message)\n"
        queue.async {
            do {
                try line.write(toFile: Config.shared.logFile, atomically: true, encoding: .utf8)
            } catch {
                print("Logger write error: \(error.localizedDescription)")
            }
        }
    }
}
''',

    "Sources/JarvisServer/SysMonitor.swift": '''import Foundation

final class SysMonitor {
    static func info() -> [String: Any] {
        let pi = ProcessInfo.processInfo
        let uptime = pi.systemUptime
        let days = Int(uptime) / 86400
        let hours = (Int(uptime) % 86400) / 3600
        let minutes = (Int(uptime) % 3600) / 60
        return [
            "hostname": Host.current().localizedName ?? "Mac",
            "platform": "macOS",
            "cpuCores": pi.processorCount,
            "memTotal": pi.physicalMemory,
            "uptime": "\(days)d \(hours)h \(minutes)m"
        ]
    }
}
''',

    "Sources/JarvisServer/WebServer.swift": '''import Foundation
import Network

final class WebServer {
    static let shared = WebServer()
    private var listener: NWListener?

    func start(port: UInt16 = 3000) {
        do {
            listener = try NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: port)!)
            listener?.newConnectionHandler = { [weak self] conn in
                self?.handle(conn: conn)
            }
            listener?.start(queue: .global(qos: .userInitiated))
            Logger.shared.write("WebServer started on port \(port)")
        } catch {
            Logger.shared.write("WebServer error: \(error.localizedDescription)")
        }
    }

    private func handle(conn: NWConnection) {
        conn.start(queue: .global())
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, _, _ in
            guard let data = data, let req = String(data: data, encoding: .utf8) else {
                conn.cancel()
                return
            }
            let parts = req.components(separatedBy: " ")
            let path = parts.count > 1 ? parts[1] : "/"
            let body = self?.route(path: path) ?? "Not Found"
            let http = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: \(body.utf8.count)\r\n\r\n\(body)"
            conn.send(content: http.data(using: .utf8), completion: .contentProcessed { _ in conn.cancel() })
        }
    }

    private func route(path: String) -> String {
        switch path {
        case "/":
            if let p = Bundle.module.path(forResource: "index", ofType: "html"),
               let s = try? String(contentsOfFile: p) { return s }
            return "<h1>JARVIS SuperServer</h1>"
        case "/api/status":
            let info = SysMonitor.info()
            if let d = try? JSONSerialization.data(withJSONObject: info),
               let s = String(data: d, encoding: .utf8) { return s }
            return "{}"
        default:
            return "Not Found"
        }
    }
}
''',

    "Sources/JarvisServer/main.swift": '''import Foundation

let args = CommandLine.arguments
let modeStr = args.count > 1 ? args[1].lowercased() : "server"

Logger.shared.write("JARVIS started in mode: \(modeStr)")

switch modeStr {
case "client":
    Logger.shared.write("Client: heartbeat mode")
    while true { Thread.sleep(forTimeInterval: 5) }
case "node":
    Logger.shared.write("Node: task mode")
    while true { Thread.sleep(forTimeInterval: 3) }
default:
    Config.shared.load()
    WebServer.shared.start()
    Logger.shared.write("Server ready → http://127.0.0.1:3000")
    while true { Thread.sleep(forTimeInterval: 1) }
}
''',

    "Resources/index.html": '''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>JARVIS SuperServer</title>
  <style>
    body { font-family: sans-serif; padding: 20px; background: #1a1a1d; color: #e0e0e0; }
    .panel { border: 1px solid #333; padding: 15px; margin-bottom: 20px; border-radius: 6px; background: #2a2a2e; }
    h2 { margin-top: 0; border-bottom: 1px solid #444; padding-bottom: 8px; }
    pre { white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>JARVIS</h1>
  <div class="panel">
    <h2>System Status</h2>
    <pre id="status">Loading...</pre>
  </div>
  <script>
    fetch('/api/status').then(r => r.text()).then(d => {
      document.getElementById('status').innerText = d;
    });
  </script>
</body>
</html>
'''
}

for rel, content in files.items():
    path = os.path.join(BASE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  ✓ {rel}")

print("\n🔨 Building...")
os.chdir(BASE)
result = subprocess.run(["swift", "build", "-c", "release"], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("ERRORS:\n" + result.stderr)
else:
    print("✓ Build OK")
    print(f"  Binary: {BASE}/.build/release/JarvisServer")
    print("  Run:    {BASE}/.build/release/JarvisServer")
    print("  URL:    http://127.0.0.1:3000")
