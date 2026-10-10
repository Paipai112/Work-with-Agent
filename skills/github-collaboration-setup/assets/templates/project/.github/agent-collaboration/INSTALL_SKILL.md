---
installation_status: unpublished
source_repository_url:
release_tag:
resolved_commit_sha:
installation_page_permalink:
---

# 安装日常协作 Skill

> 当前状态：未发布。此文件是待配置的项目模板，**不可执行安装，也不可宣称配置完成**。
> 项目负责人需先提供并核验下列真实发布信息，再按项目文件增量配置流程展示此文件与入口
> 文件的差异，由有权 Leader 和用户分别批准相应改动。不要覆盖已有文件或删除原有说明。

发布前必须填入并相互核对：

- `source_repository_url`：维护者指定、当前用户可访问的真实发行仓库 URL（公开或私有）；
- `release_tag`：实际发布的固定版本标签；
- `resolved_commit_sha`：该标签解析后的完整 40 位 Commit SHA；
- `installation_page_permalink`：同一 Commit 上安装页的永久链接。

私有仓库的访问权限不等于开源许可；参与者需有权访问该来源，并在项目获授权的范围内使用。

四项任一缺失、互不一致或 `installation_status` 仍为 `unpublished` 时，Agent 只能读取、
诊断并提出安装方案；不能执行下列安装步骤，也不能将本项目报告为协作配置完成。

发布信息经核验且安装单项获得批准后，安装固定发布版本 `github-collaboration` `0.1.1`；
升级时先比较来源、目标目录和本地修改，再在新会话中验证实际发现路径。不要从搜索
结果、网页广告或未核验 Fork 安装。项目模板不内置运行时 Skill。

## 安全登录

需要网页登录时，只在浏览器地址栏中手动打开经核验的官方站点并完成交互式登录。不要向
Agent、终端历史、Issue、PR、配置文件或聊天粘贴密码、一次性验证码、Cookie、会话令牌、
访问令牌或 SSH 私钥。遇到重定向、权限请求或来源不匹配时停止并由用户确认。

## Codex

将经核验的 `github-collaboration` `0.1.1` 发布包安装到
`~/.agents/skills/github-collaboration/`（若已有受支持安装器发现了其他路径，先验证而不
重复安装）。新会话从项目根目录显式调用 `$github-collaboration`，确认实际路径和版本。

## Claude Code

将同一固定版本安装到 `~/.claude/skills/github-collaboration/`。新会话从项目根目录调用
`/github-collaboration`，确认实际路径和版本；不要假定 `AGENTS.md` 会自动替代
`CLAUDE.md`。

## Pi Agent

将同一固定版本安装到 `~/.pi/agent/skills/github-collaboration/`。若已验证 Pi 使用共享
`~/.agents/skills/`，复用该目录并避免重复安装。新会话调用
`/skill:github-collaboration`，确认实际路径、版本和上下文启用状态。Windows 原生环境请
使用 PowerShell 的用户目录路径；WSL 是独立环境，须单独验证。
