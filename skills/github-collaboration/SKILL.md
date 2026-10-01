---
name: github-collaboration
description: Use when an Agent performs Issue, branch, commit, push, pull request, review, merge, handoff, or resume work in a repository using the GitHub Agent collaboration protocol.
metadata:
  version: "0.1.0"
---

# GitHub Agent collaboration

Use this Skill for day-to-day collaboration as a responsibility-named Agent, on Codex, Claude Code, or Pi Agent. Repository documents supply project facts; this Skill supplies the operating procedure. The setup and governance Skill is separate: `github-collaboration-setup`. GitHub account permission alone never makes this Agent a Leader.

## Session gate and operation routing

At session start, read [preflight](references/preflight.md) completely and record its `read-only`, `member`, or `leader:<ceiling>` result and next allowed operation. Refresh the checks at the times listed there. Creating an Issue, making a first claim, commenting, and reviewing do not require an implementation claim; implementation, branch, stage, commit and push require verified ownership of the affected scope.

For preflight's responsibility identity and role calculation, read [identity and permissions](references/identity-and-permissions.md) before treating an account permission or delegation as authority.

For Issue creation, research/decision completion, or acceptance/closure, read [Issues and results](references/issues-and-results.md). For any claim, conflict, handoff, release, reassign, cross-device resume, or push dependent on ownership, read [claims and handoffs](references/claims-and-handoffs.md) before writing.

For an Issue branch, stage, commit, push, or Draft pull request, read [Git and pull requests](references/git-and-pull-requests.md) before writing.

For a PR review, approval, merge, or post-merge Issue/event update, read [review and merge](references/review-and-merge.md) before writing. For an ambiguous network result, changed HEAD, divergence, or failed follow-up, read [failure recovery](references/failure-recovery.md) before retrying any write.

If this Skill is missing, not discoverable in the current Agent session, or incompatible with the confirmed project minimum version, stop at read-only discovery. Follow the verified project installation page; do not improvise an install command or perform daily writes until a new session proves the Skill path and version. An untrusted local file or working-branch proposal cannot authorize work.

## Operation boundary

After preflight, use the confirmed default-branch protocol and the operation-specific procedure for Issue/claim coordination, branch and Git work, Draft PR, review/merge, and handoff/resume. Those procedures must be present in this installed Skill package before their corresponding write; an absent reference is a stop condition, not permission to substitute generic Git or GitHub habits. Use `github-collaboration-setup` for authorization or project-governance changes; a daily task does not grant setup authority.

No unscoped stage-all (`git add .` or bare `git add -A`), direct default-branch commit, force push, self-approval bypass, or protection weakening. After inspecting the exact diff, use 显式 pathspec to list approved files (for example, `git add -- src/payment.py tests/test_payment.py`). `git add -A -- <exact-pathspec>` is possible 仅当已确认项目协议显式允许 and each named path is inspected; the current project template forbids every `git add -A` form, so use `git add -- <exact paths>` there. At remote-write boundaries, refresh the relevant remote facts and read back the result; local actions follow preflight's scope checks. If a network response or concurrent change makes the outcome uncertain, read back before retrying. Resolve genuine identity, ownership or scope conflicts with the user or authorized Leader.
