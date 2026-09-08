// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "JarvisGUI",
    platforms: [.macOS(.v10_15)],
    products: [.executable(name: "JarvisGUI", targets: ["JarvisGUI"])],
    targets: [.executableTarget(name: "JarvisGUI", path: "Sources/JarvisGUI")]
)
