#!/usr/bin/env python3
import os, shutil, subprocess, sys, json
from pathlib import Path

ARCHIVE = Path("/Users/markluck/Downloads/jarvis-archive-from-downloads")
OUT = Path("/Users/markluck/jarvis-apps")

# Очищаем выходную папку
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

# --- Читаем индекс ---
idx_file = ARCHIVE / "files_index.json"
if not idx_file.exists():
    print("❌ files_index.json не найден. Сначала запусти scan_downloads.py")
    sys.exit(1)

with open(idx_file) as f:
    index = json.load(f)

# --- Ищем нужные Swift файлы в архиве ---
def find_in_archive(name):
    for cat in ["Sources", "Scripts", "DB", "Docs", "Other"]:
        d = ARCHIVE / cat
        if d.exists():
            for p in d.rglob("*"):
                if p.name == name or p.name.startswith(name.rsplit(".", 1)[0]):
                    return p
    return None

# --- Функция исправления ошибок в Swift ---
def fix_swift(content):
    fixes = [
        ("0?.<5", "0..<5"),
        ("0?.<12", "0..<12"),
        ("0><5", "0..<5"),
        ("0><12", "0..<12"),
        ("String(bound:", "String(format:"),
        (".ignoresafeArea()", ".ignoresSafeArea()"),
        ("CFFloat.random", "CGFloat.random"),
        ("CFFloat.pi", "CGFloat.pi"),
        ("rotateBy(\n                x: 0,\n                y: 0,\n                x:", "rotateBy(\n                x: 0,\n                y: 0,\n                z:"),
        ("rotateBy(x: 0, y: 0, x:", "rotateBy(x: 0, y: 0, z:"),
        ("sin(t * .pi * 4)", "sin(Double(t) * Double.pi * 4)"),
        ("sin(t * .pi)", "sin(Double(t) * Double.pi)"),
    ]
    for old, new in fixes:
        content = content.replace(old, new)
    return content

# --- Создание SPM проекта ---
def create_spm(name, swift_files):
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

    # Копируем и чиним Swift файлы
    for sf in swift_files:
        if sf and sf.exists():
            content = sf.read_text(encoding="utf-8")
            fixed = fix_swift(content)
            dst = src / sf.name
            # Если уже есть main.swift, не перезаписываем
            if dst.name == "main.swift" and (src / "main.swift").exists():
                dst = src / f"module_{sf.name}"
            dst.write_text(fixed, encoding="utf-8")

    return proj

# --- Поиск файлов ---
shared = find_in_archive("JarvisShared.swift")
main_swift = find_in_archive("main.swift")
client_swift = find_in_archive("JarvisClient_main.swift")
node_swift = find_in_archive("JarvisNode_main.swift")

print("📦 Найденные файлы:")
print(f"   JarvisShared.swift: {shared}")
print(f"   main.swift: {main_swift}")
print(f"   JarvisClient_main.swift: {client_swift}")
print(f"   JarvisNode_main.swift: {node_swift}")

# --- Приложение 1: JarvisCore (сервер + Metal) ---
print("\n🔧 Сборка JarvisCore (сервер)...")
core_files = [x for x in [shared, main_swift] if x]
core_proj = create_spm("JarvisCore", core_files)

# --- Приложение 2: JarvisGUI (клиент-чат) ---
print("🔧 Сборка JarvisGUI (клиент)...")
gui_files = [x for x in [shared, client_swift] if x]
gui_proj = create_spm("JarvisGUI", gui_files)

# --- Приложение 3: JarvisNode (воркер) ---
print("🔧 Сборка JarvisNode (нода)...")
node_files = [x for x in [shared, node_swift] if x]
node_proj = create_spm("JarvisNode", node_files)

# --- Компиляция всех 3 ---
results = []
for proj in [core_proj, gui_proj, node_proj]:
    print(f"\n⚙️  Компиляция: {proj.name}")
    try:
        r = subprocess.run(
            ["swift", "build", "-c", "release"],
            cwd=proj,
            capture_output=True,
            text=True,
            timeout=120
        )
        if r.returncode == 0:
            binary = proj / ".build" / "release" / proj.name
            print(f"   ✅ Собран: {binary}")
            # Подпись
            try:
                subprocess.run(
                    ["codesign", "--force", "--sign", "-", str(binary)],
                    capture_output=True, timeout=10
                )
                print(f"   ✅ Подписан")
            except:
                print(f"   ⚠️ Подпись не удалась (ненужно для локального запуска)")
            results.append((proj.name, True, binary))
        else:
            print(f"   ❌ Ошибка: {r.stderr[:500]}")
            results.append((proj.name, False, r.stderr[:500]))
    except subprocess.TimeoutExpired:
        print(f"   ⚠️ Таймаут сборки")
        results.append((proj.name, False, "timeout"))
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        results.append((proj.name, False, str(e)))

# --- Создание .app для успешных сборок ---
print("\n📦 Упаковка в .app...")
for name, ok, info in results:
    if not ok:
        continue
    binary = info
    app_dir = OUT / f"{name}.app"
    macos = app_dir / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    shutil.copy(binary, macos / name)

    # Info.plist
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

    # Подпись .app
    try:
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(app_dir)],
            capture_output=True, timeout=10
        )
    except:
        pass
    print(f"   ✅ {app_dir}")

# --- Итог ---
print("\n" + "=" * 60)
print("ИТОГ СБОРКИ")
print("=" * 60)
for name, ok, info in results:
    status = "✅ OK" if ok else "❌ FAIL"
    print(f"  {name}: {status}")

ok_count = sum(1 for _, ok, _ in results if ok)
print(f"\nСобрано: {ok_count}/3")

if ok_count > 0:
    print(f"\n📂 Папка с приложениями: {OUT}")
    print("   .app файлы можно запускать двойным кликом")
    print("   SPM проекты можно открыть в Xcode: open " + str(OUT / results[0][0] / "Package.swift"))

# Сохраняем отчёт
report = OUT / "BUILD_REPORT.txt"
with open(report, "w") as f:
    f.write(f"BUILD REPORT — {__import__('datetime').datetime.now()}\n")
    f.write(f"Archive: {ARCHIVE}\n")
    f.write(f"Output: {OUT}\n\n")
    for name, ok, info in results:
        f.write(f"{name}: {'OK' if ok else 'FAIL'}\n")
        if not ok and isinstance(info, str):
            f.write(f"  Error: {info[:1000]}\n")
    f.write("\n")
    f.write("Files used:\n")
    f.write(f"  Shared: {shared}\n")
    f.write(f"  Main: {main_swift}\n")
    f.write(f"  Client: {client_swift}\n")
    f.write(f"  Node: {node_swift}\n")
print(f"\n📋 Отчёт: {report}")
