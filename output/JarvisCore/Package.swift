// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "JarvisCore",
    platforms: [.macOS(.v10_15)],
    products: [.executable(name: "JarvisCore", targets: ["JarvisCore"])],
    targets: [.executableTarget(name: "JarvisCore", path: "Sources/JarvisCore")]
)
