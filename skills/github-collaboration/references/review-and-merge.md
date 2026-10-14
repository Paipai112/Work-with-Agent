# Review, merge and post-merge

Use [preflight](preflight.md), [identity/permissions](identity-and-permissions.md), [claims](claims-and-handoffs.md) and [Git/PR](git-and-pull-requests.md). Governance additionally follows setup approvals. Refresh account/authority/protection, repository/default HEAD and task/PR lineage. Reviewers need no implementation claim.

## Two review gates

1. **Protocol:** Review the exact current HEAD/diff/scope, acceptance, tests/limits, risks and active claims. Another currently effective Leader responsibility or authorized human project owner publishes [review-record.yml](../templates/review-record.yml) with real repository/PR, implementing/reviewing identities, account, reviewed SHA, scope/evidence, conclusion/time/limits. Capture and GET comment ID/URL; independently verify immutable repository ID, PR, actual author ID/login, matching record fields, and current delegation/account permission or human ownership. A pasted URL/body title, revoked grant or implementation actor's own approval is insufficient.
2. **Native GitHub:** Inspect current review states/account IDs, actual required reviews, CODEOWNERS and effective protection. Actors on the author's account cannot supply an eligible other-account Approve; a protocol comment is not native Approve. Missing eligible reviewers leave the PR pending, without reducing existing gates. Where native review is not required, protocol/human approval still is.

Reuse substantive engineering evidence only for its exact HEAD/scope, reviewer, findings and limits; the authorized reviewer must resolve uncovered acceptance/protocol questions. Merge requires a verified protocol `approve` for current HEAD by the other Leader/human owner, plus native requirements. `comment` is feedback. Valid `request-changes` blocks until a later authorized record explicitly resolves/withdraws the concern and approves current HEAD. A bare “fixed” statement is insufficient. Any HEAD change invalidates protocol approval; re-review complete current diff and actual native/check requirements rather than trusting an old displayed green/APPROVED.

## Merge and completion

Immediately GET same-current-HEAD evidence: effective Leader/account/approval scope; claim/Issue lineage; fixed-delivery predecessors **all merged**, fresh actual target/net-diff/scope; governance routing; valid protocol approval/no unresolved changes; native/CODEOWNER reviews; check SHA/conclusion/source; conversations/base/mergeability/protection. Failed/pending/missing/stale/unknown/untrusted blocks merge. Disclose verified enforcement gaps and Actions before trigger; preserve protections, including governance PRs.

Use a 40-character **expected HEAD SHA / SHA lock** with the allowed merge method. Changed HEAD restarts review. Record PR URL, expected SHA and returned merge SHA; a timeout uses [failure recovery](failure-recovery.md) before retry.

GET merged state/SHA and verify reachability on the actual approved target, accounting for merge method. Integration records progress; final delivery needs default-branch reachability and acceptance. Inspect linked Issues, `closes_issues` and events; add only missing completion/release/handoff records, with PR/target/merge SHA, actor, remaining work/successor. GET Issue/event IDs/state. Failed follow-up preserves merge proof and recovers idempotently.
