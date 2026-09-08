import os
b = os.path.expanduser("~/Projects/JARVIS-SuperServer/Sources/JarvisServer")
def w(name, code):
    with open(os.path.join(b, name), "w") as f:
        f.write(code)
    print("OK:", name, len(code), "bytes")

w("WebServer.swift", r'''import Foundation
import Network

final class WebServer {
    static let shared = WebServer()
    private var listener: NWListener?

    func start(port: UInt16 = 3000) {
        do {
            listener = try NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: port)!)
            listener?.newConnectionHandler = { [weak self] c in self?.handle(c) }
            listener?.start(queue: .global(qos: .userInitiated))
            Logger.shared.write("WebServer: port " + String(port))
        } catch { Logger.shared.write("WebServer: " + error.localizedDescription) }
    }

    private func handle(_ conn: NWConnection) {
        conn.start(queue: .global())
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, _, _ in
            guard let data = data, let req = String(data: data, encoding: .utf8) else { conn.cancel(); return }
            let lines = req.components(separatedBy: "\r\n")
            guard let first = lines.first else { conn.cancel(); return }
            let parts = first.components(separatedBy: " ")
            guard parts.count >= 2 else { conn.cancel(); return }
            let method = parts[0]; let rawPath = parts[1]
            let path = rawPath.components(separatedBy: "?").first ?? rawPath
            let bodyStr = req.contains("\r\n\r\n") ? String(req.split(separator: "\r\n\r\n", maxSplits: 1).last ?? "") : ""
            var qp: [String: String] = [:]
            if let qi = rawPath.firstIndex(of: "?") {
                for pair in String(rawPath[rawPath.index(after: qi)...]).components(separatedBy: "&") {
                    let kv = pair.components(separatedBy: "="); if kv.count == 2 { qp[kv[0]] = kv[1].removingPercentEncoding ?? kv[1] }
                }
            }
            self?.route(method: method, path: path, qp: qp, body: bodyStr) { resp, ct in
                let h = "HTTP/1.1 200 OK\r\nContent-Type: " + (ct ?? "text/html; charset=utf-8") + "\r\nContent-Length: " + String(resp.utf8.count) + "\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n"
                conn.send(content: (h + resp).data(using: .utf8), completion: .contentProcessed { _ in conn.cancel() })
            }
        }
    }

    private func route(method: String, path: String, qp: [String: String], body: String, completion: @escaping (String, String?) -> Void) {
        switch path {
        case "/": completion(WebGUI.html, nil)

        case "/status": completion(json(SysMonitor.info()), "application/json")

        case "/ai/status":
            completion(json(AIManager.shared.status()), "application/json")

        case "/ai/provider":
            if method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let p = j["provider"] as? String {
                AIManager.shared.setProvider(p); completion("{\"ok\":true}", "application/json")
            } else { completion("{\"error\":\"bad\"}", "application/json") }

        case "/ai/alice-plus":
            if method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let on = j["enabled"] as? Bool {
                AIManager.shared.enableAlicePlus(on); completion(json(["alice_plus": AIManager.shared.alicePlusEnabled]), "application/json")
            } else { completion("{\"error\":\"bad\"}", "application/json") }

        case "/chat":
            guard method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any] else {
                completion("{\"error\":\"bad json\"}", "application/json"); return
            }
            let msg = j["message"] as? String ?? ""
            let provider = j["provider"] as? String ?? AIManager.shared.activeProvider
            let history = j["history"] as? [[String: String]] ?? []
            let useAlice = AIManager.shared.alicePlusEnabled && (provider == "auto" || provider == "yandex")
            if useAlice {
                YandexAuth.shared.chat(message: msg, history: history) { r, e in
                    completion(json(["response": r ?? ("Error: " + (e ?? "")), "provider": "alice-plus"]), "application/json")
                }
            } else {
                Task {
                    do {
                        let (r, p) = try await AIRouter.shared.chat(message: msg, provider: provider, history: history)
                        completion(json(["response": r, "provider": p]), "application/json")
                    } catch { completion(json(["response": "Error: " + error.localizedDescription, "provider": "none"]), "application/json") }
                }
            }

        case "/selfcoder/analyze":
            let root = Settings.shared.projectRoot.isEmpty ? FileManager.default.currentDirectoryPath : Settings.shared.projectRoot
            completion(json(SelfCoder.shared.analyzeSelf(projectRoot: root)), "application/json")

        case "/selfcoder/suggest":
            let root = Settings.shared.projectRoot.isEmpty ? FileManager.default.currentDirectoryPath : Settings.shared.projectRoot
            Task {
                do { let r = try await SelfCoder.shared.suggestImprovements(projectRoot: root); completion(json(["suggestions": r]), "application/json") }
                catch { completion(json(["error": error.localizedDescription]), "application/json") }
            }

        case "/selfcoder/generate":
            guard method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let desc = j["description"] as? String else {
                completion("{\"error\":\"need description\"}", "application/json"); return
            }
            let root = Settings.shared.projectRoot.isEmpty ? FileManager.default.currentDirectoryPath : Settings.shared.projectRoot
            Task {
                do { let r = try await SelfCoder.shared.generateFile(projectRoot: root, description: desc); completion(json(r), "application/json") }
                catch { completion(json(["error": error.localizedDescription]), "application/json") }
            }

        case "/selfcoder/build":
            let root = Settings.shared.projectRoot.isEmpty ? FileManager.default.currentDirectoryPath : Settings.shared.projectRoot
            Task {
                do { let r = try await SelfCoder.shared.buildAndFix(projectRoot: root); completion(json(r), "application/json") }
                catch { completion(json(["error": error.localizedDescription]), "application/json") }
            }

        case "/learner/learn":
            guard method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let url = j["url"] as? String else {
                completion("{\"error\":\"need url\"}", "application/json"); return
            }
            Task {
                do { let r = try await WebLearner.shared.learn(from: url); completion(json(r), "application/json") }
                catch { completion(json(["error": error.localizedDescription]), "application/json") }
            }

        case "/learner/learn-all":
            guard method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let urls = j["urls"] as? [String] else {
                completion("{\"error\":\"need urls\"}", "application/json"); return
            }
            Task {
                do { let r = try await WebLearner.shared.learnFromURLs(urls); completion(json(r), "application/json") }
                catch { completion(json(["error": error.localizedDescription]), "application/json") }
            }

        case "/learner/kb": completion(json(WebLearner.shared.knowledgeBase()), "application/json")

        case "/learner/search":
            guard method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let q = j["query"] as? String else {
                completion("{\"error\":\"need query\"}", "application/json"); return
            }
            Task {
                do { let r = try await WebLearner.shared.searchKnowledge(q); completion(json(["answer": r]), "application/json") }
                catch { completion(json(["error": error.localizedDescription]), "application/json") }
            }

        case "/files/check":
            completion(json(FileChecker.shared.status()), "application/json")

        case "/files/fix":
            if method == "POST", let bd = body.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: bd) as? [String: Any], let id = j["id"] as? Int {
                completion(json(["success": FileChecker.shared.fixIssue(id: id)]), "application/json")
            } else { completion("{\"error\":\"need id\"}", "application/json") }

        case "/files/fixall": completion(json(FileChecker.shared.fixAll()), "application/json")

        case "/files/fixai":
            let root = Settings.shared.projectRoot.isEmpty ? FileManager.default.currentDirectoryPath : Settings.shared.projectRoot
            completion(json(CodeFixer.shared.fixAllWithAI(projectRoot: root)), "application/json")

        case "/auth/yandex":
            if let u = YandexAuth.shared.authURL() { completion(json(["authUrl": u]), "application/json") }
            else { completion("{\"error\":\"no client_id\"}", "application/json") }

        case "/auth/callback":
            if let code = qp["code"] {
                YandexAuth.shared.exchangeCode(code) { ok, err in
                    let html = ok ? "<h2>OK!</h2><script>setTimeout(()=>window.close(),2000)</script>" : "<h2>Error: 

