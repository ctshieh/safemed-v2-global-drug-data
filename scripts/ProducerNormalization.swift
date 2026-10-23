// Standalone Foundation normalization reference. Never imports or builds the App.
// Generated from pinned SafetyEngine.swift normalized block; execution not performed by reviewer.
import Foundation
func appNormalized(_ value: String) -> String {
        value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .components(separatedBy: CharacterSet.whitespacesAndNewlines.union(CharacterSet(charactersIn: "　,，、。/／()（）[]「」『』\"'`.-")))
            .joined()
    }
let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2])
let rows = try JSONSerialization.jsonObject(with: Data(contentsOf: inputURL)) as! [[String:String]]
let results = rows.map { row -> [String:String] in
 let input = row["input"]!
 let value = appNormalized(input)
 return ["input":input,"normalized":value,"normalized_grapheme_count":String(value.count),"normalized_utf8_hex":value.utf8.map { String(format:"%02x",$0) }.joined()]
}
try JSONSerialization.data(withJSONObject:results,options:[.sortedKeys,.withoutEscapingSlashes]).write(to:outputURL)
