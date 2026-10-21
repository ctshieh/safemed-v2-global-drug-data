# Logical candidate pipeline, 2026-10-21

The App owner confirmed one logical 29-table COMPOSED_SNAPSHOT remains the data contract. Compressed-block verified storage and streaming whole validation are isolated App engineering prototypes, not shipping capabilities. Never misdeclare compressed physical bytes as sqlite_bytes. Existing 32 MiB/250000-row limits remain authoritative for the current App. Keep complete source archives on the build side; report candidate incompatibility instead of truncating original required content.

The data workflow now builds a separate real-source TW/CA/FR logical candidate from eligible official native identities and all acquired matching ingredient rows. It does not turn the reference tarball into a runtime payload. JP/KR/EMA and auxiliary-source exclusions are explicit. Source-scoped names/codes are not cross-country chemical equivalence. All product composition is UNKNOWN, product mappings UNMAPPED, clinical rules empty, source_rights PENDING and quality gate CANDIDATE_ONLY. This is unsigned engineering input; not an accepted clinical/runtime release.

Current source-row verification now reparses original bytes and compares every stored row tuple, exact JSON, native ID, order and locator, plus ingredient projections and orphan-source checks. It reuses pinned intake parsers, so this is independent stored-row reconciliation, not an independently implemented parser or medical correctness proof. Tar preflight limits total expansion to 4 GiB, one member to 2 GiB and member count to 4096; fail before extraction.

Separate TEST_ONLY synthetic fixtures preserve UNKNOWN/PARTIAL/CONFLICT, the third ingredient, raw strength/basis, NONE coverage and zero active rules. Production gates reject fixtures; workflow artifacts clearly separate them from real-source candidates.

Reproduce with the exact immutable inputs, version, created-at and previous snapshot:

```sh
python3 scripts/build_logical_runtime_candidate.py --inputs inputs --output dist/logical-candidate --version candidate-VERSION --created-at 2026-10-21T00:00:00+00:00
python3 scripts/measure_logical_candidate.py --sqlite dist/logical-candidate/snapshot.sqlite3 --gzip dist/logical-candidate/snapshot.sqlite3.gz --output measurements.json
```

Updates MUST supply --previous to retain compact IDs, source registry snapshot metadata, release sequence and retired tombstones. The GitHub workflow downloads the prior logical artifact when available and fails if its recorded artifact is expired instead of silently resetting IDs. Artifacts have a finite 90-day retention; permanent archival beyond downloaded local evidence remains an explicit deployment gap. No formal manifest, trusted key, App source or user data is overwritten.

First hosted candidate requires workflow_dispatch initialize_logical_candidate=true, explicitly a proposal and never human medical/ID approval. Scheduled runs cannot initialize a missing ledger. A previous successful candidate step with no surviving artifact fails closed; missing history also fails unless explicitly initialized. Local and hosted proposals are not assumed to be the same accepted ledger.
