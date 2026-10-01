---
name: github-collaboration-setup
description: Use when initializing, upgrading, diagnosing, repairing, or governing GitHub Agent collaboration configuration in a repository.
metadata:
  version: "0.1.0"
---

# GitHub Collaboration Setup

Use this Skill for repository collaboration governance. It is not an Agent role grant: every Agent starts as Member. The project default branch supplies current protocol and persistent authorization; a working branch is only a proposal.

## First decision

Read [preflight and identity](references/preflight-and-identity.md) before any setup action. Discover the target repository, authenticated account, protection rules, project documents, and responsibility-based Agent identity with read-only operations. Resolve the configured authorization path from the same verified default-branch SHA as the project configuration. Record unknowns instead of guessing.

Choose exactly one mode for the current request:

| Mode | Use when | Initial boundary |
| --- | --- | --- |
| `initialize` | The repository has no active collaboration installation | Preflight, then Bootstrap eligibility and explicit creation approvals |
| `upgrade` | An installed protocol or template needs a new version | Inventory existing managed resources and show an incremental diff |
| `diagnose` | The user wants status, gaps, or a cause | Read-only findings; no authorization grant is needed |
| `repair` | Existing managed content is damaged or incomplete | Identify ownership and conflicts before proposing a repair |
| `authorization` | The user requests a Leader grant, ceiling change, revocation, or recovery | Verify current default-branch authority and the human grant |
| `remote-governance` | Labels, templates, Actions, checks, Rulesets, or branch protection need configuration | Inventory actual remote state and seek approval for each item |

For any write mode, use [authorization](references/authorization.md) to decide the Agent's effective role before proposing an action. For `initialize`, or `authorization` when the last Leader is lost, follow [bootstrap and recovery](references/bootstrap-and-recovery.md) after preflight. The current account's Admin or Maintain permission alone never grants this Agent Leader authority.

If the request concerns installing either Skill, choosing its platform path, or proving discovery, read [platform installation](references/platform-installation.md). For an existing package, local changes, an upgrade, or a discovery failure, also read [upgrade and diagnosis](references/upgrade-and-diagnosis.md). The installation route does not elevate the Agent or authorize a project governance write; use the mode and approval boundary above for any project change.

For `initialize`, `upgrade`, and `repair` touching local files, follow [local configuration](references/local-configuration.md) and its [managed-resource rules](references/managed-resources.md) after authorization. Populate the project README's context index from the project's existing requirement, specification, decision, progress and validation sources; unresolved entries stay unknown. If an earlier setup attempt was interrupted or its remote result is uncertain, use [resume and recovery](references/resume-and-recovery.md) before any retry. Diagnose may use these references to explain a problem, but remains read-only.

For `remote-governance`, first use the [managed-resource rules](references/managed-resources.md) to identify the stable remote resource, ownership baseline, and exact managed-field diff. Then follow [remote governance](references/remote-governance.md) for each item-specific discovery, approval, application and read-back. If Actions or server-enforced checks, reviews, Rulesets or branch protection are involved, also follow [Actions and Rulesets](references/actions-and-rulesets.md) before any triggering Push or setting change. If a prior remote result is uncertain, use [resume and recovery](references/resume-and-recovery.md) to query it before considering a retry. Continue to a mutation only when this package supplies the complete procedure for that remote resource; otherwise stop after the read-only proposal.

If the selected mode has no complete procedure in this package, report preflight findings and stop before writes. Do not improvise a governance mutation from this router.

## Write boundary

For every proposed write, calculate effective authorization from the Agent's explicit Leader delegation or narrowly scoped Bootstrap/Recovery grant, its frozen ceiling, the current GitHub account permission, the project's allowed scope, existing GitHub protections, and the user's approval of the current specific diff. Account Admin or Maintain alone never makes an Agent Leader. Unknown, stale, revoked, or conflicting evidence means no write.

Keep configuration work within the approved governance scope. Preserve existing `AGENTS.md`, `CLAUDE.md`, and other user files with reviewable incremental changes; when content ownership, duplicates, or conflict is ambiguous, show the alternatives and get the user's choice. A local edit, Commit, Push, PR, each remote setting, Actions enablement, and Required Check each have their own approval boundary. Re-read state before applying an approved change and verify the result afterward. Never weaken existing protection to complete setup.

This Skill can carry an approved setup or repair procedure when the daily `github-collaboration` Skill is absent. It does not authorize ordinary development work in that case.
