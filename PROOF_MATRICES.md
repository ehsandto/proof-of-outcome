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

## Live StudioNet certificates

Evidence is pinned to commit `a3b3a99f1f6ed70db556b8a417a8b898556ee840`.

### Software delivery 4×4

- Template: https://explorer-studio.genlayer.com/tx/0x0d591fdd01b9f579667c4d267d7457084096973c21f38be0be3874b8a9d4b1c9
- Claim: https://explorer-studio.genlayer.com/tx/0x4a083b613855f795182b093b608b3586d2b90e3d5f474676fb9509fefc9ae8d6
- Certificate: https://explorer-studio.genlayer.com/tx/0x796fc9e8bb4be662a4a8b7a2e997d52492a5e9ef3c77ada49991f0b5bccbc0fc
- Claim ID: `software-delivery-4x4-claim-1786285898766`

### Package release 4×4

- Template: https://explorer-studio.genlayer.com/tx/0x0130c6d93f85f8e5a8e453e2178e36bcc8be2308f50cb107030b0ae24649e2f1
- Claim: https://explorer-studio.genlayer.com/tx/0xda37605ee269dcba9d9947d23822ff70c438dfff142c8861988c314a0614825a
- Certificate: https://explorer-studio.genlayer.com/tx/0x2ea130c97049c8d1f40130f63d428d71465704d0186cb49bbee37061055ae80a
- Claim ID: `package-release-4x4-claim-1786285898766`
