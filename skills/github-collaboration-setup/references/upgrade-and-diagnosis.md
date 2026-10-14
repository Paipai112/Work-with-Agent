# Package upgrade and discovery diagnosis

Use [platform installation](platform-installation.md) and conditional [package verification](package-verification.md). Diagnosis is read-only. Package approval covers no project/Git edit; those need project procedures. Package-only installation reports project status not applicable.

## Inventory → approved replacement

1. Record client/OS/version, native/WSL, CWD/target and project minimum versus discovered/proposed package.
2. Inventory supported/added roots, same-name paths/versions/full source inventory/digests, trust/disable/overrides and symlinks. Missing baseline/local edits mean unknown/conflict, not standard release. Manifest excludes no unlisted instructions.
3. Verify candidate source/full bytes. Show baseline/current/candidate digests, exact added/replaced/preserved files, effects/precedence; choose retain, independent supported path, reviewed merge or named replacement, never auto-merge same names.
4. Exact source/target/current/candidate approval; re-read (drift invalidates). Validate in separate staging, back up whole old package outside discovery, process one target; failure stops subsequent packages. Unpublished source allows proposals only.
5. Package verification's new-session test must prove actual path/version/resources/directory coverage. Unmet project minimum stops daily writes.

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

Report PASS/FAIL/UNVERIFIED with client/session/path/source/digest/directory/evidence; no machine test means UNVERIFIED, not static-contract compatibility. Platform installation links current sources.

## Rollback

Follow package verification's exact approved whole-digest restoration, then new-session validate. Missing/mismatched backup, fresh edits or unknown discovery/precedence needs a choice, never automatic discard. Project entry/minimum-version downgrade is separate governance.
