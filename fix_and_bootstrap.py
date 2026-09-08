#!/usr/bin/env python3
import os
from pathlib import Path

OUT = Path("/Users/markluck/jarvis-apps")

def make_package(name, main_code):
    proj = OUT / name
    src = proj / "Sources" / name
    src.mkdir(parents=True, exist_ok=True)

    # Package.swift
    pkg = f'''// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "{name}",
    products: [
        .executable(name: "{name}", targets: ["{name}"]),
    ],
    targets: [
        .executableTarget(
            name: "{name}",
            dependencies: [],
            path: "Sources/{name}"
        ),
    ]
)
'''
    (proj / "Package.swift").write_text(pkg)

    # main.swift — гарантированно компилируемый
    (src / "main.swift").write_text(main_code)

# --- JarvisCore: серверная часть (заглушка) ---
core_code = '''import Foundation

@main
struct JarvisCore {
    static func main() {
        print("JarvisCore started.")
        // Сюда позже вставим логику сервера
        while true {
            sleep(1)
        }
    }
}
'''

# --- JarvisGUI: клиент/чат (заглушка) ---
gui_code = '''import Foundation

@main
struct JarvisGUI {
    static func main() {
        print("JarvisGUI started.")
        print("Type something to chat with Jarvis:")
        while let line = readLine() {
            print("You said: \\(line)")
            // Сюда позже добавим GUI/Metal
        }
    }
}
'''

# --- JarvisNode: воркер/нода (заглушка) ---
node_code = '''import Foundation

@main
struct JarvisNode {
    static func main() {
        print("JarvisNode started.")
        // Сюда позже вставим обработку устройств/микшеров
        while true {
            sleep(2)
        }
    }
}
'''

make_package("JarvisCore", core_code)
make_package("JarvisGUI", gui_code)
make_package("JarvisNode", node_code)

print("✅ Каркасы созданы в ~/jarvis-apps")
