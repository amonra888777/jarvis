import Foundation
import Network

struct JarvisMessage: Codable {
    let type: String
    let text: String?
    let source: String
}

@main
struct JarvisNodeApp {
    static func main() {
        let id = "node-" + String(UUID().uuidString.prefix(8))
        print("JarvisNode \(id) запущен")
        let conn = NWConnection(to: .hostPort(host: "127.0.0.1", port: 7777), using: .tcp)
        conn.stateUpdateHandler = { state in
            switch state {
            case .ready: print("✅ Нода \(id) подключена к серверу")
            case .failed: print("❌ Нет сервера. Сначала запустите JarvisCore."); exit(1)
            default: break
            }
        }
        conn.start(queue: .global())
        sleep(2)
        var beat = 0
        while true {
            beat += 1
            let cpu = String(format: "%.2f", Double.random(in: 0.1...0.9))
            let payload = "\(id)|\(cpu)"
            let msg = JarvisMessage(type: "heartbeat", text: payload, source: id)
            if let d = try? JSONEncoder().encode(msg) {
                conn.send(content: d, completion: .contentProcessed { _ in })
            }
            print("  Beat #\(beat): CPU=\(cpu)")
            sleep(5)
        }
    }
}
