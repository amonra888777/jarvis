import Foundation

public struct JarvisMessage: Codable {
    public let type: String
    public let text: String?
    public let source: String
    public init(type: String, text: String? = nil, source: String) {
        self.type = type
        self.text = text
        self.source = source
    }
}
