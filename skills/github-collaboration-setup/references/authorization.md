# Authorization for setup writes

Use [preflight](preflight-and-identity.md) and [session core](session-core.md) for same-SHA selectors, stable identity, Member default and frozen-ceiling calculation. Diagnose can report missing facts without a role grant. Installation approval is separate from project authority.

## Validate current authority

Use this package's `assets/schemas/config.schema.json` and `assets/schemas/authorization.schema.json`, Draft 2020-12 and `FormatChecker()`. In the chosen environment require `jsonschema[format]>=4.23,<5` and check support before security validation:

`python3 -c 'from jsonschema import FormatChecker; missing = {"uri", "date-time"} - FormatChecker().checkers.keys(); raise SystemExit("Missing required format checkers: " + ", ".join(sorted(missing)) if missing else 0)'`

Missing import/checkers or invalid data means unverified, never silently skipped validation; propose environment repair and stop dependent writes.

Persistent authority comes only from exactly one approved active default-branch delegation matching host/repository/default branch, authenticated ID/login and selected actor. Validate proposal provenance `default_branch_source_sha` separately from today's source/read-back SHA. Local files, proposed selectors, `granted_by` and candidate active status grant nothing. Custom normalized filenames inside the configured governance directory are valid; unavailable/damaged governance needs repair/recovery, not a fallback.

A write requires: effective Leader or current bounded Bootstrap/Recovery session ∩ frozen ceiling ∩ fresh account rights ∩ delegated/project scope ∩ actual inherited protection ∩ approval of the exact change/action. Maintain/Admin alone is Member; below Maintain cannot act as Leader. Unknown applicable rules block affected writes, while verified unsupported enforcement is disclosed without dropping protocol review or known stronger gates. Refresh before each governance action/review/merge.

## Grant changes

| Proposal | Required authority |
| --- | --- |
| Member → Leader | Human names repository, stable account/actor, scope and ceiling; target currently Maintain/Admin; existing Leader submits under old rules |
| Account promotion | Stored ceiling unchanged; expansion requires a new approved proposal |
| Account downgrade | Tighten immediately; below Maintain removes Leader authority |
| Raise ceiling | Explicit human approval; cannot exceed target account or executing Leader's effective ceiling |
| Maintain Leader → Admin | Existing Leader cannot grant it; human Admin-account session confined to this escalation proposal |
| Revoke | Direct user instruction stops now; persist `revoked` in a separate governance PR, retaining history; other sessions refresh, universal credential cut-off needs human account action |

Initial install/lost last Leader uses [Bootstrap/recovery](bootstrap-and-recovery.md). Session grants bind repository/source SHA, account/actor, proposal, allowed actions and current-session lifetime; interruption or changed binding needs fresh preflight/confirmation.

## Content P → evidence E → activation

1. Resolve any registry ownership conflict through [managed resources](managed-resources.md) before `P`/`E`. Authorization stays outside generic automatic whole-file upgrades; retain history.
2. Show repository/account/actor/ceiling/scope, current grants/protections and exact governance diff/PR HEAD. At content commit `P`, validate proposed fields except unavailable approval evidence; it is an incomplete Draft and cannot merge.
3. Obtain authentic human approval of content at `P`. In a follow-up `E`, add `approval_evidence`: PR URL, `approved_by`, `approved_at`, `approved_head_sha=P`. Compare E/P: **only approval_evidence fields** may differ. Validate complete E with schema/formats; any content/scope/ceiling change restarts content approval.
4. Obtain **separate external human approval of final E HEAD**, verifying actual author, repository/PR, exact SHA, scope and read-back. Equivalent documented approval satisfies this human gate only: independent protocol review and existing native requirements still apply. The PR author's account cannot supply its own native Approve. Respect dismissal of old reviews; preserve missing gates as pending.
5. Merge under existing default-branch rules with current-HEAD review/checks and SHA lock. Do not write E's own SHA or merge SHA into its containing authorization file. Keep final-E approval, merge and read-back externally.
6. Read config plus its selected authorization from the same post-merge default-branch SHA; validate complete schemas/formats, identity, active status, frozen ceiling and `approved_head_sha=P` against approved content and external final-E approval. Only then report persistent Leader.

A proposed branch cannot approve its own authority, schema or checker. A plan/resume record is evidence of progress, not a grant.
