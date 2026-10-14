# Authorization for setup writes

Use [preflight](preflight-and-identity.md); requested governance writes also load [elevated authority](elevated-authority.md). Diagnosis/installation need no project role. These procedures do not substitute for human approval.

## Validate current authority

Use this package's `assets/schemas/config.schema.json` and `assets/schemas/authorization.schema.json`, Draft 2020-12 and `FormatChecker()`. In the chosen environment require `jsonschema[format]>=4.23,<5` and check support before security validation:

`python3 -c 'from jsonschema import FormatChecker; missing = {"uri", "date-time"} - FormatChecker().checkers.keys(); raise SystemExit("Missing required format checkers: " + ", ".join(sorted(missing)) if missing else 0)'`

Missing import/checkers or invalid data means unverified, never silently skipped validation; propose environment repair and stop dependent writes.

Resolve actual selectors at default SHA; unavailable/damaged governance needs repair/recovery, not fallback. Elevation's frozen-ceiling/scope/account/protection/action intersection governs every write; refresh before governance/review/merge.

## Grant changes

| Proposal | Required authority |
| --- | --- |
| Member → Leader | Human names repository, stable account/actor, scope and ceiling; target currently Maintain/Admin; existing Leader submits under old rules |
| Raise ceiling | Explicit human approval; cannot exceed target account or executing Leader's effective ceiling |
| Maintain Leader → Admin | Existing Leader cannot grant it; human Admin-account session confined to this escalation proposal |
| Revoke | Direct user instruction stops now; persist `revoked` in a separate governance PR, retaining history; other sessions refresh, universal credential cut-off needs human account action |

Initial install/lost last Leader uses [Bootstrap/recovery](bootstrap-and-recovery.md). Elevation's bound-session/promotion/downgrade rules apply.

## Content P → evidence E → activation

1. Resolve [registry conflict](managed-resources.md) before `P`/`E`; authorization is outside automatic whole-file upgrades, history retained.
2. Show repository/account/actor/ceiling/scope/current grants/protections/exact diff/HEAD. Content commit `P` validates proposed fields except unavailable approval evidence: incomplete Draft, cannot merge.
3. Authenticate human approval of P. Follow-up `E` adds `approval_evidence`: PR URL, `approved_by`, `approved_at`, `approved_head_sha=P`. E/P diff: **only approval_evidence fields**. Validate complete E/schema/formats; content/scope/ceiling change restarts approval.
4. **Separate external human approval of final E HEAD**: actual author/repository/PR/SHA/scope/read-back. Equivalent documented approval satisfies only this gate; independent protocol/native requirements remain. No author's native self-Approve; old review dismissal applies, missing gates pending.
5. Old default rules/current-HEAD reviews/checks/SHA-locked merge. Never embed E's own or merge SHA in its authorization; final-E approval/merge/read-back stay external.
6. Same post-merge default SHA config/selected authorization: validate complete schema/formats/identity/active/frozen ceiling/`approved_head_sha=P` against approved content/external final-E approval. Only then persistent Leader.

A proposed branch cannot approve its own authority, schema or checker. A plan/resume record is evidence of progress, not a grant.
