# Install an independent collaboration package

Follow [package verification](package-verification.md); existing packages/faults add [upgrade/diagnosis](upgrade-and-diagnosis.md). Install one complete package, never lone SKILL.md/nested same-name directory. Project/Git changes separately need [preflight](preflight-and-identity.md).

## 安装作用范围与会话安全

User discovery affects all projects: disclose it and setup's explicit invocation. Inspect symlinks/collision/overrides/trust **before opening** a worktree; checkout can auto-load instructions. Verified content is required even without script execution. Package approval grants no role/global-rule edit.

## Locations and invocation

Use selected `<skill>`; project location needs explicit choice. Windows native ≠ Linux/WSL; nine `tests/platform/install-contract.yml` contracts are not native results.

| Client | macOS/Linux user | Windows native PowerShell user | Project relative root | Explicit invocation |
| --- | --- | --- | --- | --- |
| Codex | `~/.agents/skills/<skill>/` | `Join-Path $env:USERPROFILE '.agents\skills\<skill>'` | `.agents/skills/<skill>/` | `$<skill>` or Skill picker |
| Claude Code | `~/.claude/skills/<skill>/` | `Join-Path $env:USERPROFILE '.claude\skills\<skill>'` | `.claude/skills/<skill>/` | `/<skill>` |
| Pi Agent | `~/.pi/agent/skills/<skill>/` | `Join-Path $env:USERPROFILE '.pi\agent\skills\<skill>'` | `.agents/skills/<skill>/` | `/skill:<skill>` |

`Join-Path` returns a path; `$<skill>` is a Codex prompt, not PowerShell. Spaces require literal paths; `Test-Path -LiteralPath` before copy, existing target uses upgrade choice. Approved new target: create parent, `Copy-Item -LiteralPath <verified-package> -Destination <target> -Recurse`. macOS/Linux also checks target first.

### 各客户端的发现边界

- Codex scans user and CWD-to-root `.agents/skills/`; check supported existing paths and `[[skills.config]] enabled=false`. Same names do not merge. [Official Skills](https://learn.chatgpt.com/docs/build-skills), [native Windows](https://learn.chatgpt.com/docs/windows/windows-app).
- Claude scans user, repository/nested `.claude/skills/` and parents to root. Enterprise/user precedence can override project names; inspect `/skills`, `skillOverrides`, permissions/frontmatter restrictions. AGENTS.md does not replace CLAUDE.md. Directory watching does not replace this protocol's new-session test. [Skills](https://code.claude.com/docs/en/skills), [Windows](https://code.claude.com/docs/en/setup#set-up-on-windows).
- Pi coding agent uses `~/.pi/agent/skills/`, shared `~/.agents/skills/`, project `.pi/skills/` and CWD-to-root `.agents/skills/`; same names warn and first discovered wins. Check project trust, `--no-skills`, `enableSkillCommands`, added `skills` paths. Native Windows tools may use Git Bash/PowerShell, while install paths remain Windows user paths. [Skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md), [Windows](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/windows.md), [trust/config](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/README.md).

## Verify actual discovery

Use package verification's new-session record/testing, including architecture and native/WSL. Native Windows additionally tests PowerShell paths, required Git for Windows, CRLF/BOM. Missing/colliding/disabled/untrusted remains FAIL/UNVERIFIED, not menu/copy success.

Pi project default: `.agents/skills/`. macOS/Pi 0.87.1 (2026-10-01): root `.pi/skills/` worked only from root; `.agents/skills/` worked root/nested/spaces. Report existing `.pi/skills/`, never auto-move/duplicate; no other OS/version is proven. The old badlogic/pi-mono URL redirected to earendil-works/pi (2026-09-26); verify current official behavior.
