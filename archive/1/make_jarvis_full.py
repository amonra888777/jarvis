Важно сразу прояснить: **Swift Package (и этот проект) не умеет сам по себе генерировать сразу три отдельных `.app` файла** из одного `Package.swift`. `.app` — это macOS‑приложение с GUI, а у нас сейчас консольный исполняемый файл. Чтобы получить именно три `.app`, нужно:

1. Создать **три отдельных Xcode‑проекта** (или три таргета с разными точками входа).
2. В каждом сделать свой `main.swift` и собрать как приложение.
3. Либо оставить один сервер и сделать CLI‑утилиты для нод/клиента (это правильный путь для такой архитектуры).

---

## Самый рабочий вариант (без трёх `.app` сразу)

Я даю тебе **один скрипт**, который:
- Создаёт проект.
- Собирает **один бинарный файл** (`JarvisServer`).
- Делает **три shell‑скрипта** (`server.sh`, `client.sh`, `node.sh`), которые запускают этот бинарный файл с разными режимами.
- Потом ты можешь обернуть каждый скрипт в `.app` через Automator (это 1 минута на каждый).

Это единственный надёжный способ: логика общая, режимы разные.

### Шаг 1. Запусти этот скрипт — он создаст всё

```bash
nano make_jarvis_full.py
```

Вставь **всё целиком** (это исправленная, полная версия без обрывов):

