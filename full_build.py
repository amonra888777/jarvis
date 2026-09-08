#!/usr/bin/env python3
import os, shutil, subprocess, sys, json, time, uuid, datetime
from pathlib import Path

ARCHIVE = Path("./archive")
OUT = Path("./output")
LOGS = Path("./logs")

LOGS.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

def log(msg):
    print(msg)
    with open(LOGS / "build.log", "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {msg}\n")

def fix_swift_code(code: str) -> str:
    fixes = [
        ("0?.<5", "0..<5"), ("0?.<12", "0..<12"),
        ("0><5", "0..<5"), ("0><12", "0..<12"),
        ("String(bound:", "String(format:"),
        (".ignoresafeArea()", ".ignoresSafeArea()"),
        (".ignoresSafearea()", ".ignoresSafeArea()"),
        ("CFFloat.random", "CGFloat.random"),
        ("CFFloat.pi", "CGFloat.pi"), ("CFFloat", "CGFloat"),
        ("rotateBy(x: 0, y: 0, x:", "rotateBy(x: 0, y: 0, z:"),
        ("sin(t * .pi * 4)", "sin(Double(t) * Double.pi * 4)"),
        ("sin(t * .pi)", "sin(Double(t) * Double.pi)"),
    ]
    for old, new in fixes:
        code = code.replace(old, new)
    return code

def make_project(name, main_code, ref_code=None):
    proj = OUT / name
    src = proj / "Sources" / name
    src.mkdir(parents=True, exist_ok=True)

    pkg = f'''// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "{name}",
    products: [.executable(name: "{name}", targets: ["{name}"])],
    targets: [.executableTarget(name: "{name}", path: "Sources/{name}")]
)
'''
    (proj / "Package.swift").write_text(pkg)
    (src / "main.swift").write_text(main_code)

    if ref_code:
        ref_dir = proj / "Reference"
        ref_dir.mkdir(exist_ok=True)
        (ref_dir / "original_code.swift").write_text(ref_code)

    readme = f'''# {name}
Собрано: {datetime.datetime.now().isoformat()}

## Запуск
cd {proj}
swift build -c release
.build/release/{name}

## Открыть в Xcode
open {proj}/Package.swift
'''
    (proj / "README.md").write_text(readme)
    log(f"Project {name} created")
    return proj

CORE_STUB = '''import Foundation
import Network

struct JarvisMessage: Codable {
    let type: String
    let text: String?
    let source: String
}

final class JarvisServer {
    private var listener: NWListener?
    private var connections: [NWConnection] = []
    private var startTime: Date?

    var uptime: String {
        guard let s = startTime else { return "00:00:00" }
        let i = Int(Date().timeIntervalSince(s))
        return String(format: "%02d:%02d:%02d", i / 3600, (i % 3600) / 60, i % 60)
    }

    func start(port: UInt16 = 7777) {
        startTime = Date()
        guard let p = NWEndpoint.Port(rawValue: port) else { return }
        do {
            listener = try NWListener(using: .tcp, on: p)
        } catch {
            print("Error creating listener: \\(error)")
            return
        }
        listener?.newConnectionHandler = { [weak self] c in self?.handle(c) }
        listener?.start(queue: .global())
        print("JarvisCore запущен на порту \\(port)")
    }

    private func handle(_ c: NWConnection) {
        c.start(queue: .global())
        connections.append(c)
        receive(c)
    }

    private func receive(_ c: NWConnection) {
        c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] d, _, _, e in
            if let e = e { return }
            if let d = d, !d.isEmpty { self?.process(d, c) }
            self?.receive(c)
        }
    }

    private func process(_ data: Data, _ c: NWConnection) {
        guard let m = try? JSONDecoder().decode(JarvisMessage.self, from: data) else { return }
        var r = "OK"
        switch m.type.lowercased() {
        case "ping": r = "pong"
        case "status": r = "Core OK. Conns: \\(connections.count). Up: \\(uptime)"
        case "help": r = "status, help, ping, boss, wiring"
        case "boss": r = "Boss GX-10: Clean, Crunch, Lead. Online."
        case "wiring": r = "Humbucker: green=start, white=end, red=south, black=ground."
        default: r = m.text ?? "OK"
        }
        let resp = JarvisMessage(type: "response", text: r, source: "core")
        if let d = try? JSONEncoder().encode(resp) {
            c.send(content: d, completion: .contentProcessed { _ in })
        }
    }
}

@main
struct JarvisCoreApp {
    static func main() {
        let s = JarvisServer()
        s.start()
        print("Ctrl+C для остановки")
        while true { sleep(1) }
    }
}
'''

