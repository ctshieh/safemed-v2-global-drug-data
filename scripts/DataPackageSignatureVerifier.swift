import Foundation
import CryptoKit

/// Ed25519 authenticity checks with application-pinned keys, never manifest-supplied keys.
struct DataPackageSignatureVerifier {
    static let algorithm = "ED25519_SAFEMED_SORTED_JSON_V1"
    static let trustedKeysInfoKey = "SafeMedTrustedDataPackageKeys"
    // Bound only transport metadata; the existing clinical package32MiB consumer contract is unchanged.
    static let maximumManifestBytes2117 = 1024 * 1024
    private let trustedKeys: [String: Data]

    static func userFacingMessage(language: String) -> String {
        let code = language.lowercased()
        let normalized = code.hasPrefix("zh") ? "zh" : code.hasPrefix("fil") || code.hasPrefix("tl") ? "fil" : String(code.prefix(2))
        let messages: [String: String] = [
            "zh": "更新資料尚未通過可信驗證，已拒絕更新。原有紀錄仍保留。",
            "en": "The update could not be verified as trusted and was rejected. Your existing records are preserved.",
            "ja": "更新データの信頼性を確認できなかったため、更新を拒否しました。既存の記録は保持されます。",
            "ko": "업데이트의 신뢰성을 확인할 수 없어 업데이트를 거부했습니다. 기존 기록은 유지됩니다.",
            "fr": "La fiabilité de la mise à jour n’a pas pu être vérifiée. Elle a été refusée. Vos données existantes sont conservées.",
            "de": "Die Vertrauenswürdigkeit der Aktualisierung konnte nicht bestätigt werden. Sie wurde abgelehnt. Ihre vorhandenen Aufzeichnungen bleiben erhalten.",
            "vi": "Không thể xác minh độ tin cậy của bản cập nhật nên đã từ chối cập nhật. Các bản ghi hiện có được giữ nguyên.",
            "id": "Kepercayaan terhadap pembaruan tidak dapat diverifikasi, sehingga pembaruan ditolak. Catatan Anda yang ada tetap tersimpan.",
            "th": "ไม่สามารถยืนยันความน่าเชื่อถือของข้อมูลอัปเดตได้ จึงปฏิเสธการอัปเดต บันทึกเดิมยังคงอยู่",
            "fil": "Hindi mapatunayan na mapagkakatiwalaan ang update kaya tinanggihan ito. Nananatili ang iyong mga kasalukuyang tala."
        ,
            "es": "No se pudo verificar la fiabilidad de la actualización y se ha rechazado. Se conservan los registros existentes."
        ]
        return messages[normalized] ?? messages["en"]!
    }

    enum VerificationError: Error, LocalizedError, Equatable {
        case invalidManifest, unknownFields, missingSignature, unsupportedAlgorithm
        case missingTrustedKeys, unknownKey, invalidPublicKey, invalidSignature, invalidPayload
        var errorDescription: String? {
            switch self {
            case .invalidManifest: return "資料包更新清單格式無效。"
            case .unknownFields: return "更新清單含未支援欄位，已拒絕更新。"
            case .missingSignature: return "更新清單缺少正式簽章，已拒絕更新。"
            case .unsupportedAlgorithm: return "不支援此簽章方式，已拒絕更新。"
            case .missingTrustedKeys: return "App 尚未設定可信資料包公鑰，已拒絕更新。"
            case .unknownKey: return "簽章金鑰不在 App 信任清單內，已拒絕更新。"
            case .invalidPublicKey: return "App 的資料包公鑰設定無效，已拒絕更新。"
            case .invalidSignature: return "資料包簽章驗證失敗，已拒絕更新。"
            case .invalidPayload: return "資料包必要欄位無效，已拒絕更新。"
            }
        }
    }

    /// Injection is for tests or keys obtained from the application bundle, never network input.
    init(trustedKeys: [String: Data]) { self.trustedKeys = trustedKeys }

    static func bundled(bundle: Bundle = .main) throws -> DataPackageSignatureVerifier {
        try configured(infoDictionary: bundle.infoDictionary ?? [:])
    }

