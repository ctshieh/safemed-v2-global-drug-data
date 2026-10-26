import Foundation
#if canImport(DrugManifestReference)
import DrugManifestReference
#endif
#if canImport(CryptoKit)
import CryptoKit
#else
import Crypto
#endif

@main
struct SignDrugManifest {
    static func main() {
        do { try run() }
        catch {
            // Never interpolate an exception that could contain environment material.
            FileHandle.standardError.write(Data("Manifest signing/verification failed.\n".utf8))
            exit(1)
        }
    }
    static func run() throws {
        let args = CommandLine.arguments
        guard args.count == 5, ["sign", "verify"].contains(args[1]),
            let publicData = Data(base64Encoded: args[4]), publicData.count == 32 else {
            throw Failure.invalid
        }
        let source = URL(fileURLWithPath: args[2])
        let target = URL(fileURLWithPath: args[3])
        let data = try Data(contentsOf: source)
        guard data.count <= 1024 * 1024 else { throw Failure.invalid }
        var object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let keyID = object?["signature_key_id"] as? String else { throw Failure.invalid }
        let verifier = DataPackageSignatureVerifier(trustedKeys: [keyID: publicData])
        if args[1] == "sign" {
            guard let encoded = ProcessInfo.processInfo.environment["SAFEMED_DATA_PACKAGE_ED25519_PRIVATE_KEY_B64"],
                let raw = Data(base64Encoded: encoded), raw.count == 32 else { throw Failure.invalid }
            let key = try Curve25519.Signing.PrivateKey(rawRepresentation: raw)
            guard key.publicKey.rawRepresentation == publicData else { throw Failure.invalid }
            let manifest = try JSONDecoder().decode(SignedDataPackageManifest.self, from: data)
            let signature = try key.signature(for: manifest.canonicalSigningPayload())
            object?["signature"] = signature.base64EncodedString()
            let signed = try JSONSerialization.data(withJSONObject: object!, options: [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes])
            _ = try verifier.verify(manifestData: signed)
            guard !FileManager.default.fileExists(atPath: target.path) else { throw Failure.invalid }
            try signed.write(to: target, options: [.atomic])
        } else {
            let manifest = try verifier.verify(manifestData: data)
            let canonical = try manifest.canonicalSigningPayload()
            guard !FileManager.default.fileExists(atPath: target.path) else { throw Failure.invalid }
            try canonical.write(to: target, options: [.atomic])
        }
        print("PASS_ED25519_SAFEMED_SORTED_JSON_V1")
    }
    enum Failure: Error { case invalid }
}
