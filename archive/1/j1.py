import os
b=os.path.expanduser("~/Projects/JARVIS-SuperServer")
src=os.path.join(b,"Sources/JarvisServer")
os.makedirs(src,exist_ok=True)
def w(n,c):
    open(os.path.join(src,n),"w").write(c)
    print("  "+n+": "+str(len(c)))
open(os.path.join(b,"Package.swift"),"w").write('// swift-tools-version:5.9\nimport PackageDescription\nlet package=Package(name:"JARVIS-SuperServer",targets:[.executableTarget(name:"JarvisServer",path:"Sources/JarvisServer")])\n')
print("Package.swift")

w("Logger.swift",r'''import Foundation
final class Logger {
    static let shared = Logger()
    private let logFile: String
    private let q = DispatchQueue(label: "jarvis.log")
    init() { logFile = (NSTemporaryDirectory() as NSString).appendingPathComponent("jarvis.log") }
    func write(_ m: String) {
        let ts = DateFormatter.localizedString(from: Date(), dateStyle: .short, timeStyle: .medium)
        let line = "[\(ts)] \(m)"
        print(line)
        q.async { [logFile] in
            let old = (try? String(contentsOfFile: logFile)) ?? ""
            try? (old + line + "\n").write(toFile: logFile, atomically: true, encoding: .utf8)
        }
    }
    func recentLines(_ n: Int) -> String {
        ((try? String(contentsOfFile: logFile)) ?? "").components(separatedBy: "\n").suffix(n).joined(separator: "\n")
    }
}
''')

w("Settings.swift",r'''import Foundation
final class Settings {
    static let shared = Settings()
    private let f: String
    private(set) var dict: [String: String] = [:]
    init() { f = (FileManager.default.homeDirectoryForCurrentUser.path as NSString).appendingPathComponent(".jarvis_settings.json"); load() }
    func load() { if let d = try? Data(contentsOf: URL(fileURLWithPath: f)), let j = try? JSONSerialization.jsonObject(with: d) as? [String: String] { dict = j } }
    func save() { if let d = try? JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted) { try? d.write(to: URL(fileURLWithPath: f)) } }
    func get(_ k: String) -> String { dict[k] ?? "" }
    func set(_ k: String, _ v: String) { dict[k] = v; save() }
    var yandexClientId: String { get("yandex_client_id") }
    var yandexFolderId: String { get("yandex_folder_id") }
    var projectRoot: String { get("project_root") }
    var ollamaModel: String { get("ollama_model") }
    func toDict() -> [String: Any] { ["yandex_client_id": yandexClientId, "yandex_folder_id": yandexFolderId, "project_root": projectRoot, "ollama_model": ollamaModel] }
}
''')

w("Config.swift",r'''import Foundation
final class Config { static let shared = Config(); func load() {} }
''')

w("SysMonitor.swift",r'''import Foundation
struct SysMonitor {
    static func info() -> [String: Any] {
        var cpu: Double = 0
        var load = host_cpu_load_info()
        var size = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info_data_t>.size / MemoryLayout<integer_t>.size)
        if host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, host_info_t(&load), &size) == KERN_SUCCESS {
            let t = Double(load.cpu_ticks.0 + load.cpu_ticks.1 + load.cpu_ticks.2 + load.cpu_ticks.3)
            if t > 0 { cpu = Double(load.cpu_ticks.0 + load.cpu_ticks.1 + load.cpu_ticks.2) / t * 100 }
        }
        return ["cpu": String(format: "%.1f%%", cpu), "cores": ProcessInfo.processInfo.activeProcessorCount, "uptime": Int(ProcessInfo.processInfo.systemUptime)]
    }
}
''')

w("MetalEngine.swift",r'''import Foundation
import Metal
final class MetalEngine {
    static let shared = MetalEngine()
    init() {
        guard let dev = MTLCreateSystemDefaultDevice() else { return }
        if let lib = try? dev.makeDefaultLibrary(bundle: Bundle.main), let fn = lib.makeFunction(name: "jarvis_compute") {
            _ = try? dev.makeComputePipelineState(function: fn)
            Logger.shared.write("Metal: OK")
        }
    }
}
''')

