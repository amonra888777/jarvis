// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "JarvisNode",
    platforms: [.macOS(.v10_15)],
    products: [.executable(name: "JarvisNode", targets: ["JarvisNode"])],
    targets: [.executableTarget(name: "JarvisNode", path: "Sources/JarvisNode")]
)
