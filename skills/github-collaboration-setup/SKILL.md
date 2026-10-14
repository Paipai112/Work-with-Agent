---
name: github-collaboration-setup
description: Use when initializing, upgrading, diagnosing, repairing, or governing GitHub Agent collaboration configuration in a repository.
metadata:
  version: "0.2.0"
---

# GitHub Collaboration Setup

Client installation and project governance; no role grant. Agents default to Member.

## Choose the route

Installation/discovery loads [platform installation](references/platform-installation.md); existing/modified packages or faults also load [upgrade/diagnosis](references/upgrade-and-diagnosis.md). Exact directory-owner approval needs no project/Leader and covers no governance/Git action.

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

A project write uses preflight's current authority/scope/protection intersection and exact action approval; a plan, account Admin or check pass grants none. Unknown blocks dependent writes, not diagnosis.

Validate exact template candidates through same-version parser/schema/checker. Whole-entry review is not whole-file ownership; preserve external/dirty bytes, resolve overlap and Commit ownership. Separately approve file edit, Commit, Push, PR, each remote setting, Actions execution and Required Check. Refresh/apply/read back one item; no protection weakening or blind retry.

Missing procedures allow read-only proposals only. Setup/repair may finish without daily; ordinary development may not.