    static func configured(infoDictionary: [String: Any]) throws -> DataPackageSignatureVerifier {
        guard let encoded = infoDictionary[trustedKeysInfoKey] as? [String: String], !encoded.isEmpty else {
            throw VerificationError.missingTrustedKeys
        }
        var keys: [String: Data] = [:]
        for (id, raw) in encoded {
            guard !id.isEmpty, let data = Data(base64Encoded: raw), data.count == 32 else {
                throw VerificationError.invalidPublicKey
            }
            keys[id] = data
        }
        return DataPackageSignatureVerifier(trustedKeys: keys)
    }

    /// Returns the authenticated typed manifest. Call before URL resolution, version checks or activation.
    func verify(manifestData: Data) throws -> SignedDataPackageManifest {
        guard !manifestData.isEmpty, manifestData.count <= Self.maximumManifestBytes2117 else { throw VerificationError.invalidManifest }
        do { try SignedManifestObjectMembers2117.validateUniqueMembers(manifestData) }
        catch { throw VerificationError.invalidManifest }
        guard let object = (try? JSONSerialization.jsonObject(with: manifestData)) as? [String: Any] else {
            throw VerificationError.invalidManifest
        }
        guard Set(object.keys).isSubset(of: SignedDataPackageManifest.allowedKeys) else {
            throw VerificationError.unknownFields
        }
        guard let signatureText = object["signature"] as? String, !signatureText.isEmpty else {
            throw VerificationError.missingSignature
        }
        guard object["signature_algorithm"] as? String == Self.algorithm,
              object["signature_payload_prefix"] == nil || object["signature_payload_prefix"] is NSNull else {
            throw VerificationError.unsupportedAlgorithm
        }
        guard let manifest = try? JSONDecoder().decode(SignedDataPackageManifest.self, from: manifestData) else {
            throw VerificationError.invalidManifest
        }
        guard !trustedKeys.isEmpty else { throw VerificationError.missingTrustedKeys }
        guard let keyData = trustedKeys[manifest.signatureKeyID] else { throw VerificationError.unknownKey }
        guard keyData.count == 32, let key = try? Curve25519.Signing.PublicKey(rawRepresentation: keyData) else {
            throw VerificationError.invalidPublicKey
        }
        let payload = try manifest.canonicalSigningPayload()
        guard let signature = Data(base64Encoded: signatureText), signature.count == 64,
              key.isValidSignature(signature, for: payload) else { throw VerificationError.invalidSignature }
        return manifest
    }
}

/// Exact versioned producer contract. Optional legacy sha256 is signed as explicit null if absent.
struct SignedDataPackageManifest: Codable, Equatable, Sendable {
    let schemaVersion: String
    let packageMajorVersion: Int
    let productLine: String
    let licenseTier: String
    let requiresEntitlement: Bool
    let compatibleAppMajorVersions: [Int]
    let version: String
    let createdAt: String
    let packageURL: String
    let packageFormat: String
    let gzipBytes: Int64
    let sqliteBytes: Int64
    let sha256: String?
    let gzipSHA256: String
    let sqliteSHA256: String
    let signature: String
    let signatureAlgorithm: String
    let signatureKeyID: String

    enum CodingKeys: String, CodingKey, CaseIterable {
        case schemaVersion = "schema_version", packageMajorVersion = "package_major_version"
        case productLine = "product_line", licenseTier = "license_tier", requiresEntitlement = "requires_entitlement"
        case compatibleAppMajorVersions = "compatible_app_major_versions", version, createdAt = "created_at"
        case packageURL = "package_url", packageFormat = "package_format", gzipBytes = "gzip_bytes", sqliteBytes = "sqlite_bytes"
        case sha256, gzipSHA256 = "gzip_sha256", sqliteSHA256 = "sqlite_sha256"
        case signature, signatureAlgorithm = "signature_algorithm", signatureKeyID = "signature_key_id"
    }
    static let allowedKeys = Set(CodingKeys.allCases.map(\.rawValue) + ["signature_payload_prefix"])

