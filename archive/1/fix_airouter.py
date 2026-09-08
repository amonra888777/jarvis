import os

path = os.path.expanduser("~/Projects/JARVIS-SuperServer/Sources/JarvisServer/AIRouter.swift")

code = r'''import Foundation

struct AIConfig {
    static var ollamaURL: String { OllamaManager.shared.ollamaURL + "/api/chat" }
    static let ollamaModel = "qwen3:0.6b"
    static let yandexURL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    static let yandexModel = "yandexgpt"
    static let gigaAuthKey = ""
    static let gigaScope = "GIGACHAT_API_PERS"
    static let gigaBaseURL = "https://api.giga.chat"
    static let gigaOAuthURL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    static let gigaModel = "GigaChat-2-Pro"
    static let openaiAPIKey = ""
    static let openaiURL = "https://api.openai.com/v1/chat/completions"
    static let openaiModel = "gpt-4o-mini"
}

class AIRouter {
    static let shared = AIRouter()
    private var gigaToken: String?
    private var gigaTokenExpiry: Date?

    func status() -> [String: [String: Any]] {
        return [
            "ollama": ["available": OllamaManager.shared.isRunning, "name": "Ollama"],
            "yandex": ["available": YandexAuth.shared.isAuthorized, "name": "YandexGPT"],
            "giga": ["available": !AIConfig.gigaAuthKey.isEmpty, "name": "GigaChat"],
            "openai": ["available": !AIConfig.openaiAPIKey.isEmpty, "name": "OpenAI"]
        ]
    }

    func chat(message: String, provider: String, history: [[String: String]]) async throws -> (response: String, provider: String) {
        let providers = provider == "auto" ? ["ollama", "yandex", "giga", "openai"] : [provider]
        var lastError: Error?
        for p in providers {
            do {
                let resp = try await callProvider(p, message: message, history: history)
                return (resp, p)
            } catch { lastError = error; continue }
        }
        throw lastError ?? NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "No AI available"])
    }

    private func callProvider(_ provider: String, message: String, history: [[String: String]]) async throws -> String {
        switch provider {
        case "ollama": return try await callOllama(message: message, history: history)
        case "yandex": return try await callYandexGPT(message: message, history: history)
        case "giga": return try await callGigaChat(message: message, history: history)
        case "openai": return try await callOpenAI(message: message, history: history)
        default: throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unknown provider"])
        }
    }

    private func callOllama(message: String, history: [[String: String]]) async throws -> String {
        var msgs: [[String: String]] = [["role": "system", "content": "Ты - JARVIS. Отвечай на русском, кратко."]]
        for m in history { msgs.append(["role": m["role"] ?? "user", "content": m["content"] ?? ""]) }
        msgs.append(["role": "user", "content": message])
        let body: [String: Any] = ["model": AIConfig.ollamaModel, "messages": msgs, "stream": false]
        let data = try await postJSON(url: AIConfig.ollamaURL, body: body, headers: ["Content-Type": "application/json"])
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        return ((json["message"] as? [String: Any])?["content"] as? String) ?? "Ollama: пустой ответ"
    }

    private func callYandexGPT(message: String, history: [[String: String]]) async throws -> String {
        guard YandexAuth.shared.isAuthorized else {
            throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "YandexGPT: не авторизован"])
        }
        let semaphore = DispatchSemaphore(value: 0)
        var result: String?
        var errorMsg: String?
        YandexAuth.shared.chat(message: message, history: history) { response, error in
            result = response
            errorMsg = error
            semaphore.signal()
        }
        _ = semaphore.wait(timeout: .now() + 30)
        if let r = result { return r }
        throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: errorMsg ?? "YandexGPT: нет ответа"])
    }

    private func callGigaChat(message: String, history: [[String: String]]) async throws -> String {
        guard !AIConfig.gigaAuthKey.isEmpty else { throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "GigaChat: нет ключа"]) }
        if gigaToken == nil || Date() > (gigaTokenExpiry ?? Date()) {
            gigaToken = try await getGigaToken()
            gigaTokenExpiry = Date().addingTimeInterval(25 * 60)
        }
        var msgs: [[String: String]] = [["role": "system", "content": "Ты - JARVIS. Отвечай на русском, кратко."]]
        for m in history { msgs.append(["role": m["role"] ?? "user", "content": m["content"] ?? ""]) }
        msgs.append(["role": "user", "content": message])
        let body: [String: Any] = ["model": AIConfig.gigaModel, "messages": msgs, "temperature": 0.6, "max_tokens": 2000]
        let data = try await postJSON(
            url: AIConfig.gigaBaseURL + "/v1/chat/completions",
            body: body,
            headers: ["Content-Type": "application/json", "Authorization": "Bearer " + (gigaToken ?? "")]
        )
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        let choices = json["choices"] as? [[String: Any]] ?? []
        return ((choices.first?["message"] as? [String: Any])?["content"] as? String) ?? "GigaChat: нет ответа"
    }

    private func getGigaToken() async throws -> String {
        let url = URL(string: AIConfig.gigaOAuthURL)!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue(UUID().uuidString, forHTTPHeaderField: "RqUID")
        req.setValue("Basic " + AIConfig.gigaAuthKey, forHTTPHeaderField: "Authorization")
        req.httpBody = ("scope=" + AIConfig.gigaScope).data(using: .utf8)
        let (data, response) = try await URLSession(configuration: .ephemeral).data(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "GigaChat OAuth failed"])
        }
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        return (json["access_token"] as? String) ?? ""
    }

    private func callOpenAI(message: String, history: [[String: String]]) async throws -> String {
        guard !AIConfig.openaiAPIKey.isEmpty else { throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "OpenAI: нет ключа"]) }
        var msgs: [[String: String]] = [["role": "system", "content": "Ты - JARVIS. Отвечай на русском, кратко."]]
        for m in history { msgs.append(["role": m["role"] ?? "user", "content": m["content"] ?? ""]) }
        msgs.append(["role": "user", "content": message])
        let body: [String: Any] = ["model": AIConfig.openaiModel, "messages": msgs, "temperature": 0.6, "max_tokens": 2000]
        let data = try await postJSON(
            url: AIConfig.openaiURL,
            body: body,
            headers: ["Content-Type": "application/json", "Authorization": "Bearer " + AIConfig.openaiAPIKey]
        )
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        let choices = json["choices"] as? [[String: Any]] ?? []
        return ((choices.first?["message"] as? [String: Any])?["content"] as? String) ?? "OpenAI: нет ответа"
    }

    private func postJSON(url: String, body: [String: Any], headers: [String: String]) async throws -> Data {
        guard let urlObj = URL(string: url) else {
            throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"])
        }
        var req = URLRequest(url: urlObj)
        req.httpMethod = "POST"
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        req.timeoutInterval = 30
        let (data, response) = try await URLSession.shared.data(for: req)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let s = String(data: data, encoding: .utf8) ?? ""
            let code = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw NSError(domain: "AIRouter", code: code, userInfo: [NSLocalizedDescriptionKey: "HTTP " + String(code) + ": " + s])
        }
        return data
    }
}
'''

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print(f"OK: AIRouter.swift written ({len(code)} bytes)")

