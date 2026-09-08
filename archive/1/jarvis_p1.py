import os
b = os.path.expanduser("~/Projects/JARVIS-SuperServer/Sources/JarvisServer")
os.makedirs(b, exist_ok=True)
def w(name, code):
    with open(os.path.join(b, name), "w") as f:
        f.write(code)
    print("OK:", name, len(code), "bytes")

w("Logger.swift", r'''import Foundation
final class Logger {
    static let shared = Logger()
    private let logFile: String
    private let q = DispatchQueue(label: "jarvis.log")
    init() { logFile = (NSTemporaryDirectory() as NSString).appendingPathComponent("jarvis.log") }
    func write(_ m: String) {
        let ts = DateFormatter.localizedString(from: Date(), dateStyle: .short, timeStyle: .medium)
        let line = "[

