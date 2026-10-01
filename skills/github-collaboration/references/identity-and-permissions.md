# Identity and permission decision

Use after [daily preflight](preflight.md) identifies the target repository, pinned default-branch SHA, authenticated account and selected responsibility. This reference computes a decision; it does not itself grant permission to write. Recompute before formal review, merge or routing a governance change, and whenever any source or account state may have changed.

## Stable responsibility, not a running instance

`actor_id` names the responsibility, such as `backend-api` or `release-coordination`. The identity key is `controlled_by + actor_id`, with `controlled_by_id` matched to the authenticated GitHub account's stable numeric ID and `controlled_by` checked against its current login. `runtime`, device and `session_id` describe where the actor is running; they are not part of a Leader grant. Select the actor from the user's explicit choice, an explicitly bound environment, or a single unambiguous local identity. When several identities could apply, ask the user. Never infer an actor from a GitHub login, branch name or PR author alone.

Reject generic, role, platform, device, random-code or numeric-suffix actor names (`codex`, `claude-code`, `pi`, `leader`, `member-01`, `backend-api-01`, `laptop-a`). Ask the user for a descriptive responsibility name. A local `actors.yml` may hold identity bindings, but must not hold a token, role, ceiling or task state; show its exact contents before an authorized change. A new session may use the same identity but does **not** inherit an old session's active Issue claim or branch ownership. Existing ownership needs verified handoff/resume or Leader reassign followed by a new claim; a first uncontested claim requires neither. Old-session silence is not a release.

## Trusted Leader source

Start as `member` even when the authenticated account is Admin or Maintain. For a persistent Leader, follow [preflight](preflight.md): read and validate config from the verified repository's confirmed default branch at a recorded SHA, resolve its schema-valid `managed_paths.authorization` within the allowed governance directory, then read the authorization file at **that configured path from the same SHA**. Do not hard-code the template's usual filename or search alternative paths. Its repository `hostname`, immutable `repository_id` and `default_branch` must match the independently queried target. Verify `default_branch_source_sha` as provenance of the approved governance proposal and the approval evidence for that proposal and final HEAD; it is **not** assumed equal to today's default-branch HEAD after later commits. Recheck HEAD before use. A local copy, business PR branch, proposed authorization edit, `granted_by` text or stale cached result is not authority. Validate the complete record with the bundled authorization schema, Draft 2020-12 and `FormatChecker()`; malformed, duplicate or conflicting active grants fail closed.

Find exactly one current `active` delegation whose `controlled_by_id`, `controlled_by` and `actor_id` match this session's selected identity. `revoked` and `superseded` records stay in the history but confer nothing. Verify the human approval and governance PR evidence as the setup authorization procedure specifies. The grant's `permission_ceiling` is frozen at explicit approval; a later account promotion does not edit or increase it. This daily Skill cannot grant, restore, revoke or raise it. Route such a proposal to `github-collaboration-setup`, where a valid Leader or bounded human-approved recovery/escalation session must handle it under the existing default-branch rules.

## Decision table

Permission order: `read < triage < write < maintain < admin`. For Leader-only operations, the effective ceiling is the lower of the active delegation ceiling and a *fresh* account permission; the project protocol and GitHub Rulesets/branch protection can further prohibit the action. A Member has no Leader authority regardless of account Admin and is capped at the protocol's Member operations, with account rights still enforced. Role is not a substitute for Issue ownership, an active uncontested claim, user authorization, or review/check gates.

| Observed state | Decision |
| --- | --- |
| Current account query succeeds; no matching active delegation | `member`; account Admin/Maintain alone does not elevate. |
| One matching, approved active delegation; current account is Maintain or Admin | `leader:<min(frozen ceiling, current account)>`, subject to protocol and platform protection. |
| Former Admin Leader account falls to Maintain | Still Leader only up to Maintain; Admin actions stop immediately. |
| Leader account falls below Maintain | Leader becomes ineffective immediately: `member`, at most current account rights and Member scope. |
| Account permission query, repository/source validation, identity or authorization read fails or is ambiguous | `read-only` for writes; report the unknown and do not use cached elevation. |
| Delegation names another account, actor or repository | No Leader grant for this actor; if the trusted authorization file itself mismatches the target repository or branch, stop as `read-only`. |
| Default-branch direct push forbidden by a Ruleset or branch protection | No direct push, including for a Leader with Admin account permission. |

Before each formal Approve/Request Changes, merge, or governance referral, re-query account permission and re-read the current default-branch authorization and protection state. A credential or permission change takes effect in this calculation immediately, even if the default-branch record has not yet been revised. `write` or lower cannot act as Leader; if the account itself lacks required write or review rights, even ordinary Member work may be read-only for that operation. A direct human revocation received in the current session stops affected writes immediately; other sessions must refresh at preflight. Because credentials may be shared, this protocol cannot remotely terminate old sessions or bypass GitHub's own permission and protection decisions.
