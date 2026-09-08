import Foundation
import Network

struct JarvisMessage: Codable {
    let type: String
    let text: String?
    let source: String
}

@main
struct JarvisGUIApp {
    static func main() {
        print("=== JARVIS GUI CLIENT v1.0 ===")
        print("Подключение к 127.0.0.1:7777...")
        let conn = NWConnection(to: .hostPort(host: "127.0.0.1", port: 7777), using: .tcp)
        conn.stateUpdateHandler = { state in
            switch state {
            case .ready:
                print("✅ Подключено к серверу!")
                print("Доступные команды: status, help, ping, boss, wiring, quit")
                print()
            case .failed:
                print("❌ Не удалось подключиться. Сначала запустите JarvisCore.")
                exit(1)
            default: break
            }
        }
        conn.start(queue: .main)
        sleep(2)
        while let input = readLine() {
            let cmd = input.trimmingCharacters(in: .whitespaces)
            if cmd.isEmpty { continue }
            if cmd == "quit" || cmd == "exit" { break }
            let msg = JarvisMessage(type: cmd, text: cmd, source: "user")
            if let d = try? JSONEncoder().encode(msg) {
                conn.send(content: d, completion: .contentProcessed { _ in })
            }
            sleep(1)
        }
        conn.cancel()
        print("Отключено.")
    }
}