    func canonicalSigningPayload() throws -> Data {
        func isHash(_ value: String) -> Bool {
            value.count == 64 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
        }
        guard !version.isEmpty, !createdAt.isEmpty, !schemaVersion.isEmpty, packageMajorVersion > 0,
              !productLine.isEmpty, !licenseTier.isEmpty,
              let downloadURL = URL(string: packageURL), downloadURL.scheme?.lowercased() == "https", downloadURL.host != nil,
              downloadURL.user == nil, downloadURL.password == nil, !packageFormat.isEmpty,
              !signatureKeyID.isEmpty, signatureAlgorithm == DataPackageSignatureVerifier.algorithm,
              gzipBytes > 0, sqliteBytes > 0, !compatibleAppMajorVersions.isEmpty,
              compatibleAppMajorVersions.allSatisfy({ $0 > 0 }),
              Set(compatibleAppMajorVersions).count == compatibleAppMajorVersions.count,
              compatibleAppMajorVersions == compatibleAppMajorVersions.sorted(),
              isHash(gzipSHA256), isHash(sqliteSHA256), sha256 == nil || sha256 == gzipSHA256 else {
            throw DataPackageSignatureVerifier.VerificationError.invalidPayload
        }
        // Foundation sorted-key JSON, explicitly not RFC 8785. All integer values are exact Int/Int64.
        let payload: [String: Any] = [
            "signature_algorithm": signatureAlgorithm, "signature_key_id": signatureKeyID,
            "schema_version": schemaVersion, "package_major_version": packageMajorVersion,
            "product_line": productLine, "license_tier": licenseTier, "requires_entitlement": requiresEntitlement,
            "compatible_app_major_versions": compatibleAppMajorVersions,
            "version": version, "created_at": createdAt, "package_url": packageURL, "package_format": packageFormat,
            "gzip_bytes": gzipBytes, "sqlite_bytes": sqliteBytes,
            "sha256": sha256.map { $0 as Any } ?? NSNull(),
            "gzip_sha256": gzipSHA256, "sqlite_sha256": sqliteSHA256
        ]
        return try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys, .withoutEscapingSlashes])
    }
}

private enum SignedManifestObjectMembers2117 {
    enum Failure: Error { case unreadable, duplicateMember }
    static func validateUniqueMembers(_ data: Data) throws {
        let prefix = Array(data.prefix(4))
        let encoding: String.Encoding
        if prefix.starts(with: [0, 0, 0xFE, 0xFF]) || (prefix.count == 4 && prefix[0] == 0 && prefix[1] == 0 && prefix[2] == 0) {
            encoding = .utf32BigEndian
        } else if prefix.starts(with: [0xFF, 0xFE, 0, 0]) || (prefix.count == 4 && prefix[1] == 0 && prefix[2] == 0 && prefix[3] == 0) {
            encoding = .utf32LittleEndian
        } else if prefix.starts(with: [0xFE, 0xFF]) || (prefix.count == 4 && prefix[0] == 0 && prefix[2] == 0) {
            encoding = .utf16BigEndian
        } else if prefix.starts(with: [0xFF, 0xFE]) || (prefix.count == 4 && prefix[1] == 0 && prefix[3] == 0) {
            encoding = .utf16LittleEndian
        } else {
            encoding = .utf8
        }
        guard let text = String(data: data, encoding: encoding) else { throw Failure.unreadable }
        let bytes = Array(text.utf8)
        var index = 0, objects: [Set<String>] = []
        while index < bytes.count {
            switch bytes[index] {
            case 123: // {
                objects.append([]); index += 1
            case 125: // }
                guard !objects.isEmpty else { throw Failure.unreadable }
                objects.removeLast(); index += 1
            case 34: // JSON string; escaped quotes remain inside the token.
                let start = index
                index += 1
                while index < bytes.count && bytes[index] != 34 {
                    index += bytes[index] == 92 ? 2 : 1
                }
                guard index < bytes.count else { throw Failure.unreadable }
                index += 1
                var next = index
                while next < bytes.count && [9, 10, 13, 32].contains(bytes[next]) { next += 1 }
                if next < bytes.count && bytes[next] == 58 {
                    guard !objects.isEmpty else { throw Failure.unreadable }
                    let key = try JSONDecoder().decode(String.self, from: Data(bytes[start..<index]))
                    guard objects[objects.count - 1].insert(key).inserted else { throw Failure.duplicateMember }
                }
            default:
                index += 1
            }
        }
        guard objects.isEmpty else { throw Failure.unreadable }
    }
}
