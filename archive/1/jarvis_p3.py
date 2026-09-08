import os
b = os.path.expanduser("~/Projects/JARVIS-SuperServer/Sources/JarvisServer")
def w(name, code):
    with open(os.path.join(b, name), "w") as f:
        f.write(code)
    print("OK:", name, len(code), "bytes")

w("AIManager.swift", r'''import Foundation
final class AIManager {
    static let shared = AIManager()
    private(set) var alicePlusEnabled = false
    private(set) var activeProvider = "auto"
    private(set) var providers: [String: Bool] = [:]

    func updateProviders() {
        providers["ollama"] = OllamaManager.shared.isRunning
        providers["yandex"] = YandexAuth.shared.isAuthorized
        providers["giga"] = !AIConfig.gigaAuthKey.isEmpty
        providers["openai"] = !AIConfig.openaiAPIKey.isEmpty
        alicePlusEnabled = YandexAuth.shared.isAuthorized && YandexAuth.shared.useProModel
        Logger.shared.write("AIManager: providers=

