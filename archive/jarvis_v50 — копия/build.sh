#!/usr/bin/env bash
set -e
cd ~/jarvis_v50
rm -rf build/*
mkdir -p build/JarvisServer.app/Contents/MacOS
mkdir -p build/JarvisClient.app/Contents/MacOS
mkdir -p build/JarvisNode.app/Contents/MacOS

echo "Building JarvisServer (3D SceneKit GUI)..."
swiftc -O Shared/JarvisShared.swift JarvisServer/main.swift -o build/JarvisServer -framework Foundation -framework Network -framework SwiftUI -framework SceneKit -framework AppKit -parse-as-library
cp build/JarvisServer build/JarvisServer.app/Contents/MacOS/JarvisServer
echo "  OK"

echo "Building JarvisClient..."
swiftc -O Shared/JarvisShared.swift JarvisClient/main.swift -o build/JarvisClient -framework Foundation -framework Network -framework SwiftUI -framework AppKit -parse-as-library
cp build/JarvisClient build/JarvisClient.app/Contents/MacOS/JarvisClient
echo "  OK"

echo "Building JarvisNode..."
swiftc -O Shared/JarvisShared.swift JarvisNode/main.swift -o build/JarvisNode -framework Foundation -framework Network
cp build/JarvisNode build/JarvisNode.app/Contents/MacOS/JarvisNode
echo "  OK"

codesign --force --sign - build/JarvisServer.app 2>/dev/null && echo "Server signed" || true
codesign --force --sign - build/JarvisClient.app 2>/dev/null && echo "Client signed" || true
codesign --force --sign - build/JarvisNode.app 2>/dev/null && echo "Node signed" || true

echo ""
echo "=== ALL 3 APPS BUILT ==="
ls -la build/*.app/Contents/MacOS/
