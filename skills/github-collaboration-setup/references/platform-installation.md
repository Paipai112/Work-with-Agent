# 安装两个协作 Skill

用于 `github-collaboration-setup` 的安装，以及向项目参与者说明如何安装日常 `github-collaboration`。开始前先按 [预检与身份](preflight-and-identity.md) 确认项目和客户端；已有包的处理见 [升级与诊断](upgrade-and-diagnosis.md)。安装 Skill 本身不授予 Leader 权限，也不修改 Agent 全局规则。

## 先确定来源和目标

1. 记录客户端名称、确切版本、macOS/Linux/Windows native、当前工作目录和仓库根目录。Windows 下若 Agent 实际运行在 WSL，按独立的 **Linux/WSL** 环境记录、安装、测试；不能算 Windows native 通过。
2. 使用维护者指定、当前用户可访问的**真实发行仓库 URL、Release 标签、该标签解析后的完整 Commit SHA**；发行仓库可以公开或私有，私有仓库访问权不等于开源许可。核对 GitHub 仓库身份、Release 与 Commit 指向，取得该 Commit 的只读源树；运行仓库的包校验，并记录两个完整 Skill 目录各自的文件清单和 SHA-256 摘要。拒绝搜索结果、未经核验的 Fork、浮动 `main`、只给标签而没有 Commit、缺少资源的单文件下载。发布 URL/Commit 尚未确定时，以“待发布”报告并停止安装，不能把候选项目配置当作已完成配置。
3. 列出当前用户级、项目级、插件/包/设置添加的发现位置，已有同名 Skill、实际生效路径、版本和禁用/覆盖设置。先检查目标路径是否已存在或是符号链接，以及现有文件是否与记录的发布摘要相符；不因想安装新包而覆盖已修改的目录。默认使用**复制完整目录**，保留 `SKILL.md`、`references/`、`assets/`、`scripts/`、`agents/` 与 `RESOURCE_MANIFEST.json`（存在的文件）；不依赖源码仓库仍留在用户机器上，也不要求符号链接权限。
4. 给用户一份具体安装提案：来源 URL、Release、完整 Commit SHA、包摘要、Skill 名称、客户端/版本、目标目录、已有同名项及差异、计划复制的文件、所需批准。取得批准后才复制。目标不存在时建立父目录并复制到**精确目标目录**；目标已存在时按升级流程提出选择，不做合并、清空或覆盖。复制后重新计算目标摘要。

项目目录里的 `.github/agent-collaboration/INSTALL_SKILL.md` 是参与者的固定安装入口。仅当维护者指定的发行仓库 URL、Release 标签、完整 Commit SHA 及该 Commit 上的安装页永久链接均已确认且相互一致时，才将日常 Skill 的这些真实发布信息填入经审阅的项目候选差异。四项未完成或无法核验时，应标记安装入口“待发布/不可安装”并阻断“配置完成”声明，不能虚构可用链接；私有来源还需确认参与者的访问权限。配置 Skill 即使在日常 Skill 缺席时仍可执行**已授权的治理配置/修复**；普通开发写操作仍须等日常 Skill 可用。

## 安装位置和显式调用

下表的 `<skill>` 分别替换为 `github-collaboration-setup` 或 `github-collaboration`，一次只处理一个包。项目级位置仅在明确选择把 Skill 放进该仓库时使用；通常向多个项目提供日常 Skill 选用户级。具体九组合机器可读合同见发布仓库 `tests/platform/install-contract.yml`，**合同不是九组合实测结果**。

| 客户端 | macOS/Linux 用户级 | Windows native PowerShell 用户级 | 项目级（相对仓库根） | 显式调用 |
| --- | --- | --- | --- | --- |
| Codex | `~/.agents/skills/<skill>/` | `Join-Path $env:USERPROFILE '.agents\skills\<skill>'` | `.agents/skills/<skill>/` | `$<skill>`，或在 Skill 选择器中选定 |
| Claude Code | `~/.claude/skills/<skill>/` | `Join-Path $env:USERPROFILE '.claude\skills\<skill>'` | `.claude/skills/<skill>/` | `/<skill>` |
| Pi Agent | `~/.pi/agent/skills/<skill>/` | `Join-Path $env:USERPROFILE '.pi\agent\skills\<skill>'` | `.agents/skills/<skill>/` | `/skill:<skill>` |

