# Preflight and identity

Use this reference at the start of every setup mode. The preflight itself is read-only; a user's request to configure the project is not approval to mutate Git or GitHub.

## Establish the target

1. Confirm the project directory and whether it is a Git worktree, an uninitialized directory, or a repository without a GitHub remote. Read local status, current branch, default-branch evidence, tracked and untracked paths, and pending edits. Do not open or print secret values to inspect them.
2. Resolve the GitHub host and repository from authenticated remote/API evidence. Record immutable repository ID, owner/name, default branch, and its current commit SHA. Treat a URL or folder name alone as a hint, not verified identity. If local and remote identity conflict, stop with the discrepancy.
3. Query existing branch protection, Rulesets, required reviews/checks, Actions configuration, and managed resources before proposing any change. Record whether the default branch is protected and whether the authenticated account can read each relevant setting. Unknown is not permission.
4. At that recorded default-branch SHA, read `.github/agent-collaboration/config.yml` and validate it with the bundled config schema. Resolve `managed_paths.authorization` and `managed_paths.protocol`, then read those exact repository-relative paths at the **same SHA**. Reject invalid paths, missing selectors and mixed revisions; never fall back to a hardcoded authorization path. Worktree, integration-branch and PR-branch copies cannot grant current authority. An absent configured authorization file, a revoked last Leader, an unreadable file and an invalid/missing installed config are distinct conditions. For a first installation with no config, inventory prior governance and require explicit Bootstrap eligibility; choose the proposed paths in the reviewed setup diff. An unreadable or damaged installation is not proof that authorization never existed.
5. Locate existing project context from the repository's own README/entry files, documents and linked GitHub records. Identify the authoritative PRD/requirements, SPEC/design, decisions, progress and validation locations and record conflicts or missing access. Prepare only source pointers for the project README index; do not reconstruct or duplicate their facts. The write procedure is in [local configuration](local-configuration.md).

## Resolve the person, account, and Agent

The v0.1 config schema keeps `protocol`, `authorization` and `managed_resources` inside `.github/agent-collaboration/`. Custom filenames are allowed there; an incompatible existing location needs an explicit, reviewed repair, not an automatic move or fallback.

- Identify the authenticated GitHub account and its stable account ID; verify its current permission on this repository. `Admin` and `Maintain` are GitHub account permissions. The Agent remains Member unless a valid project delegation or explicit, scoped human Bootstrap/Recovery grant applies. If the permission lookup is unavailable, leave it unknown and stop before writes.
- Resolve `actor_id` from the user's explicit choice, an explicit environment binding, or one unambiguous local identity. Use a responsibility name such as `release-coordination`, not a device or platform code. Record the controlling account (`controlled_by`) separately. The same responsibility may continue on another device only after fresh account and task-state checks.
- For an existing repository without active authorization, verify the account is at least Maintain before requesting a scoped Bootstrap Leader grant. For an existing installation, compute the effective permission as the intersection of the active default-branch delegation, its frozen ceiling, the account's current permission, protocol scope, and GitHub protections. An account upgrade never raises the frozen ceiling automatically. A lost last Leader requires a distinct scoped Recovery grant; do not remove authorization history to make it look like first installation.
- If multiple Agent identities or accounts fit, or the current session grant is not explicit, ask the user to select one. Never infer a Leader grant from account ownership, a Skill invocation, or a draft authorization change.

## Missing prerequisites

- If the user has no GitHub account, give the official [GitHub signup](https://github.com/signup) link and pause remote setup. If the account is not authenticated locally, guide browser-based `gh auth login --web` and recheck identity afterward.
- Never ask for a Classic Token or any token in chat, and never run or display `gh auth token`. If browser login is unavailable, explain secure local credential entry as a fallback without echoing the secret; a fine-grained PAT is preferable to a Classic PAT when supported. If a token appears in chat or logs, stop using it and advise revocation.
- If Git, a remote, or the GitHub repository is absent, report the proposed initialization steps and missing owner/name/visibility choices. Obtain separate approval before local Git initialization, repository creation, the minimal initial Commit, and Push. After creation, verify the actual account permission; if it is below Maintain, stop configuration and report the created resource without deleting it.
- The only direct default-branch exception is an approved minimal first commit needed to establish a default branch. Show its exact path list, scan for credentials and large or generated files, and exclude governance content such as workflow and persistent authorization. Existing history and protections still apply.

## Preflight result

Return a concise inventory: selected mode; project path and Git state; verified host/repository ID/default branch/SHA; authenticated account ID and current permission; selected `actor_id`; current active delegation or scoped session grant; effective permission or reason it is unknown; existing protections and managed files; missing facts; and the next safe action. A diagnostic request ends with findings. For a write mode, continue only under the mode's complete procedure and the user's approval of its exact proposed changes.