w("MidiController.swift",r'''import Foundation
import CoreMIDI
final class MidiController {
    static let shared = MidiController()
    private var client: MIDIClientRef?
    private var port: MIDIPortRef?
    func setup() {
        var s = MIDIClientCreate("JARVIS" as CFString, nil, nil, &client)
        guard s == noErr else { Logger.shared.write("MIDI: fail"); return }
        s = MIDIOutputPortCreate(client, "Out" as CFString, &port)
        Logger.shared.write(s == noErr ? "MIDI: OK, \(MIDIGetNumberOfDestinations()) dest" : "MIDI: port fail")
    }
}
''')

w("FileChecker.swift",r'''import Foundation
final class FileChecker {
    static let shared = FileChecker()
    private var root: String = ""
    private(set) var issues: [Issue] = []
    struct Issue: Codable { let id: Int; let file: String; let line: Int; let severity: String; let message: String; let suggestion: String? }
    func setup(projectRoot: String) { root = projectRoot; scan() }
    @discardableResult
    func scan() -> [Issue] {
        var found: [Issue] = []
        guard let en = FileManager.default.enumerator(atPath: root) else { issues = []; return [] }
        var id = 0
        while let file = en.nextObject() as? String {
            guard file.hasSuffix(".swift"), !file.contains(".build"), !file.contains(".git") else { continue }
            let fp = (root as NSString).appendingPathComponent(file)
            guard let c = try? String(contentsOfFile: fp) else { continue }
            let lines = c.components(separatedBy: "\n")
            if (c.contains("JSON") || c.contains("String(data:")) && !c.contains("import Foundation") { found.append(Issue(id: id, file: file, line: 1, severity: "warning", message: "Missing import Foundation", suggestion: "import Foundation")); id += 1 }
            if c.contains("NW") && !c.contains("import Network") { found.append(Issue(id: id, file: file, line: 1, severity: "warning", message: "Missing import Network", suggestion: "import Network")); id += 1 }
            for (i, line) in lines.enumerated() {
                let t = line.trimmingCharacters(in: .whitespaces)
                if t.contains("TODO") || t.contains("FIXME") { found.append(Issue(id: id, file: file, line: i+1, severity: "info", message: "TODO: \(t)", suggestion: nil)); id += 1 }
                if !t.hasPrefix("//") && t.contains("!.") && !t.contains("if ") && !t.contains("guard ") && !t.contains("!= ") { found.append(Issue(id: id, file: file, line: i+1, severity: "warning", message: "Force unwrap: \(t)", suggestion: "Use if let / guard let")); id += 1 }
                if t.contains("print(") && !t.hasPrefix("//") && !file.contains("Logger.swift") { found.append(Issue(id: id, file: file, line: i+1, severity: "info", message: "print() instead of Logger", suggestion: "Logger.shared.write()")); id += 1 }
            }
        }
        issues = found
        Logger.shared.write("FileChecker: \(found.count) issues")
        return found
    }
    func status() -> [String: Any] {
        return ["total": issues.count, "warnings": issues.filter { $0.severity == "warning" }.count, "infos": issues.filter { $0.severity == "info" }.count, "issues": issues.map { ["id": $0.id, "file": $0.file, "line": $0.line, "severity": $0.severity, "message": $0.message, "suggestion": $0.suggestion ?? ""] }]
    }
    func fixIssue(id: Int) -> Bool {
        guard id >= 0, id < issues.count, let s = issues[id].suggestion else { return false }
        let issue = issues[id]
        let fp = (root as NSString).appendingPathComponent(issue.file)
        guard let c = try? String(contentsOfFile: fp) else { return false }
        var lines = c.components(separatedBy: "\n")
        if s.hasPrefix("import ") { if !lines.contains(where: { $0.trimmingCharacters(in: .whitespaces) == s }) { lines.insert(s, at: 0) } }
        else if s.contains("Logger") && issue.message.contains("print") { if issue.line - 1 < lines.count { lines[issue.line - 1] = lines[issue.line - 1].replacingOccurrences(of: "print(", with: "Logger.shared.write(") } }
        else { return CodeFixer.shared.fixWithAI(issue: issue, projectRoot: root) }
        do { try lines.joined(separator: "\n").write(toFile: fp, atomically: true, encoding: .utf8); scan(); return true } catch { return false }
    }
    func fixAll() -> [String: Any] { let f = issues.filter { $0.suggestion != nil }; var fix = 0, fail = 0; for i in f { if fixIssue(id: i.id) { fix += 1 } else { fail += 1 } }; return ["fixed": fix, "failed": fail, "total": f.count] }
}
''')

