import Foundation
import Network

struct JarvisMessage: Codable {
    let type: String
    let text: String?
    let source: String
}

final class JarvisServer {
    private var listener: NWListener?
    private var connections: [NWConnection] = []
    private var startTime: Date?

    var uptime: String {
        guard let s = startTime else { return "00:00:00" }
        let i = Int(Date().timeIntervalSince(s))
        return String(format: "%02d:%02d:%02d", i / 3600, (i % 3600) / 60, i % 60)
    }

    func start(port: UInt16 = 7777) {
        startTime = Date()
        guard let p = NWEndpoint.Port(rawValue: port) else { return }
        do {
            listener = try NWListener(using: .tcp, on: p)
        } catch {
            print("Error creating listener: \(error)")
            return
        }
        listener?.newConnectionHandler = { [weak self] c in self?.handle(c) }
        listener?.start(queue: .global())
        print("JarvisCore запущен на порту \(port)")
    }

    private func handle(_ c: NWConnection) {
        c.start(queue: .global())
        connections.append(c)
        receive(c)
    }

    private func receive(_ c: NWConnection) {
        c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] d, _, _, e in
            if let e = e { return }
            if let d = d, !d.isEmpty { self?.process(d, c) }
            self?.receive(c)
        }
    }

    private func process(_ data: Data, _ c: NWConnection) {
        guard let m = try? JSONDecoder().decode(JarvisMessage.self, from: data) else { return }
        var r = "OK"
        switch m.type.lowercased() {
        case "ping": r = "pong"
        case "status": r = "Core OK. Conns: \(connections.count). Up: \(uptime)"
        case "help": r = "status, help, ping, boss, wiring"
        case "boss": r = "Boss GX-10: Clean, Crunch, Lead. Online."
        case "wiring": r = "Humbucker: green=start, white=end, red=south, black=ground."
        default: r = m.text ?? "OK"
        }
        let resp = JarvisMessage(type: "response", text: r, source: "core")
        if let d = try? JSONEncoder().encode(resp) {
            c.send(content: d, completion: .contentProcessed { _ in })
        }
    }
}

@main
struct JarvisCoreApp {
    static func main() {
        let s = JarvisServer()
        s.start()
        print("Ctrl+C для остановки")
        while true { sleep(1) }
    }
}
