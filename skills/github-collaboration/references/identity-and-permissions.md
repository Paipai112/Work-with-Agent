# Identity and permission decision

Use [session core](session-core.md) for account/actor binding, same-SHA authority, schema validation, Member default and frozen ceiling. Recompute before formal review, reassign, merge or governance, and on any relevant drift.

Match exactly one active grant to the authenticated stable account ID/login, responsibility `actor_id` and intended repository. Runtime, device and session identify this run; they are not grant keys. A same-actor new session may retain a valid role but needs verified task handoff/resume, not silent claim inheritance. Ambiguous identities need the user's choice.

| Verified state | Result |
| --- | --- |
| Account valid; no matching active grant | `member`, within account rights and protocol/task scope |
| Matching approved grant; account Maintain/Admin | `leader:<min(frozen ceiling, current permission)>`, within delegated scope, protections and current action approval |
| Account promoted | Ceiling unchanged |
| Account below Maintain | Leader ineffective immediately; at most Member/account scope |
| Source/account/authorization/protection unknown or conflicting | No dependent write; report unknowns |
| Direct user revocation | Stop affected writes now; retain history |

Grant, raise, restore or revoke persistent authority only through `github-collaboration-setup` under existing default-branch rules. A proposed/local/PR grant, `granted_by` label or shared-account statement cannot authorize itself, prove a human approval, stop an old process or bypass native GitHub review/protection.