w("OllamaManager.swift",r'''import Foundation
final class OllamaManager {
    static let shared = OllamaManager()
    private var process: Process?
    private(set) var isRunning = false
    private(set) var binaryPath: String?
    var ollamaURL: String { "http://127.0.0.1:11434" }
    func setup() {
        if let p = Bundle.main.path(forResource: "ollama", ofType: nil) { binaryPath = p; startProcess() }
        else if let s = findSystem() { binaryPath = s; checkRunning() }
        else { Logger.shared.write("OllamaManager: not found") }
    }
    private func findSystem() -> String? {
        let t = Process(); t.launchPath = "/usr/bin/which"; t.arguments = ["ollama"]
        let p = Pipe(); t.standardOutput = p
        do { try t.run(); t.waitUntilExit(); let s = String(data: p.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines); return s?.isEmpty == false ? s : nil } catch { return nil }
    }
    private func startProcess() {
        guard let path = binaryPath else { return }
        process = Process(); process?.launchPath = path; process?.arguments = ["serve"]
        do { try process?.run(); isRunning = true; Logger.shared.write("OllamaManager: started") } catch { Logger.shared.write("OllamaManager: error") }
    }
    private func checkRunning() {
        guard let u = URL(string: ollamaURL + "/api/tags") else { return }
        URLSession.shared.dataTask(with: u) { [weak self] _, r, _ in
            if let r = r as? HTTPURLResponse, r.statusCode == 200 { self?.isRunning = true; Logger.shared.write("OllamaManager: running") } else { self?.startProcess() }
        }.resume()
    }
    func status() -> [String: Any] { ["running": isRunning, "bundled": Bundle.main.path(forResource: "ollama", ofType: nil) != nil, "path": binaryPath ?? "", "url": ollamaURL] }
}
''')

w("AIRouter.swift",r'''import Foundation
struct AIConfig {
    static var ollamaURL: String { OllamaManager.shared.ollamaURL + "/api/chat" }
    static let ollamaModel = "qwen3:0.6b"
    static let gigaAuthKey = ""
    static let gigaScope = "GIGACHAT_API_PERS"
    static let gigaBaseURL = "https://api.giga.chat"
    static let gigaOAuthURL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    static let gigaModel = "GigaChat-2-Pro"
    static let openaiAPIKey = ""
    static let openaiURL = "https://api.openai.com/v1/chat/completions"
    static let openaiModel = "gpt-4o-mini"
}
class AIRouter {
    static let shared = AIRouter()
    private var gigaToken: String?
    private var gigaTokenExpiry: Date?
    func status() -> [String: [String: Any]] { ["ollama": ["available": OllamaManager.shared.isRunning, "name": "Ollama"], "yandex": ["available": YandexAuth.shared.isAuthorized, "name": "YandexGPT"], "giga": ["available": !AIConfig.gigaAuthKey.isEmpty, "name": "GigaChat"], "openai": ["available": !AIConfig.openaiAPIKey.isEmpty, "name": "OpenAI"]] }
    func chat(message: String, provider: String, history: [[String: String]]) async throws -> (response: String, provider: String) {
        let ps = provider == "auto" ? ["ollama", "yandex", "giga", "openai"] : [provider]
        var lastErr: Error?
        for p in ps { do { let r = try await call(p, message: message, history: history); return (r, p) } catch { lastErr = error } }
        throw lastErr ?? NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "No AI"])
    }
    private func call(_ p: String, message: String, history: [[String: String]]) async throws -> String {
        switch p {
        case "ollama": return try await callOllama(message: message, history: history)
        case "yandex": return try await callYandex(message: message, history: history)
        case "giga": return try await callGiga(message: message, history: history)
        case "openai": return try await callOpenAI(message: message, history: history)
        default: throw NSError(domain: "AIRouter", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unknown"])
        }
    }
    private func callOllama(message: String, history: [[String: String]]) async throws -> String {
        var msgs: [[String: String]] = [["role": "system", "content": "You are JARVIS. Answer in Russian, concise."]]
        for m in history { msgs.append(["role": m["role"] ?? "user", "content": m["content"] ?? ""]) }
        msgs.append(["role": "user", "content": message])
        let body: [String: Any] = ["model": AIConfig.ollamaModel, "messages": ms

