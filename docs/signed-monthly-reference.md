# Signed monthly reference downloads

`sign-monthly-reference.yml` takes the exact tag of a successful monthly
seven-market build. It runs only from this repository's main branch. It does
not collect a substitute fixture, rebuild the App, activate a package, alter
the medical/rights statuses, or delete older releases.

The publisher verifies the source run/attempt/commit, all GitHub server asset
SHA-256 digests and lengths, the downloaded full assets, the complete gzip
roundtrip, SQLite integrity/foreign keys, 29 tables, and all seven market
counts. Metadata is read from the actual SQLite package_manifest, including
the original data_version. The signed manifest binds the final immutable
release asset URL, exact compressed/decompressed lengths and hashes, and
consumer compatibility declarations.

`scripts/DataPackageSignatureVerifier.swift` is the unchanged App consumer
reference encoder/verifier (SHA-256
`f42ea61536a7c522b6a9191b0a7a3dde628ef7faab88e213951634b4b7a88152`).
`SignDrugManifest.swift` uses that implementation and CryptoKit Ed25519.
The contract is `ED25519_SAFEMED_SORTED_JSON_V1`, Foundation sorted JSON
without escaped slashes, including explicit legacy `sha256:null`. This is
not RFC 8785. `canonical-payload.json` is the exact signed byte stream, with
no trailing newline. The publisher verifies the signature again before
uploading, and checks every remote asset's server digest and bytes before
publishing the draft. Independent copies of the payload and original source
archives prevent candidate retention from breaking a signed download.

## Key configuration

The dedicated private key is a standard Base64-encoded 32-byte Ed25519 seed
in the Actions repository secret
`SAFEMED_DATA_PACKAGE_ED25519_PRIVATE_KEY_B64`. It is exposed only to the
signing step, never printed, committed, uploaded, placed in command-line
arguments, or included in the App. There is no signing credential for pull
requests or arbitrary branch execution. The publisher needs only
GITHUB_TOKEN with contents:write; no personal access token is stored.

Public variables `SAFEMED_DATA_PACKAGE_SIGNING_KEY_ID` and
`SAFEMED_DATA_PACKAGE_ED25519_PUBLIC_KEY_B64` must exactly match the reviewed
public pin in `contracts/signing/2026-10-release-public-key.json`. The same
32-byte public key must be pinned by the App owner inside the signed App's
`SafeMedTrustedDataPackageKeys` Info.plist dictionary. A manifest cannot
supply its own trust root. A local macOS login Keychain backup exists for
this initial release key; it is separate from this repository.

For rotation, first distribute the next public key through an App release,
then configure a new private secret/public ID and reviewed pin. Preserve
older public IDs as required by the App's explicit trust policy. Signature
verification alone does not provide anti-rollback; the existing consumer
contract does not sign a release counter or expiry.

## Delivery and remaining acceptance gates

Each signing attempt creates an independent immutable tag:
`signed-drug-reference-YYYY-MM-run-SOURCE-ATTEMPT-sign-PUBLISHER-ATTEMPT`.
The release is deliberately a **prerelease** while medical/source-rights
review and formal App acceptance remain pending. It is not made the
production `releases/latest` update feed. The original unsigned candidate
reports stay unchanged; `SIGNED_RELEASE.json` records the new signature,
provenance, public key and remaining gaps separately. This is an
authenticated reference download, not a formal clinically approved
shipping package.

App integration must separately resolve the hardcoded manifest 404,
GitHub asset HTTPS redirects versus the existing no-redirect payload
policy, source-rights and medical gates, entitlement, activation/rollback,
complete App QA and required iPhone Simulator performance tests. A valid
signature must not bypass any of these. TestFlight/ASC upload, real-device
permissions, purchase/restore operations and paid APIs are not performed.

Local/Actions regression checks use ephemeral test keys only. They cover
valid/reformatted signed manifests, Unicode/escapes/null/Int64 encoding,
tampering, duplicate/unknown fields, wrong public keys, immutable signing
outputs, source provenance failures and unexpected asset rejection. They
do not constitute App QA or performance acceptance.
