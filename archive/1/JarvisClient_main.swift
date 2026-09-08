import Foundation
import Network
import SwiftUI
import AppKit

@main
struct JarvisClientApp: App {
    var body: some Scene {
        WindowGroup {
            JarvisChatView().frame(minWidth: 400, minHeight: 500)
        }
    }
}

final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMsg] = []
    @Published var textInput = ""
    @Published var connected = false
    private var conn: NWConnection?

    func connect() {
        let ep = NWEndpoint.hostPort(
            host: NWEndpoint.Host("127.0.0.1"),
            port: NWEndpoint.Port(rawValue: 7777) ?? 7777
        )
        conn = NWConnection(to: ep, using: .tcp)
        conn?.stateUpdateHandler = { [weak self] state in
            switch state {
            case .ready:
                DispatchQueue.main.async { self?.connected = true }
                self?.receive()
            case .failed, .cancelled:
                DispatchQueue.main.async { self?.connected = false }
            default:
                break
            }
        }
        conn?.start(queue: .main)
    }

    func receive() {
        guard let c = conn else { return }
        c.receive(minimumIncompleteLength: 1, maximumLength: 65536) { [weak self] data, context, isComplete, error in
            if error != nil { return }
            if let data = data, !data.isEmpty,
               let msg = try? JSONDecoder().decode(JarvisMessage.self, from: data),
               let t = msg.text {
                DispatchQueue.main.async {
                    self?.messages.append(ChatMsg(role: "JARVIS", text: t))
                }
            }
            self?.receive()
        }
    }

    func sendCmd(_ cmd: String) {
        let c = cmd.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !c.isEmpty, let cn = conn else { return }
        let m = JarvisMessage(type: "clientCommand", text: c, source: "user")
        if let d = try? JSONEncoder().encode(m) {
            cn.send(content: d, completion: .contentProcessed { _ in })
        }
        messages.append(ChatMsg(role: "You", text: c))
        textInput = ""
    }
}

struct JarvisChatView: View {
    @StateObject var vm = ChatViewModel()

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("JARVIS").font(.title2).bold()
                Spacer()
                HStack(spacing: 6) {
                    Circle().fill(vm.connected ? Color.green : Color.gray).frame(width: 8, height: 8)
                    Text(vm.connected ? "Connected" : "Offline")
                        .font(.caption).foregroundColor(.secondary)
                }
            }.padding()

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(vm.messages) { m in
                        HStack(alignment: .top, spacing: 8) {
                            Circle().fill(m.color).frame(width: 8, height: 8).padding(.top, 4)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(m.role).font(.caption2).foregroundColor(.secondary)
                                Text(m.text).font(.body)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer()
                        }
                    }
                }.padding()
            }

            Divider()
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    qBtn("Status", "status")
                    qBtn("Boss GX-10", "boss")
                    qBtn("Wiring", "wiring")
                    qBtn("Help", "help")
                    qBtn("Ping", "ping")
                }.padding(.horizontal).padding(.vertical, 6)
            }
            Divider()

            HStack(spacing: 8) {
                TextField("Command...", text: $vm.textInput)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .onSubmit { vm.sendCmd(vm.textInput) }
                Button(action: { vm.sendCmd(vm.textInput) }) {
                    Image(systemName: "paperplane.fill")
                }
                .buttonStyle(.bordered)
                .disabled(vm.textInput.isEmpty)
            }.padding()
        }
        .onAppear { vm.connect() }
    }

    func qBtn(_ label: String, _ cmd: String) -> some View {
        Button(label) { vm.sendCmd(cmd) }
            .buttonStyle(.bordered)
            .controlSize(.small)
    }
}

struct ChatMsg: Identifiable {
    let id = UUID()
    let role: String
    let text: String
    var color: Color { role == "You" ? .blue : .green }
}
