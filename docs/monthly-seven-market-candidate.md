# Monthly seven-market engineering candidate

The existing `monthly-public-reference.yml` workflow runs on the 18th of each
month at 01:17 UTC (09:17 Asia/Taipei). GitHub may queue scheduled runs.
A scheduled run skips only when a completed, verified seven-market candidate already exists for that Taipei month. A legacy reference-only recovery does not suppress a fresh monthly build.
The runner retrieves official TW, CA, FR, US, JP, KR and AU source exports,
builds source-native projections, produces the 29-table SQLite/gzip candidate,
and checks every market, SQLite integrity, foreign keys, transport roundtrip,
stable IDs and immutable source history. It does not upload a locally built
medicine database. A standalone Foundation utility produces alias keys; it
does not build or test the App.

## Retention and recovery

Successful candidates are prereleases named `global-drug-candidate-YYYY-MM-run-ID-ATTEMPT`.
The full gzip payload, a small durable ID/source checkpoint, verification and
complete source archives are uploaded to a draft release. Every uploaded
asset must match GitHub's server-side SHA256 digest and byte size before the
release is marked complete. Only then may the workflow delete its own older,
strictly named and marked completed monthly candidate releases and tags.
The newest two successful months are retained. Failed builds never clean up.
A retry creates a new immutable run release. Only after the new copy is verified may an older success in the same month be removed; the previous successful month stays.
An incomplete draft is retained for inspection and is never treated
as the previous ledger. Original local source/evidence/FAIL files and unrelated
releases are outside this cleanup policy. Legacy successful package payload artifacts from this same workflow are also removed once their Taipei month is older than the two retained months. Diagnostic, failed and unrelated artifacts are excluded; their existing evidence lifecycle is preserved.

November therefore retains October and November; December retains November
and December. Missing months retain the last two successful months rather than
deleting the last working copy. The checkpoint includes all prior stable IDs,
tombstones and immutable source registrations, so deleting an old payload does
not reset identity history. First migration can recover the existing successful
`LOGICAL-RUNTIME-CANDIDATE` artifact. Missing history fails closed.

To reconstruct sources: download all `sources.tar.gz.part-*` assets from a
single release, concatenate in lexical order and extract into a fresh directory.
The release marker is an unsigned engineering record, not the formal App
download manifest. Source copyright notices and transformations are retained
in the source archive. No private API key is stored. PBS uses HPP's anonymously
published Postman example header, subject to its public request-rate limit.

## Scope still pending

Technical build success does not establish worldwide completeness, chemical
equivalence between countries, current verified composition, clinical rules,
redistribution approval, App integration or iPhone performance. US catalogue
vs bulk discrepancies remain visible in the US intake report; KR component
gaps remain UNKNOWN; JP is price-list scope and AU is PBS subsidy scope.
All clinical/right statuses remain PENDING/UNKNOWN. This collection workflow
does not sign or activate its candidate. Successful completion automatically
starts the separate [signed reference workflow](signed-monthly-reference.md),
which authenticates an independent download while preserving those statuses.
No formal App shipping approval, latest feed activation, TestFlight upload or
runtime gate is changed.

The workflow checks that its workflow-file bytes still match `main` before expensive collection and before publication. GitHub requires a permission unavailable to `GITHUB_TOKEN` when releasing a commit with different workflow files. If workflow files change during a run, rerun latest main; the old run fails without publishing or deleting older packages. No personal access token is stored in Actions.
