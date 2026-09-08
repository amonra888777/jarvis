import os

path = os.path.expanduser("~/Projects/JARVIS-SuperServer/Sources/JarvisServer/WebServer.swift")

code = """\
import Foundation
import Network

final class WebServer {
    static let shared = WebServer()
    private var listener: NWListener?

    func start(port: UInt16 = 3000) {
        do {
            listener = try NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: port)!)
            listener?.newConnectionHandler = { [weak self] conn in
                self?.handle(conn: conn)
            }
            listener?.start(queue: .global(qos: .userInitiated))
            Logger.shared.write("WebServer started on port \\(port)")
        } catch {
            Logger.shared.write("WebServer error: \\(error.localizedDescription)")
        }
    }

    private func handle(conn: NWConnection) {
        conn.start(queue: .global())
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, _, _, _ in
            guard let data = data, let req = String(data: data, encoding: .utf8) else {
                conn.cancel()
                return
            }
            let lines = req.components(separatedBy: "\\r\\n")
            guard let firstLine = lines.first else { conn.cancel(); return }
            let parts = firstLine.components(separatedBy: " ")
            guard parts.count >= 2 else { conn.cancel(); return }
            let method = parts[0]
            let rawPath = parts[1]
            let cleanPath = rawPath.components(separatedBy: "?").first ?? rawPath
            let bodyComponents = req.components(separatedBy: "\\r\\n\\r\\n")
            let bodyStr = bodyComponents.count > 1 ? bodyComponents[1] : ""

            self?.route(method: method, path: cleanPath, body: bodyStr) { response, contentType in
                let ct = contentType ?? "text/html; charset=utf-8"
                let http = "HTTP/1.1 200 OK\\r\\nContent-Type: \\(ct)\\r\\nContent-Length: \\(response.utf8.count)\\r\\nAccess-Control-Allow-Origin: *\\r\\nConnection: close\\r\\n\\r\\n\\(response)"
                conn.send(content: http.data(using: .utf8), completion: .contentProcessed { _ in conn.cancel() })
            }
        }
    }

    private func route(method: String, path: String, body: String, completion: @escaping (String, String?) -> Void) {
        switch path {
        case "/":
            if let p = Bundle.module.path(forResource: "index", ofType: "html"),
               let s = try? String(contentsOfFile: p) {
                completion(s, "text/html; charset=utf-8")
            } else {
                completion("<h1>JARVIS SuperServer</h1>", "text/html")
            }

        case "/status", "/api/status":
            let info = SysMonitor.info()
            if let d = try? JSONSerialization.data(withJSONObject: info),
               let s = String(data: d, encoding: .utf8) {
                completion(s, "application/json")
            } else {
                completion("{}", "application/json")
            }

        case "/ai/status":
            let status = AIRouter.shared.status()
            if let d = try? JSONSerialization.data(withJSONObject: status),
               let s = String(data: d, encoding: .utf8) {
                completion(s, "application/json")
            } else {
                completion("{}", "application/json")
            }

        case "/chat":
            guard method == "POST" else {
                completion("{\"error\":\"POST required\"}", "application/json")
                return
            }
            guard let bodyData = body.data(using: .utf8),
                  let json = try? JSONSerialization.jsonObject(with: bodyData) as? [String: Any] else {
                completion("{\"error\":\"Invalid JSON\"}", "application/json")
                return
            }
            let message = json["message"] as? String ?? ""
            let provider = json["provider"] as? String ?? "auto"
            let history = json["history"] as? [[String: String]] ?? []

            Logger.shared.write("Chat request: provider=\\(provider), message=\\(message.prefix(50))")

            Task {
                do {
                    let (response, usedProvider) = try await AIRouter.shared.chat(
                        message: message, provider: provider, history: history
                    )
                    Logger.shared.write("Chat response via \\(usedProvider): \\(response.prefix(80))")
                    let result: [String: Any] = ["response": response, "provider": usedProvider]
                    if let d = try? JSONSerialization.data(withJSONObject: result),
                       let s = String(data: d, encoding: .utf8) {
                        completion(s, "application/json")
                    } else {
                        completion("{\"response\":\"Encoding error\"}", "application/json")
                    }
                } catch {
                    Logger.shared.write("Chat error: \\(error.localizedDescription)")
                    let fallback: [String: Any] = ["response": "Ошибка: \\(error.localizedDescription)", "provider": "none"]
                    if let d = try? JSONSerialization.data(withJSONObject: fallback),
                       let s = String(data: d, encoding: .utf8) {
                        completion(s, "application/json")
                    } else {
                        completion("{\"response\":\"Unknown error\"}", "application/json")
                    }
                }
            }

        default:
            completion("{\"error\":\"Not Found\"}", "application/json")
        }
    }
}
"""

with open(path, "w") as f:
    f.write(code)

print(f"OK: WebServer.swift written to {path}")
print(f"Size: {len(code)} bytes")