PowerShell 示例中的 `Join-Path` 返回**路径**；`$<skill>` 是上表 Codex 提示词记法，不是 PowerShell 命令。实际复制时从上述表选择一个目标，以 `Test-Path -LiteralPath` 查是否存在；目标已存在就停止进入升级流程。若为新目标，可用 `New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force` 建立父目录，再用 `Copy-Item -LiteralPath $verifiedSkillDir -Destination $target -Recurse` 复制**经核验的完整目录**。将含空格路径始终作为一个参数传给 `-LiteralPath`。macOS/Linux 同样先检查目标不存在，再建立父目录并用保留目录结构的复制操作；不要把两个包嵌套进一个同名目录。

### 各客户端的发现边界

- **Codex**：官方当前文档列出用户 `~/.agents/skills/` 及从当前目录向仓库根逐级扫描的 `.agents/skills/`。同名 Skill 不合并，可能同时显示。还要检查既有受支持安装位置和 `~/.codex/config.toml` 中 `[[skills.config]]` 的 `enabled = false`；仅报告禁用和建议，不暗改全局配置。[Codex Skill 官方文档](https://learn.chatgpt.com/docs/build-skills)；[Windows native Agent 文档](https://learn.chatgpt.com/docs/windows/windows-app)。
- **Claude Code**：官方列出用户 `~/.claude/skills/`、仓库及嵌套 `.claude/skills/`；从子目录启动会读父级到仓库根。`/name` 同名时可能由更高优先级的用户/企业版本接管，项目版不能仅凭目录存在判定生效。检查 `/skills`、`skillOverrides`、Skill 工具权限及 frontmatter 的调用限制。Claude Code 会监视已有 Skill 目录变化，但本协议仍要求**新会话**作为可重复验收。Claude Code 不会把 `AGENTS.md` 当成 `CLAUDE.md` 的自动替代。[Claude Code Skill 官方文档](https://code.claude.com/docs/en/skills)；[Windows native 安装](https://code.claude.com/docs/en/setup#set-up-on-windows)。
- **Pi Agent**：这里指原 `badlogic/pi-mono` 仓库的 Pi coding agent；旧仓库 URL [目前重定向](https://github.com/badlogic/pi-mono)到维护中的 `earendil-works/pi`，本页核对日期 2026-09-26。Pi 支持用户 `~/.pi/agent/skills/`、共享 `~/.agents/skills/`、项目 `.pi/skills/` 及从当前目录向仓库根扫描 `.agents/skills/`；已在共享路径发现同版时先复用，避免重复。Pi 同名警告并保留先发现的版本，不能假定目标包获选。检查项目信任、`--no-skills`、`enableSkillCommands`、设置中的附加 `skills` 路径及启动诊断。Windows native 的 Pi 默认用 Git Bash 执行 Bash 工具，也可选 PowerShell 工具；其 Skill **安装路径仍是 Windows 用户目录**。WSL 中则使用 Linux 家目录。[Pi Skill 官方文档](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)；[Pi Windows 官方文档](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/windows.md)；[Pi 项目信任与配置](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/README.md)。

## 新会话验收

Pi 的项目级默认选共享 `.agents/skills/`，以便从仓库嵌套目录继续工作。2026-10-01 的 macOS／Pi 0.87.1 原生加载器实测中，根目录 `.pi/skills/` 只在从根目录启动时被发现，从 `nested/child` 启动不会向上发现它；根目录 `.agents/skills/` 在根、嵌套和含空格目录均可发现。若明确固定从仓库根启动，可另外选择 `.pi/skills/`，但不能据此声称嵌套目录可用。已有 `.pi/skills/` 安装先报告实际路径和此边界，不自动移动或额外复制同名包。该实测不代替 Linux／Windows 原生验证，也不代替下述完整新会话验收。

在每个计划支持的客户端/操作系统组合上记载**真实运行**的客户端版本、OS/架构、native 或 WSL、来源 Commit、安装摘要、目标路径、实际发现路径及验证时间。分别从仓库根、嵌套目录、含空格路径的新会话运行显式调用，要求 Agent 报告其实际读取的 `SKILL.md` 路径、版本、可打开的相对 `references/`、`assets/`、`scripts/` 资源，以及项目入口文件位置。仅“命令出现在菜单”或“文件在磁盘上”不算通过。若发现了别的同名包、入口被覆盖/截断、Skill 禁用或项目未信任，记录失败及实际路径；按 [诊断](upgrade-and-diagnosis.md) 提议修复，不能宣称兼容。Windows native 还需实际检查 PowerShell 路径、Git for Windows（客户端需要时）、CRLF、UTF-8 BOM；WSL 结果单列。
