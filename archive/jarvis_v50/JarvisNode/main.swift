import Foundation
import Network

class JarvisNode {
    let host: String
    let port: UInt16
    let threads: Int
    let nodeId: String
    var conn: NWConnection?
    var running = true

    init(host: String, port: UInt16, threads: Int) {
        self.host = host
        self.port = port
        self.threads = threads
        self.nodeId = "node-" + String(UUID().uuidString.prefix(8))
    }

    func run() {
        connect()
        startLoad()
        startHeartbeat()
        RunLoop.main.run()
    }

    private func connect() {
        let endpoint = NWEndpoint.hostPort(host: NWEndpoint.Host(host), port: NWEndpoint.Port(rawValue: port) ?? 7777)
        conn = NWConnection(to: endpoint, using: .tcp)
        conn?.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                print("Node connected to \(self?.host ?? "")")
                self?.receive()
            case .failed, .cancelled:
                print("Reconnecting in 5s...")
                self?.conn = nil
                DispatchQueue.global().asyncAfter(deadline: .now() + 5) { self?.connect() }
            default:
                break
            }
        }
        conn?.start(queue: .global())
    }

    private func startLoad() {
        for _ in 0..<threads {
            DispatchQueue.global().async {
                var h: UInt64 = 0
                while self.running {
                    for _ in 0..<100000 {
                        h ^= h << 13
                        h ^= h >> 7
                        h ^= h << 17
                    }
                    usleep(1000)
                }
            }
        }
        print("\(self.threads) crunch threads started")
    }

    private func startHeartbeat() {
        DispatchQueue.global().async {
            while self.running {
                sleep(30)
                self.beat()
            }
        }
    }

    private func beat() {
        guard let c = conn else { return }
        let cpu = String(format: "%.2f", Double.random(in: 0.1...0.9))
        let payload = "\(nodeId)|\(cpu)|\(threads)"
        let msg = JarvisMessage(type: "nodeHeartbeat", text: payload, source: nodeId)
        if let d = try? JSONEncoder().encode(msg) {
            c.send(content: d, completion: .contentProcessed { _ in })
            print("Heartbeat sent")
        }
    }

    private func receive() {
        guard let c = conn else { return }
        c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, context, isComplete, error in
            if let error = error { return }
            if let data = data, !data.isEmpty {
                if let msg = try? JSONDecoder().decode(JarvisMessage.self, from: data) {
                    print("Server: \(msg.text ?? msg.type)")
                }
            }
            self?.receive()
        }
    }
}

var host = "127.0.0.1"
var port: UInt16 = 7777
var threads = 8

for arg in CommandLine.arguments.dropFirst() {
    if arg.hasPrefix("--host=") { host = String(arg.dropFirst(7)) }
    else if arg.hasPrefix("--port=") { port = UInt16(String(arg.dropFirst(7))) ?? 7777 }
    else if arg.hasPrefix("--threads=") { threads = Int(String(arg.dropFirst(10))) ?? 8 }
}

print("JarvisNode: host=\(host) port=\(port) threads=\(threads)")
let node = JarvisNode(host: host, port: port, threads: threads)
node.run()
