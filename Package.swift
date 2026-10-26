// swift-tools-version:6.2
import PackageDescription

let package = Package(
    name: "SafeMedDrugManifestTools",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "sign-manifest", targets: ["SignDrugManifest"]),
        .executable(name: "test-manifest", targets: ["TestSignedManifest"]),
    ],
    dependencies: [
        // Apple Swift Crypto 5.0.3. Fixed commit, not a floating branch/tag.
        .package(url: "https://github.com/apple/swift-crypto.git", revision: "c2cbadd7263439d8015189668f96ff5b5be565ce"),
    ],
    targets: [
        .target(name: "DrugManifestReference", dependencies: [.product(name: "Crypto", package: "swift-crypto")], path: "signing/Reference"),
        .executableTarget(name: "SignDrugManifest", dependencies: ["DrugManifestReference", .product(name: "Crypto", package: "swift-crypto")], path: "signing/Signer"),
        .executableTarget(name: "TestSignedManifest", dependencies: ["DrugManifestReference", .product(name: "Crypto", package: "swift-crypto")], path: "signing/Regression"),
    ]
)
