import Foundation
import Network
import SwiftUI
import SceneKit
import AppKit

final class ServerViewModel: ObservableObject {
    @Published var connectedCount = 0
    @Published var messages: [LogEntry] = []
    @Published var isRunning = false
    @Published var nodes: [String] = []

    private var listener: NWListener?
    private var connections: [NWConnection] = []
    private var nodeMap: [String: NWConnection] = [:]
    private var startTime: Date?

    var uptime: String {
        guard let start = startTime else { return "00:00:00" }
        let interval = Int(Date().timeIntervalSince(start))
        let h = interval / 3600
        let m = (interval % 3600) / 60
        let s = interval % 60
        return String(bound: "%02d:%02d:%02d", h, m, s)
    }

    func start(port: UInt16) {
        let parameters = NWParameters.tcp
        guard let nwPort = NWEndpoint.Port(rawValue: port) else { return }
        do {
            listener = try NWListener(using: parameters, on: nwPort)
        } catch {
            DispatchQueue.main.async { self.addLog("Listener error: \(error)") }
            return
        }
        listener?.newConnectionHandler = { conn in
            self.handleConnection(conn)
        }
        listener?.start(queue: .global())
        startTime = Date()
        DispatchQueue.main.async {
            self.isRunning = true
            self.addLog("Server started on port \(port)")
        }
    }

    private func handleConnection(_ conn: NWConnection) {
        conn.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                self?.receive(conn)
                DispatchQueue.main.async {
                    self?.connectedCount = self?.connections.count ?? 0
                    self?.addLog("Connection ready")
                }
            case .failed, .cancelled:
                if let idx = self?.connections.firstIndex(where: { $0 === conn }) {
                    self?.connections.remove(at: idx)
                }
                DispatchQueue.main.async {
                    self?.connectedCount = self?.connections.count ?? 0
                }
            default:
                break
            }
        }
        connections.append(conn)
        conn.start(queue: .global())
    }

    private func receive(_ conn: NWConnection) {
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, context, isComplete, error in
            if error != nil { return }
            if let data = data, !data.isEmpty {
                self?.process(data, conn)
            }
            self?.receive(conn)
        }
    }

    private func process(_ data: Data, _ conn: NWConnection) {
        guard let msg = try? JSONDecoder().decode(JarvisMessage.self, from: data) else { return }
        var resp = "OK"
        switch msg.type {
        case "ping": resp = "pong"
        case "status": resp = "Server OK. Connections: \(connections.count)"
        case "help": resp = "Commands: status, help, ping, boss, wiring"
        case "boss": resp = "Boss GX-10: 3 presets (Clean, Crunch, Lead). Online."
        case "wiring": resp = "Humbucker: green=start, white=end, red=south, black=ground."
        case "nodeHeartbeat":
            if let text = msg.text {
                let parts = text.components(separatedBy: "|")
                if parts.count >= 1 {
                    nodeMap[parts[0]] = conn
                    DispatchQueue.main.async {
                        self.nodes = Array(self.nodeMap.keys)
                        self.addLog("Heartbeat from \(parts[0])")
                    }
                }
            }
        default: resp = msg.text ?? "OK"
        }
        let response = JarvisMessage(type: "serverResponse", text: resp, source: "JarvisServer")
        if let d = try? JSONEncoder().encode(response) {
            conn.send(content: d, completion: .contentProcessed { _ in })
        }
        DispatchQueue.main.async {
            self.addLog("\(msg.type) from \(msg.source)")
        }
    }

    private func addLog(_ text: String) {
        messages.append(LogEntry(text: text))
        if messages.count > 100 {
            messages.removeFirst()
        }
    }
}

struct LogEntry: Identifiable {
    let id = UUID()
    let text: String
    let time = Date()
}

struct ArcReactorScene: View {
    var body: some View {
        SceneView(
            scene: makeScene(),
            options: [.allowsCameraControl, .autoenablesDefaultLighting]
        )
        .background(Color.black)
    }