GUI_STUB = '''import Foundation
import Network

struct JarvisMessage: Codable {
    let type: String
    let text: String?
    let source: String
}

@main
struct JarvisGUIApp {
    static func main() {
        print("=== JARVIS GUI CLIENT v1.0 ===")
        print("Подключение к 127.0.0.1:7777...")
        let conn = NWConnection(to: .hostPort(host: "127.0.0.1", port: 7777), using: .tcp)
        conn.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("✅ Подключено к серверу!")
                print("Доступные команды: status, help, ping, boss, wiring, quit")
                print()
            case .failed:
                print("❌ Не удалось подключиться. Сначала запустите JarvisCore.")
                exit(1)
            default: break
            }
        }
        conn.start(queue: .main)
        sleep(2)
        while let input = readLine() {
            let cmd = input.trimmingCharacters(in: .whitespaces)
            if cmd.isEmpty { continue }
            if cmd == "quit" || cmd == "exit" { break }
            let msg = JarvisMessage(type: cmd, text: cmd, source: "user")
            if let d = try? JSONEncoder().encode(msg) {
                conn.send(content: d, completion: .contentProcessed { _ in })
            }
            sleep(1)
        }
        conn.cancel()
        print("Отключено.")
    }
}
'''

NODE_STUB = '''import Foundation
import Network

struct JarvisMessage: Codable {
    let type: String
    let text: String?
    let source: String
}

@main
struct JarvisNodeApp {
    static func main() {
        let id = "node-" + String(UUID().uuidString.prefix(8))
        print("JarvisNode \\(id) запущен")
        let conn = NWConnection(to: .hostPort(host: "127.0.0.1", port: 7777), using: .tcp)
        conn.stateUpdateHandler = { state in
            switch state {
            case .ready: print("✅ Нода \\(id) подключена к серверу")
            case .failed: print("❌ Нет сервера. Сначала запустите JarvisCore."); exit(1)
            default: break
            }
        }
        conn.start(queue: .global())
        sleep(2)
        var beat = 0
        while true {
            beat += 1
            let cpu = String(format: "%.2f", Double.random(in: 0.1...0.9))
            let payload = "\\(id)|\\(cpu)"
            let msg = JarvisMessage(type: "heartbeat", text: payload, source: id)
            if let d = try? JSONEncoder().encode(msg) {
                conn.send(content: d, completion: .contentProcessed { _ in })
            }
            print("  Beat #\\(beat): CPU=\\(cpu)")
            sleep(5)
        }
    }
}
'''

core_proj = make_project("JarvisCore", CORE_STUB)
gui_proj  = make_project("JarvisGUI", GUI_STUB)
node_proj = make_project("JarvisNode", NODE_STUB)

results = []
for proj in [core_proj, gui_proj, node_proj]:
    name = proj.name
    log(f"\nСборка {name}...")
    try:
        r = subprocess.run(
            ["swift", "build", "-c", "release"],
            cwd=proj,
            capture_output=True,
            text=True,
            timeout=180
        )
        if r.returncode == 0:
            binary = proj / ".build" / "release" / name
            log(f"✅ {name} собран: {binary}")
            results.append((name, True, binary))
        else:
            err = r.stderr or r.stdout
            log(f"❌ {name} ошибка: {err[:800]}")
            results.append((name, False, err))
    except Exception as e:
        log(f"❌ {name} исключение: {e}")
        results.append((name, False, str(e)))

for name, ok, info in results:
    if not ok: continue
    binary = info
    app_dir = OUT / f"{name}.app"
    macos_dir = app_dir / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(binary, macos_dir / name)

    plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>{name}</string>
    <key>CFBundleIdentifier</key><string>com.markluck.{name.lower()}</string>
    <key>CFBundleName</key><string>{name}</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>LSMinimumSystemVersion</key><string>12.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>'''
    (app_dir / "Contents" / "Info.plist").write_text(plist)

    try:
        subprocess.run(["codesign", "--force", "--sign", "-", str(app_dir)], capture_output=True, timeout=15)
        log(f"✅ {name}.app подписан")
    except:
        log(f"⚠️ {name}.app — подпись не удалась (локально ок)")

ok_count = sum(1 for _, ok, _ in results if ok)
with open(OUT / "BUILD_REPORT.txt", "w") as f:
    f.write(f"BUILD REPORT — {datetime.datetime.now()}\n{'='*60}\n\n")
    f.write(f"Archive: {ARCHIVE}\nOutput: {OUT}\n\n")
    for name, ok, info in results:
        status = "✅ OK" if ok else "❌ FAIL"
        f.write(f"{name}: {status}\n")
        if ok:
            f.write(f"  Binary: {info}\n  App: {OUT / f'{name}.app'}\n")
        else:
            f.write(f"  Error: {str(info)[:1000]}\n")
        f.write("\n")
    f.write(f"\nИтого: {ok_count}/3 собрано\n")

print("\n" + "="*60)
print("ИТОГ")
print("="*60)
for name, ok, _ in results:
    print(f"  {name}: {'✅' if ok else '❌'}")
print(f"\nПриложения: {OUT}")
print("Готово!")
