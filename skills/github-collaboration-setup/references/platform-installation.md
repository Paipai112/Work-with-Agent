# Install an independent collaboration package

Use [package verification](package-verification.md) for fixed source, full bytes/manifest, directory ownership approval and new-session validation. Existing packages/faults use [upgrade/diagnosis](upgrade-and-diagnosis.md). Package installation needs no project/Leader; project-governance changes separately use [preflight](preflight-and-identity.md). Install one named complete package, never a lone SKILL.md or nested same-name directory.

## 安装作用范围与会话安全

User-level discovery affects all projects for that client/user. Disclose implicit discovery and setup's explicit-invocation policy in the proposal. Inspect symlinks, same-name collision/overrides and trust **before opening** the worktree: checkout alone can auto-load instructions. Begin from verified content; not executing scripts is insufficient proof of trust. Package approval grants no role/global-rule edit.

## Locations and invocation

Replace `<skill>` with the selected package name. Project paths require an explicit project-level installation choice. Windows native and Linux/WSL are separate; nine static contracts in `tests/platform/install-contract.yml` are not nine native test results.

| Client | macOS/Linux user | Windows native PowerShell user | Project relative root | Explicit invocation |
| --- | --- | --- | --- | --- |
| Codex | `~/.agents/skills/<skill>/` | `Join-Path $env:USERPROFILE '.agents\skills\<skill>'` | `.agents/skills/<skill>/` | `$<skill>` or Skill picker |
| Claude Code | `~/.claude/skills/<skill>/` | `Join-Path $env:USERPROFILE '.claude\skills\<skill>'` | `.claude/skills/<skill>/` | `/<skill>` |
| Pi Agent | `~/.pi/agent/skills/<skill>/` | `Join-Path $env:USERPROFILE '.pi\agent\skills\<skill>'` | `.agents/skills/<skill>/` | `/skill:<skill>` |

`Join-Path` returns a path; Codex's `$<skill>` is a prompt, not PowerShell. Use literal path arguments for spaces; `Test-Path -LiteralPath` first, existing targets stop for upgrade choice. A new approved target may create its parent and `Copy-Item -LiteralPath <verified-package> -Destination <target> -Recurse`. macOS/Linux likewise checks exact target before complete directory copy.

### 各客户端的发现边界

- Codex scans user and CWD-to-root `.agents/skills/`; check supported existing paths and `[[skills.config]] enabled=false`. Same names do not merge. [Official Skills](https://learn.chatgpt.com/docs/build-skills), [native Windows](https://learn.chatgpt.com/docs/windows/windows-app).
- Claude scans user, repository/nested `.claude/skills/` and parents to root. Enterprise/user precedence can override project names; inspect `/skills`, `skillOverrides`, permissions/frontmatter restrictions. AGENTS.md does not replace CLAUDE.md. Directory watching does not replace this protocol's new-session test. [Skills](https://code.claude.com/docs/en/skills), [Windows](https://code.claude.com/docs/en/setup#set-up-on-windows).
- Pi coding agent uses `~/.pi/agent/skills/`, shared `~/.agents/skills/`, project `.pi/skills/` and CWD-to-root `.agents/skills/`; same names warn and first discovered wins. Check project trust, `--no-skills`, `enableSkillCommands`, added `skills` paths. Native Windows tools may use Git Bash/PowerShell, while install paths remain Windows user paths. [Skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md), [Windows](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/windows.md), [trust/config](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/README.md).

## Verify actual discovery

Use package verification's real new-session record: exact client/OS/architecture/native-or-WSL, commit/digest, target/actual discovered path and time; open all relative resources. Configured projects test root/nested/space-containing paths and proper entry; package-only install needs no invented entry. Native Windows adds PowerShell paths, Git for Windows when needed, CRLF/BOM. Menu visibility/copying is not loading proof; missing/colliding/disabled/untrusted states stay FAIL/UNVERIFIED.

Pi project default is shared `.agents/skills/`. Recorded macOS/Pi 0.87.1 (2026-10-01) found root `.pi/skills/` from root only, whereas `.agents/skills/` worked root/nested/spaces. Existing `.pi/skills/` is reported, never automatically moved/duplicated; this observation proves no other OS/version. The old badlogic/pi-mono URL redirected to earendil-works/pi at the 2026-09-26 check; runtime behavior follows current official sources.
