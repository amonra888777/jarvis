#!/usr/bin/env python3
import os, shutil, subprocess, glob, stat

BASE = os.path.expanduser("~/Projects/JARVIS-SuperServer")
APP_DIR = os.path.expanduser("~/Applications/JARVIS-Server.app")

os.chdir(BASE)
print("1/6 Building Swift project...")
r = subprocess.run(["swift", "build", "-c", "release"], capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr)
    exit(1)

BIN = os.path.join(BASE, ".build/release/JarvisServer")
if not os.path.exists(BIN):
    print("Binary not found!")
    exit(1)

bundles = glob.glob(os.path.join(BASE, ".build/release/*.bundle"))

print("2/6 Creating .app structure...")
if os.path.exists(APP_DIR):
    shutil.rmtree(APP_DIR)

contents = os.path.join(APP_DIR, "Contents")
macos = os.path.join(contents, "MacOS")
resources = os.path.join(contents, "Resources")
os.makedirs(macos)
os.makedirs(resources)

print("3/6 Copying binary...")
shutil.copy2(BIN, os.path.join(macos, "JarvisServer"))
# Явно ставим права на выполнение
os.chmod(os.path.join(macos, "JarvisServer"), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

print("4/6 Copying resource bundles (next to binary)...")
for b in bundles:
    name = os.path.basename(b)
    dest = os.path.join(macos, name)
    shutil.copytree(b, dest)
    # Bundle тоже должен быть доступен для чтения
    os.chmod(dest, stat.S_IRWXU)

html_src = os.path.join(BASE, "Sources/JarvisServer/Resources/index.html")
if os.path.exists(html_src):
    shutil.copy2(html_src, os.path.join(resources, "index.html"))

print("5/6 Writing Info.plist...")
plist = r'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>JARVIS Server</string>
    <key>CFBundleDisplayName</key>
    <string>JARVIS</string>
    <key>CFBundleIdentifier</key>
    <string>com.jarvis.server</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>JarvisServer</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSNetworkUsageDescription</key>
    <string>JARVIS needs network access for the web server</string>
</dict>
</plist>
'''

with open(os.path.join(contents, "Info.plist"), "w") as f:
    f.write(plist)

with open(os.path.join(contents, "PkgInfo"), "w") as f:
    f.write("APPL????")

print("6/6 Done.")
print(f"App: {APP_DIR}")