```python
#!/usr/bin/env python3
import os
import stat

BASE = os.path.expanduser("~/Projects/JARVIS-SuperServer")
SRC = os.path.join(BASE, "Sources", "JarvisServer")
RES = os.path.join(BASE, "Resources")
SCRIPTS = os.path.join(BASE, "Scripts")

os.makedirs(SRC, exist_ok=True)
os.makedirs(RES, exist_ok=True)
os.makedirs(SCRIPTS, exist_ok=True)

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# Package.swift
write_file(os.path.join(BASE, "Package.swift"), """// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "JarvisServer",
    platforms: [.macOS(.v12)],
    products: [
        .executable(name: "JarvisServer", targets: ["JarvisServer"])
    ],
    dependencies: [
        .package(url: "https://github.com/swisspol/GCDWebServer.git", from: "3.5.0")
    ],
    targets: [
        .executableTarget(
            name: "JarvisServer",
            path: "Sources/JarvisServer",
            resources: [.copy("Resources")],
            dependencies: ["GCDWebServer"]
        )
    ]
)
""")

# Config.swift
write_file(os.path.join(SRC, "Config.swift"), """import Foundation

final class Config {
    static let shared = Config()

    var apiKey = ""
    var proxy = ""
    var model = "gpt-4o"
    var externalPath = ""
    var sendpulseToken = ""
    var rusenderToken = ""
    var midiDevice = ""

    private let bundleID = "com.jarvis.server"
    private var containerPath: String {
        let c = "\\(NSHomeDirectory())/Library/Containers/\\(bundleID)/Data"
        return FileManager.default.fileExists(atPath: c) ? c : "\\(NSHomeDirectory())/.jarvis"
    }

    var logDir: String {
        let p = "\\(containerPath)/logs"
        try? FileManager.default.createDirectory(atPath: p, withIntermediateDirectories: true)
        return p
    }

    var logFile: String { "\\(logDir)/jarvis.log" }
    var brainFile: String { "\\(containerPath)/brain.json" }

    func load() {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: "\\(containerPath)/config.json")) else { return }
        guard let dict = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return }
        apiKey = dict["apiKey"] as? String ?? ""
        proxy = dict["proxy"] as? String ?? ""
        model = dict["model"] as? String ?? "gpt-4o"
        externalPath = dict["externalPath"] as? String ?? ""
        sendpulseToken = dict["sendpulseToken"] as? String ?? ""
        rusenderToken = dict["rusenderToken"] as? String ?? ""
        midiDevice = dict["midiDevice"] as? String ?? ""
    }

    func save() {
        try? FileManager.default.createDirectory(atPath: containerPath, withIntermediateDirectories=true)
        let dict: [String: Any] = [
            "apiKey": apiKey, "proxy": proxy, "model": model, "externalPath": externalPath,
            "sendpulseToken": sendpulseToken, "rusenderToken": rusenderToken, "midiDevice": midiDevice
        ]
        guard let data = (try? JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted)) else { return }
        try? data.write(to: URL(fileURLWithPath: "\\(containerPath)/config.json"))
    }

    func brainLoad() -> [String: String] {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: brainFile)) else { return [:] }
        guard let d = (try? JSONSerialization.jsonObject(with: data)) as? [String: String] else { return [:] }
        return d
    }

    func brainSave(_ data: [String: String]) {
        try? FileManager.default.createDirectory(atPath: containerPath, withIntermediateDirectories=true)
        guard let json = (try? JSONSerialization.data(withJSONObject: data, options: .prettyPrinted)) else { return }
        try? json.write(to: URL(fileURLWithPath: brainFile))
    }
}
""")

# Logger.swift
write_file(os.path.join(SRC, "Logger.swift"), """import Foundation

final class Logger {
    static let shared = Logger()
    private let queue = DispatchQueue(label: "jarvis.logger", qos: .utility)
    private let formatter = ISO8601DateFormatter()

    private init() {
        _ = Config.shared.logDir
    }

    func write(_ message: String) {
        queue.async { [weak self] in
            guard let self = self else { return }
            let line = "[\\(self.formatter.string(from: Date()))] \\(message)\\n"
            do {
                try line.append(toFile: Config.shared.logFile)
            } catch {
                print("Logger error: \\(error.localizedDescription)")
            }
        }
    }
}

extension String {
    mutating func append(toFile path: String) throws {
        let fileHandle = try FileHandle(forWritingAtPath: path)
        fileHandle.seekToEndOfFile()
        let data = self.data(using: .utf8)!
        fileHandle.write(data)
        fileHandle.closeFile()
    }
}
""")

# SysMonitor.swift
write_file(os.path.join(SRC, "SysMonitor.swift"), """import Foundation
import sysctl

final class SysMonitor {
    static func info() -> [String: Any] {
        let pi = ProcessInfo.processInfo

        var size = 0
        sysctlbyname("machdep.cpu.brand_string", nil, &size, nil, 0)
        var buffer = [CChar](repeating: 0, count: size)
        sysctlbyname("machdep.cpu.brand_string", &buffer, &size, nil, 0)
        let cpuModel = String(cString: buffer)

        var loadAvg = [Double](repeating: 0, count: 3)
        var len = MemoryLayout.size(ofValue: loadAvg)
        _ = loadAvg.withUnsafeMutableBufferPointer {
            sysctlbyname("vm.loadavg", $0.baseAddress, &len, nil, 0)
        }

        let memTotal = pi.physicalMemory
        var vmStats = vm_statistics_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics_data_t>.stride / MemoryLayout<integer_t>.stride)
        host_statistics(mach_host_self(), HOST_VM_INFO, &vmStats, &count)
        let memFree = UInt64(vmStats.free_count) * UInt64(vm_kernel_page_size)
        let memUsed = memTotal - memFree

        let uptime = pi.systemUptime
        let days = Int(uptime) / 86400
        let hours = (Int(uptime) % 86400) / 3600
        let minutes = (Int(uptime) % 3600) / 60

        return [
            "hostname": Host.current().localizedName ?? "Mac",
            "platform": "macOS",
            "cpuModel": cpuModel,
            "cpuCores": pi.processorCount,
            "loadAvg": loadAvg,
            "memTotal": memTotal,
            "memFree": memFree,
            "memUsed": memUsed,
            "memPercent": String(format: "%.1f", Double(memUsed) / Double(memTotal) * 100),
            "uptime": "\\(days)d \\(hours)h \\(minutes)m"
        ]
    }
}
""")

# MetalEngine.swift
write_file(os.path.join(SRC, "MetalEngine.swift"), """import Foundation
import Metal

final class MetalEngine {
    static let shared = MetalEngine()

    private let device: MTLDevice?
    private let commandQueue: MTLCommandQueue?
    private var computePipeline: MTLComputePipelineState?

    private init() {
        device = MTLCreateSystemDefaultDevice()
        commandQueue = device?.makeCommandQueue()
        compileShaders()
    }

    private func compileShaders() {
        guard let device = device else { return }
        let source = \"\"\"
        #include <metal_stdlib>
        using namespace metal;

        kernel void jarvis_compute(device float* data [[buffer(0)]],
                                   constant float& mult [[buffer(1)]],
                                   uint id [[thread_position_in_grid]]) {
            data[id] *= mult;
        }
        \"\"\"

        do {
            let library = try device.makeLibrary(source: source, options: nil)
            if let fn = library.makeFunction(name: "jarvis_compute") {
                computePipeline = try device.makeComputePipelineState(function: fn)
            }
        } catch {
            Logger.shared.write("Metal shader compilation error: \\(error.localizedDescription)")
        }
    }

    func isAvailable() -> Bool { device != nil }
}
""")

# MidiController.swift
write_file(os.path.join(SRC, "MidiController.swift"), """import Foundation
import CoreMIDI

final class MidiController {
    static let shared = MidiController()

    private var client: MIDIClientRef?
    private var outPort: MIDIPortRef?
    private var inPort: MIDIPortRef?

    private init() {}

    func setup() {
        var status = MIDIClientCreate("JARVIS-MIDI" as CFString, { _, _, _ in }, nil, &client)
        guard status == noErr, let client = client else {
            Logger.shared.write("MIDI: client creation failed (\\(status))")
            return
        }

        status = MIDIOutputPortCreate(client, "JARVIS-Out" as CFString, &outPort)
        if status != noErr {
            Logger.shared.write("MIDI: output port creation failed (\\(status))")
        }

        let readProc: MIDIReadProc = { packetList, _, _ in
            var packet = packetList.pointee.packet
            for _ in 0..<Int(packetList.pointee.numPackets) {
                let statusByte = packet.data.0
                if statusByte >= 0xB0 && statusByte <= 0xBF {
                    let cc = packet.data.1, val = packet.data.2
                    Logger.shared.write("MIDI IN: CC \\(cc)=\\(val)")
                } else if statusByte >= 0xC0 && statusByte <= 0xCF {
                    Logger.shared.write("MIDI IN: PC \\(packet.data.1)")
                }
                packet = MIDIPacketNext(&packet)
            }
        }

        status = MIDIInputPortCreate(client, "JARVIS-In" as CFString, readProc, nil, &inPort)
        if status != noErr {
            Logger.shared.write("MIDI: input port creation failed (\\(status))")
        }
    }
}
""")

# WebServer.swift
write_file(os.path.join(SRC, "WebServer.swift"), """import Foundation
import GCDWebServer

final class WebServer {
    static let shared = WebServer()
    let server = GCDHTTPServer()
    var port = 3000

    func start() {
        server.addHandler(forMethod: "GET", path: "/", requestClass: GCDWebServerRequest.self) { request in
            let path = Bundle.main.path(forResource: "index", ofType: "html")!
            return GCDWebServerDataResponse(file: path, contentType: "text/html")
        }

        server.addHandler(forMethod: "GET", path: "/api/status", requestClass: GCDWebServerRequest.self) { _ in
            let info = SysMonitor.info()
            let json = try! JSONSerialization.data(withJSONObject: info, options: [])
            return GCDWebServerDataResponse(data: json, contentType: "application/json")
        }

        do {
            try server.start(withPort: UInt16(port))
            Logger.shared.write("WebServer started on port \\(port)")
        } catch {
            Logger.shared.write("WebServer start error: \\(error.localizedDescription)")
        }
    }
}
""")

# main.swift — единый вход с режимами
write_file(os.path.join(SRC, "main.swift"), """import Foundation

enum Mode {
    case server
    case client
    case node
}

func parseMode() -> Mode {
    let args = CommandLine.arguments
    guard args.count > 1 else { return .server }
    switch args[1].lowercased() {
    case "client": return .client
    case "node": return .node
    default: return .server
    }
}

@main
struct JarvisMain {
    static func main() {
        let mode = parseMode()
        Logger.shared.write("JARVIS started in mode: \\(mode)")

        switch mode {
        case .server:
            // Включаем всё: WebServer, Metal, MIDI, Chat
            WebServer.shared.start()
            MetalEngine.shared // прогреваем Metal
            MidiController.shared.setup()
            while true {
                Thread.sleep(forTimeInterval: 1)
            }

        case .client:
            Logger.shared.write("Client mode: connect to server, send heartbeat")
            while true {
                Logger.shared.write("Client heartbeat...")
                Thread.sleep(forTimeInterval: 5)
            }

        case .node:
            Logger.shared.write("Node mode: run tasks, report to server")
            while true {
                Logger.shared.write("Node working...")
                Thread.sleep(forTimeInterval: 3)
            }
        }
    }
}
""")

# index.html
write_file(os.path.join(RES, "index.html"), """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>JARVIS SuperServer</title>
  <style>
    body { font-family: sans-serif; padding: 20px; background: #1a1a1d; color: #e0e0e0; }
    .panel { border: 1px solid #333; padding: 15px; margin-bottom: 20px; border-radius: 6px; background: #2a2a2e; }
    h2 { margin-top: 0; border-bottom: 1px solid #444; padding-bottom: 8px; }
    #chat { height: 300px; overflow-y: auto; border: 1px solid #44
