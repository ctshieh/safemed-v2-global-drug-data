import Foundation
import CryptoKit

@main
struct TestSignedManifest {
    static func main() throws {
        let key = Curve25519.Signing.PrivateKey()
        let id = "TEST_ONLY_EPHEMERAL"
        let verifier = DataPackageSignatureVerifier(trustedKeys: [id: key.publicKey.rawRepresentation])
        var object: [String: Any] = [
            "schema_version": "safemed-mobile-safety-v2.1", "package_major_version": 2,
            "product_line": "safemed_pro", "license_tier": "professional", "requires_entitlement": true,
            "compatible_app_major_versions": [2], "version": "test-é-藥-😀-\\-\"",
            "created_at": "2026-10-26T00:00:00Z", "package_url": "https://example.invalid/data/a.gz?x=1&y=2",
            "package_format": "sqlite3+gzip", "gzip_bytes": 466838543, "sqlite_bytes": Int64(2360496128),
            "gzip_sha256": String(repeating: "a", count: 64), "sqlite_sha256": String(repeating: "b", count: 64),
            "sha256": NSNull(), "signature_algorithm": DataPackageSignatureVerifier.algorithm,
            "signature_key_id": id, "signature": ""]
        func encode(_ x: [String: Any]) throws -> Data { try JSONSerialization.data(withJSONObject: x, options: [.sortedKeys, .withoutEscapingSlashes]) }
        let typed = try JSONDecoder().decode(SignedDataPackageManifest.self, from: encode(object))
        let canonical = try typed.canonicalSigningPayload()
        precondition(!canonical.isEmpty && canonical.last != 10)
        precondition(String(decoding: canonical, as: UTF8.self).contains("\"sha256\":null"))
        object["signature"] = try key.signature(for: canonical).base64EncodedString()
        _ = try verifier.verify(manifestData: encode(object))
        _ = try verifier.verify(manifestData: JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted]))
        var rejected = 0
        for (field, value) in [("package_url", "https://example.invalid/wrong.gz" as Any),
            ("gzip_bytes", 1), ("sqlite_bytes", 1), ("gzip_sha256", String(repeating: "c", count: 64)),
            ("signature_key_id", "wrong"), ("requires_entitlement", false), ("license_tier", "testing"),
            ("version", "tampered"), ("extra", "untrusted"), ("signature_payload_prefix", "bad"),
            ("package_major_version", true), ("gzip_bytes", 1.5), ("signature", "invalid")] {
            var bad = object; bad[field] = value
            do { _ = try verifier.verify(manifestData: encode(bad)); fatalError("Tamper accepted") }
            catch { rejected += 1 }
        }
        let text = String(decoding: try encode(object), as: UTF8.self)
        let duplicate = Data(("{\"version\":\"duplicate\"," + text.dropFirst()).utf8)
        do { _ = try verifier.verify(manifestData: duplicate); fatalError("Duplicate accepted") } catch { rejected += 1 }
        let wrong = DataPackageSignatureVerifier(trustedKeys: [id: Curve25519.Signing.PrivateKey().publicKey.rawRepresentation])
        do { _ = try wrong.verify(manifestData: encode(object)); fatalError("Wrong key accepted") } catch { rejected += 1 }
        precondition(rejected == 15)
        if CommandLine.arguments.count == 2 {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent("safemed-ephemeral-sign-test-" + UUID().uuidString)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
            defer { try? FileManager.default.removeItem(at: directory) }
            object["signature"] = ""
            let input = directory.appendingPathComponent("input.json")
            let output = directory.appendingPathComponent("signed.json")
            let payload = directory.appendingPathComponent("canonical.json")
            try encode(object).write(to: input)
            func invoke(_ mode: String, _ source: URL, _ target: URL, _ pub: Data) throws -> Int32 {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: CommandLine.arguments[1])
                process.arguments = [mode, source.path, target.path, pub.base64EncodedString()]
                var environment = ProcessInfo.processInfo.environment
                environment["SAFEMED_DATA_PACKAGE_ED25519_PRIVATE_KEY_B64"] = key.rawRepresentation.base64EncodedString()
                process.environment = environment
                process.standardOutput = FileHandle.nullDevice
                process.standardError = FileHandle.nullDevice
                try process.run(); process.waitUntilExit()
                return process.terminationStatus
            }
            let signStatus = try invoke("sign", input, output, key.publicKey.rawRepresentation)
            precondition(signStatus == 0)
            let verifyStatus = try invoke("verify", output, payload, key.publicKey.rawRepresentation)
            precondition(verifyStatus == 0)
            let actualPayload = try Data(contentsOf: payload)
            precondition(actualPayload == canonical)
            let overwriteStatus = try invoke("sign", input, output, key.publicKey.rawRepresentation)
            precondition(overwriteStatus != 0) // immutable output
            let wrongOutput = directory.appendingPathComponent("wrong.json")
            let wrongKeyStatus = try invoke("sign", input, wrongOutput, Curve25519.Signing.PrivateKey().publicKey.rawRepresentation)
            precondition(wrongKeyStatus != 0)
            precondition(!FileManager.default.fileExists(atPath: wrongOutput.path))
            print("PASS_PRODUCER_CLI: sign + reference verify + exact canonical bytes + overwrite/mismatched-key rejection")
        }
        print("PASS_SIGNED_MANIFEST: valid Unicode/escape/null/Int64/formatting + 15 rejection cases; ephemeral test key only")
    }
}
