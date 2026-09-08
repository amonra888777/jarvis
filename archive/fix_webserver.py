import os

path = os.path.expanduser("~/Projects/JARVIS-SuperServer/Sources/JarvisServer/WebServer.swift")

code = r'''import Foundation
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
            Logger.shared.write("WebServer started on port 

