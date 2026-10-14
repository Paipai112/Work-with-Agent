# Package upgrade and discovery diagnosis

Use [platform installation](platform-installation.md) and conditional [package verification](package-verification.md). Diagnose is read-only. Exact directory-owner approval covers package installation only; project entry/config/authorization and Git changes separately use project preflight/authorization/local configuration. No project is required for user-package installation; report its project position as not applicable.

## Inventory → approved replacement

1. Record actual client/OS/version, native/WSL, CWD and target. For an existing project compare trusted required name/minimum version, actual discovered package and proposed version.
2. Enumerate supported/added discovery roots, same-name paths, versions, source/full file inventories/digests, trust/disable/override and parent/target symlinks. Missing old digest/source or local changes are unknown/conflict, not standard old release. Manifest covers listed resources only; whole-package inventory includes instructions.
3. Verify proposed fixed repository/tag/commit/permalink and full bytes. Show current/old verified baseline/candidate digest and exact added/replaced/preserved files, project/client effects and precedence. Offer retain, explicitly chosen independent supported path, reviewed merge or named-target replacement; never merge same-name packages automatically.
4. Bind approval to exact source/target/current/candidate digests. Re-read before copying; drift invalidates approval. Validate in separate staging, back up old full directory/digest outside auto-discovery, then process one approved target. Copy/check failure stops subsequent packages. Pending/unpublished source permits proposals only.
5. New-session test proves actual path/version/all resources and intended project directory coverage. Unsatisfied project minimum still stops dependent daily writes.

## Fault diagnosis

| Observation | Read-only evidence and next proposal |
| --- | --- |
| No invocation | Supported path/frontmatter/new session; actual package and version from root/nested |
| Pi works root, not nested | Root .pi/skills may not scan upward; verify root or propose exact .agents/skills migration after collisions/local-change review |
| Wrong same-name package | Enumerate precedence/source; Codex no merge, Claude enterprise/user/project overrides, Pi first-discovered warning; user chooses |
| Visible, not selected | Description/explicit call, Codex skills.config, Claude skillOverrides/permissions, Pi --no-skills/enableSkillCommands; report before global setting proposal |
| Missing project entry | CWD/root/nested and existing overrides; Codex/Pi AGENTS.md versus Claude CLAUDE.md. Managed-block diff, not silent substitution |
| Missing resources | Full fixed-source inventory/relative refs; local edits need choice before completion |
| Native Windows fails, WSL passes | Separate client/user-directory/shell/project records; Windows USERPROFILE/literal paths are not Linux ~ |

Report PASS/FAIL/UNVERIFIED with actual client/session/path/source/digest/directory/evidence; no machine evidence means UNVERIFIED. Static nine-platform contracts are not tested compatibility. Current platform sources are linked in platform installation.

## Rollback

Verify recorded old backup inventory/full digest, current target and actual discovery/precedence. Show current → old exact restoration, affected clients/projects and named target; get explicit approval, restore that target only, rehash and new-session validate. Missing/mismatched backup, fresh user edits or unknown precedence needs a choice; no automatic deletion/discard or success claim. Project entry/minimum-version downgrade is a separate governance proposal.
