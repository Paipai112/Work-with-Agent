# Claims, handoffs, and reassignment

Read [preflight](preflight.md) and [identity and permissions](identity-and-permissions.md) first. An Issue comment is audit evidence, never an atomic lock. Timestamp, silence and successful posting do not establish ownership or stop a process.

## Verify every event

Validate event bodies with the installed Skill's `references/schemas/collaboration-event.schema.json`, using `Draft202012Validator` and `FormatChecker`. A missing/invalid/incompatible bundled schema means read-only; a working-tree schema cannot replace it. Schema validation checks structure, not authorship, authorization, process state or scope conflicts.

Fetch the real GitHub Issue comment and verify hostname, immutable `repository_id`, owner/name, Issue number, actual ID/URL, and `user.id`/`user.login` against top-level `controlled_by_id`/`controlled_by`. Fetch predecessors in the same repository/Issue and compare their actual IDs/URLs and `event_id` with the links. Resolve edited, duplicate or contradictory events before relying on them. For handoff/resume/release/reassign, `github_comment_id` and `github_comment_url` identify the already-published predecessor, never the event being drafted. Capture the new comment's own ID/URL after posting and carry it forward.

## Claim an Issue scope

1. Verify an open Issue and this actor/session binding. Search related Issues, PRs, branches and claim/handoff/release/resume/reassign records for overlapping scope, including other sessions of the same identity. A first claim requires no prior owned claim. Resolve a missing Issue using [Issues and results](issues-and-results.md).
2. For an uncontested scope, fill [claim.yml](../templates/events/claim.yml) or [research-claim.yml](../templates/events/research-claim.yml) with a unique `event_id`. A code claim names a proposed Issue branch and verified base SHA; actual branch creation follows claim read-back. Branchless research names its result scope. Use `previous_event_id: null` only for a first claim; a successor claim references the verified terminal handoff/release or reassign event and its actual comment ID/URL.
3. Validate, post and capture the comment ID/URL. Re-read it and all related claims/PRs with the envelope checks. An uncertain response requires read-back before retry. Treat the scope as owned only when identity, session, scope and branch agree and no unresolved competing allocation exists. Otherwise stop affected implementation for Leader resolution; a later comment is not the winner.

Pure local subagents may use the parent's explicitly delegated scope without separate GitHub claims; the publisher owns their scope, review and GitHub write responsibilities. Any subagent independently writing to GitHub must establish its own identity and claim where that operation requires one.

## Self-release, handoff and same-branch resume

The current owner publishes [handoff.yml](../templates/events/handoff.yml) or [release.yml](../templates/events/release.yml), linking the previous event and recording remaining work and intended successor. `release_mode: self` requires the real author/account and actor to match the old claim; a Leader cannot post release as another owner. Code handoffs record verified branch/HEAD. Research handoff/release/resume omit Git fields and carry `artifact_urls` to durable results/progress. Release changes allocation, not credentials or process state.

A new session does not inherit an active claim. For same-account/same-actor [resume.yml](../templates/events/resume.yml), verify an original-session handoff that relinquishes further writes, or the current user's direct confirmation that the named old process stopped. In the latter case record that confirmation and publish/read back a self-release under the original account/actor before resume. A shared-account GitHub comment cannot distinguish a human from an Agent and is not independent stop evidence. Link `previous_event_id` and `handoff_event_id` to the terminal handoff or self-release (including its actual comment ID/URL), verify the same branch/current HEAD, and re-read competing records after posting. A different actor posts a new claim. If process safety remains unknown, use the reassignment path below with an independent branch.

## Leader reassignment

An approved allocation decision can supersede a stale claim without claiming its process stopped. Refresh the Leader's own current authorization from the configured default-branch path and current account permission. Read back the approval evidence and targeted claim, then publish [reassign.yml](../templates/events/reassign.yml) under the **Leader's own** account/actor/session. This is a distinct `reassign` event, not proxy `release`.

- `target` identifies the old claim's event/comment ID/URL, controlling account, actor and session. Its scope and (for code) top-level branch/base describe the old allocation; the predecessor link names the latest valid event in that claim's lineage.
- `successor` names the intended new controlling account, actor and session. `approval_url` and `reason` record the approved allocation decision. Verify the approval's real envelope and applicable authority; a URL alone proves neither human authorship nor process termination.
- `old_process_status` is `unknown` with `stop_evidence: null`, or `stopped` with independently verified stop evidence. A Leader's own assertion, timeout or account-shared comment cannot establish stop. Record allocation and stop facts separately.
- Read back the event, current Leader delegation/permission, target lineage and approval. A valid reassign supersedes that old allocation for its exact scope. The successor publishes a new claim referencing the reassign and reads it back; reassign itself is not the successor's claim.
- When the old process is unknown, preserve the old branch and use a distinct new Issue branch from a verified default or approved integration baseline. Do not resume or push to the old branch, reuse its worktree, or claim remote termination. Inspect any selected old commits before separately integrating them. Every later session must validate the reassign's author/current authority, predecessor and successor claim; a restored old session stops writes to its superseded scope. If current authority or lineage cannot be verified, keep the affected scope read-only pending resolution, rather than reviving the old claim.

Research reassignment also requires a new claim and separate durable result lineage. It never turns unknown process state into termination proof. Contradictory reassignments or claims remain a coordination conflict.

## Immediately before each push

Re-read active claims, reassignments and related Issue/PR records; fetch the target branch and compare its remote HEAD with the expected SHA and verified base. Changed ownership, scope, permission or HEAD stops the push. Preserve both histories and coordinate; never force-push or blindly retry an uncertain response. Read back remote HEAD and event state afterward. No event overrides GitHub protection or current account permission.
