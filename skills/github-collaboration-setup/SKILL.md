---
name: github-collaboration-setup
description: Use when initializing, upgrading, diagnosing, repairing, or governing GitHub Agent collaboration configuration in a repository.
metadata:
  version: "0.2.0"
---

# GitHub Collaboration Setup

This package handles client installation and project governance. It does not grant a role: every Agent starts as Member.

## Choose the route

For client package installation, platform paths or discovery, read [platform installation](references/platform-installation.md); existing/locally changed packages and faults also use [upgrade and diagnosis](references/upgrade-and-diagnosis.md). The directory owner approves the exact package proposal. No initialized project or Leader is needed; that approval covers no project-governance file or Git operation.

For project work start with [preflight and identity](references/preflight-and-identity.md), then select one mode:

| Mode | Load only the applicable procedure |
| --- | --- |
| `diagnose` | Read-only findings; no Leader grant required |
| `initialize` | [Authorization](references/authorization.md), [Bootstrap/recovery](references/bootstrap-and-recovery.md), then local procedures |
| `upgrade` / `repair` | [Authorization](references/authorization.md), [Local configuration](references/local-configuration.md), [Managed resources](references/managed-resources.md) |
| `authorization` | [Authorization](references/authorization.md); Bootstrap/recovery only when eligible |
| `remote-governance` | Authorization, managed resources, then [Remote governance](references/remote-governance.md) |
| Actions triggers, Required Checks/Reviews, Rulesets/protection | Also [Actions and Rulesets](references/actions-and-rulesets.md) |
| Interrupted attempt or uncertain result | [Resume and recovery](references/resume-and-recovery.md) before retry |

## Write boundary

A project write needs current effective Leader or explicitly bounded Bootstrap/Recovery authority, frozen ceiling, fresh account permission, delegated/project scope, existing protections and approval of the exact change/action. Account Admin/Maintain, a plan, proposed authorization or a passing check cannot supply that authority. Unknown evidence blocks affected writes; diagnose remains read-only.

Local configuration must validate actual edited template candidates through the bundled same-version parser/schema/check chain before deployment. Preserve user-owned bytes and dirty edits; whole-entry governance review grants no whole-file ownership. Resolve overlap and Commit ownership explicitly. File edit, Commit, Push, PR, each remote setting, Actions execution and Required Check are separate approval boundaries. Refresh before applying one item and GET/read back afterward; never weaken protection or blindly retry.

Missing procedures stop at a read-only proposal. This package can finish approved setup/repair while daily is absent; it cannot authorize ordinary development in that state.