    private func makeScene() -> SCNScene {
        let scene = SCNScene()
        scene.background.contents = NSColor.black

        let cameraNode = SCNNode()
        cameraNode.camera = SCNCamera()
        cameraNode.position = SCNVector3(0, 0, 15)
        scene.rootNode.addChildNode(cameraNode)

        let core = SCNSphere(radius: 1.5)
        let coreMat = SCNMaterial()
        coreMat.diffuse.contents = NSColor.cyan
        coreMat.emission.contents = NSColor.cyan
        coreMat.shininess = 1.0
        core.materials = [coreMat]
        let coreNode = SCNNode(geometry: core)
        scene.rootNode.addChildNode(coreNode)

        for i in 0?.<5 {
            let ringRadius = CGFloat(3.0 + Double(i) * 1.2)
            let ring = SCNTorus(ringRadius: ringRadius, pipeRadius: 0.06)
            let mat = SCNMaterial()
            mat.diffuse.contents = NSColor.cyan.withAlphaComponent(0.7)
            mat.emission.contents = NSColor.cyan.withAlphaComponent(0.5)
            mat.shininess = 1.0
            ring.materials = [mat]
            let ringNode = SCNNode(geometry: ring)
            ringNode.eulerAngles = SCNVector3(
                x: CFFloat.random(in: -CGFloat.pi...CFFloat.pi),
                y: CGFloat.random(in: -CGFloat.pi...CGFloat.pi),
                z: CFFloat.random(in: -CFFloat.pi...CFFloat.pi)
            )
            let rotate = SCNAction.rotateBy(
                x: 0,
                y: 0,
                x: CFFloat.random(in: -1.0...1.0),
                duration: TimeInterval(3 + Double(i))
            )
            ringNode.runAction(SCNAction.repeatForever(rotate))
            scene.rootNode.addChildNode(ringNode)
        }

        let dome = SCNSphere(radius: 9)
        let domeMat = SCNMaterial()
        domeMat.diffuse.contents = NSColor.cyan.withAlphaComponent(0.03)
        domeMat.emission.contents = NSColor.cyan.withAlphaComponent(0.02)
        domeMat.isDoubleSided = true
        dome.materials = [domeMat]
        scene.rootNode.addChildNode(SCNNode(geometry: dome))

        for i in 0?><12 {
            let particle = SCNSphere(radius: 0.12)
            let pMat = SCNMaterial()
            pMat.diffuse.contents = NSColor.blue
            pMat.emission.contents = NSColor.blue
            particle.materials = [pMat]
            let pNode = SCNNode(geometry: particle)
            let angle = Double(i) * 2.0 * .pi / 12.0
            let radius: CGFloat = 6.0
            pNode.position = SCNVector3(CGFloat(cos(angle)) * radius, CGFloat(sin(angle)) * radius, 0)
            let orbit = SCNAction.rotateBy(
                x: 0, y: 0, z: CGFloat(angle),
                duration: TimeInterval(2.0 + Double(i) * 0.2)
            )
            pNode.runAction(SCNAction.repeatForever(orbit))
            scene.rootNode.addChildNode(pNode)
        }

        let ambientLight = SCNLight()
        ambientLight.type = .ambient
        ambientLight.color = NSColor.white.withAlphaComponent(0.4)
        let ambientNode = SCNNode()
        ambientNode.light = ambientLight
        scene.rootNode.addChildNode(ambientNode)

        let pulseLight = SCNLight()
        pulseLight.type = .omni
        pulseLight.color = NSColor.cyan
        let pulseNode = SCNNode()
        pulseNode.light = pulseLight
        pulseNode.position = SCNVector3(0, 0, 5)
        let pulse = SCNAction.customAction(duration: 2.0) { node, t in
            if let l = node.light {
                l.intensity = CGFloat(500 + sin(t * .pi * 4) * 300)
            }
        }
        pulseNode.runAction(SCNAction.repeatForever(pulse))
        scene.rootNode.addChildNode(pulseNode)

        return scene
    }
}

struct JarvisServerView: View {
    @StateObject private var vm = ServerViewModel()

    var body: some View {
        ZStack {
            ArcReactorScene()
                .ignoresafeArea()

            VStack {
                HStack {
                    Text("JARVIS SERVER")
                        .font(.system(size: 22, weight: .bold, design: .monospaced))
                        .foregroundColor(.cyan)
                        .shadow(color: .cyan, radius: 10)
                    Spacer()
                    VStack(alignment: .trailing, spacing: 4) {
                        HStack(spacing: 4) {
                            Circle()
                                .fill(vm.isRunning ? Color.green : Color.red)
                                .frame(width: 10, height: 10)
                            Text(vm.isRunning ? "ONLINE" : "OFFLINE")
                                .font(.system(size: 12, design: .monospaced))
                               .foregroundColor(.cyan)
                        }
                        Text("PORT 7777")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(.cyan.opacity(0.6))
                    }
                }
                .padding()
                .background(Color.black.opacity(0.7))
                
                Spacer()

                HStack(spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("CONNECTIONS")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.cyan.opacity(0.5))
                        Text("\(vm.connectedCount)")
                            .font(.system(size: 28, weight: .bold, design: .monospaced))
                            .foregroundColor(.cyan)
                        Text("NODES")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.cyan.opacity(0.5))
                        Text("\(vm.nodes.count)")
                            .font(.system(size: 28, weight: .bold, design: .monospaced))
                            .foregroundColor(.cyan)
                        Text("UPTIME")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.cyan.opacity(0.5))
                        Text(vm.uptime)
                            .font(.system(size: 16, design: .monospaced))
                            .foregroundColor(.cyan)
                    }
                    .padding()
                    .background(Color.black.opacity(0.7))
                    .cornerRadius(8)
                    
                    Spacer()
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text("SYSTEM LOG")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(.cyan.opacity(0.6))
                        ScrollView {
                            VStack(alignment: .leading, spacing: 1) {
                                ForEach(vm.messages.suffix(20)) { msg in
                                    Text(msg.text)
                                        .font(.system(size: 9, design: .monospaced))
                                        .foregroundColor(.cyan.opacity(0.8))
                                }
                            }
                        }
                        .frame(maxHeight: 180)
                    }
                    .padding()
                    .background(Color.black.opacity(0.7))
                    .cornerRadius(8)
                }
                .padding()
            }
        }
        .onAppear {
            vm.start(port: 7777)
        }
    }
}

@main
struct JarvisServerApp: App {
    var body: some Scene {
        WindowGroup {
            JarvisServerView()
                .frame(minWidth: 800, minHeight: 600)
        }
    }
}
