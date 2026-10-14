# Resume a setup operation

A progress record is not a role grant or approval of today's diff. Refresh [preflight](preflight-and-identity.md), [authorization](authorization.md), [local configuration](local-configuration.md) and [ownership](managed-resources.md) for the actual resumed action.

Keep local configuration's complete `operation_id` plan plus returned IDs, Commit/pushed HEAD/PR, separate Actions/setting/check approvals and errors. No secrets. States: planned, approved, write-sent-result-unknown, read-back-verified, blocked; 2xx is not read-back.

1. Re-establish identity, effective role/default-branch authority, protections, current source/branch/HEAD. Old Bootstrap/Recovery sessions do not transfer; obtain fresh bound confirmation.
2. Compare current item IDs/bytes/fields with baseline and approval digest. Drift/revocation/unknown approval invalidates that item; show new diff and obtain exact approval. Never replay verified completed items.
3. A possible local edit/Commit requires source/index/status and commit/parent inspection; preserve user work and choose the next separately approved Git action.
4. A possible Push/PR needs exact remote ref and unique repository/head/base/operation match; ambiguous results stop, without force.
5. Unknown remote mutation: GET stable ID; creation without returned ID searches exact repository/type/name/path and requires one match with approved fields. Retry only after confirming no matching mutation happened and rechecking current approval/authority.
6. Read back one item and report verified/unchanged/blocked/unknown resources with ID/digest/next action.

Without a reliable record rebuild a read-only inventory instead of guessing. File/Git/API operations are not one transaction; concurrent conflicts preserve current data/protection pending a decision, not automatic replacement.
