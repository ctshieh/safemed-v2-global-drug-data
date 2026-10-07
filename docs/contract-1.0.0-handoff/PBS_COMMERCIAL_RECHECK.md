# PBS commercial use recheck — 2026-10-08

## Result

Commercial use is not yet verified. Public access and explicit permission to redistribute are verified; an unconditional commercial or adaptation license is not.

## Evidence

The official [API catalogue](https://data-api-portal.health.gov.au/apis) publishes a public subscription key. Its API metadata identifies the `Subscription-Key` header. A read-only request to `https://data-api.health.gov.au/pbs/api/v3/schedules?limit=1` returned HTTP 200. The exact returned `_meta`, including the copyright statement, is retained in `pbs-api-copyright-evidence.json` with the full response SHA-256. No drug rows were ingested.

The API copyright message states:

> Permission is granted to use and redistribute this content, as long as all copyright statements are retained. Permission is not granted to modify this content.

It also refers readers to [Department of Health copyright](https://www.health.gov.au/using-our-websites/copyright). That page permits personal/internal reproduction except where otherwise indicated and separately states that website content must not be used for any commercial purpose. The specific API permission may constitute an exception, but its commercial scope is not explicit. We cannot resolve that legal scope merely from free public access or software-vendor usage.

The [official release notes](https://data.pbs.gov.au/api/api-release-notes.html) confirm that copyright metadata was added to every endpoint on 21 February 2025. [Public API documentation](https://data.pbs.gov.au/api/api-public.html) permits downloads and local software import, with a shared one-request-per-twenty-seconds limit.

## Correction and handling

The previous Australian intake record said no specific redistribution permission had been verified. This recheck found explicit API redistribution permission and corrects that record. It does not establish an unrestricted commercial-use license.

Retain all copyright notices. Do not assume ingredient-name normalization, translation, textual modification, or merged derived content is allowed by the no-modification permission. SQLite conversion preserving original values and notices requires scope clarification before commercial release. PBS is schedule/reimbursement information and must not be represented as a complete drug-interaction source.

Commercial App packaging remains ineligible pending authoritative clarification of commercial redistribution and the intended conversions. TGA rights status is unchanged. No permission enquiry was sent, no full PBS data build was run, and no runtime activation or formal release occurred.
