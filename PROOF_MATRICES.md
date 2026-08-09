# Live Proof Matrices

Each matrix uses four immutable, commit-pinned HTTPS evidence documents and four
ordered criteria. Validators independently retrieve all four sources. The stored
certificate binds the complete criterion vector, source status vector, combined
evidence fingerprint, failure vector, confidence bucket, and derived outcome.

## Matrix A: software delivery

| Evidence source | Tests | API compatibility | Security | Documentation |
|---|---:|---:|---:|---:|
| CI | primary | contextual | contextual | contextual |
| API diff | contextual | primary | contextual | contextual |
| Security scan | contextual | contextual | primary | contextual |
| Documentation audit | contextual | contextual | contextual | primary |

## Matrix B: package release

| Evidence source | Published version | Release tag | Provenance | License |
|---|---:|---:|---:|---:|
| Package registry | primary | contextual | digest | metadata |
| Source repository | contextual | primary | signature | contextual |
| Build provenance | digest | commit | primary | contextual |
| License audit | contextual | contextual | contextual | primary |

“Primary” and “contextual” are documentation labels only. The contract does not
apply arbitrary source weights: every configured source must be available and
every criterion must independently resolve to `PASS` for `SUCCESS`.
