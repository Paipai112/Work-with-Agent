---
installation_status: unpublished
source_repository_url:
release_tag:
resolved_commit_sha:
installation_page_permalink:
---

# 安装来源

候选版本 `0.2.0` 尚未发布：**不可执行安装，也不可宣称配置完成**。四项真实发布字段需相互核验：可访问的发行仓库 URL、固定标签、标签解析的完整 40 位 Commit SHA、同 Commit 安装页永久链接。缺失/不一致或 unpublished 仅允许只读诊断/方案；私有访问不代表开源许可。

## 参与者安装

取得目标目录拥有者对精确固定来源/完整包摘要/目标路径的批准后，复制所需的完整独立包；同名、本地修改、符号链接或未知来源先解决。包安装不授予 Leader，不涵盖项目治理文件或 Git 操作。已有可信验证记录未漂移时复用，不为每次本地动作重新下载。

| 客户端 | 默认用户目录 | 新会话显式调用 |
| --- | --- | --- |
| Codex | `~/.agents/skills/<skill>/` | `$<skill>` |
| Claude Code | `~/.claude/skills/<skill>/` | `/<skill>` |
| Pi Agent | `~/.pi/agent/skills/<skill>/` | `/skill:<skill>` |

`<skill>` 为任务需要的包名。确认实际 Skill 路径/版本和全部相对资源；已有支持安装器路径先核验，避免重复。Claude 使用 CLAUDE.md，不能假设 AGENTS.md 替代；Pi 的共享已验证路径可复用。Windows native 使用 Windows 用户目录/PowerShell；WSL 单独验证。完整安装/升级/发现边界由 setup 包的对应参考按需读取。

## 安全登录

仅由用户在经核验的官方站点交互登录；密码、验证码、Cookie、会话/访问令牌和 SSH 私钥不进入聊天、Issue/PR、配置或终端历史。来源/重定向/权限请求不匹配先停下确认。
