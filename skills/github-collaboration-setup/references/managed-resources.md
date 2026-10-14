# Managed resources and ownership

Use [local configuration](local-configuration.md) for plan/apply. The registry records a change baseline, not authority. Validate with bundled `assets/schemas/managed-resources.schema.json`, Draft 2020-12 and `FormatChecker()`.

Each entry needs `kind`, `stable_id`, `template_version`, `managed_fields_baseline_digest`, `applied_digest`, recoverable `baseline_reference`; digests are `sha256:<64 lowercase hex>`. Include registry changes in the exact governance diff. Never use a new registry entry to retroactively claim a resource, invent an ancestor or store credentials.

| Resource | Permitted maintenance boundary |
| --- | --- |
| Markdown entries | One exact approved managed block; renderer preserves all outside bytes. Duplicate/broken/similar unmanaged markers stop |
| config.yml | Strictly parse actual current/baseline/candidate, validate schema/formats, preserve unknown fields/comments/order/unrelated bytes; exact text diff. Unreliable preservation needs manual choice |
| Selected authorization | Explicit [authorization](authorization.md) P/E proposal, outside automatic whole-file upgrades; preserve grants/history/unknown bytes |
| Issue/PR templates and workflows | New path unoccupied; existing managed path uses verified last-applied ancestor, current bytes and new template. Update only approved unchanged portions; overlap or missing ancestor requires a choice |
| CODEOWNERS | Preserve order/lines; verify eligible accounts/teams and effective last-pattern ownership per path. Ownership changes need separate approval |
| Labels/Rulesets/protection | Exact repository/stable ID plus verified managed-field baseline; preserve unowned/inherited/stronger fields. Same name is not ownership |

Report `baseline → current` user drift, `baseline → proposed` template change and exact `current → candidate`. Missing baseline/overlap offers retain, reviewed merge, another resource/path or explicit takeover. Keep existing protection; user chooses and approves exact resulting bytes/fields.

For files hash full bytes; for remote resources deterministically hash stable ID plus **only named managed fields**. Use identical selection/serialization for baseline, approval and read-back; inability to reproduce stops a match claim. Record untouched fields separately. Registry updates bind old baseline/digest and newly read-back applied digest; raw `__SETUP_REQUIRED__` is not an installed value.

## Authorization registry conflict

New installs keep authorization outside automatic whole-file ownership. If an old registry already tracks it, show entry/ID/recoverable baseline/prior/current digests before P/E: evidence-only E changes authorization digest, while updating registry in E violates the evidence-only rule. Obtain an explicit choice to retain/defer pending a non-circular maintenance plan, or separately approve migration out of automatic ownership. Preserve the original entry/baseline as audit history and show exact registry diff. Until verified, both registry and authorization remain intact.

## One-item approval/apply loop

1. GET exact local bytes or full paginated/inherited remote state; record repository/path/stable ID and untouched fields. 403/404/missing fields are unknown, not absence.
2. Show baseline/current/candidate diff/digests, ownership, exact fields/effects/unknowns. Obtain individual approval for this item; file treatment, Commit, Push, PR, Actions execution and each setting remain separate.
3. Refresh identity/default authority/account/protection and exact target/candidate digest. Drift invalidates this item. Apply approved bytes/fields only; preserve user/unowned/inherited/stronger state.
4. GET/read back path/ID, approved and untouched values; bind returned ID/digest. Unknown result queries stable ID, or exact repository/type/name/path for creation; ambiguity stops, no blind retry. Local pre-read/write is not atomic.
