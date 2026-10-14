# Work-with-Agent

基于 GitHub 的多 Agent 协作模板与三个可独立安装的 Skill。项目事实保存在仓库、Issue 和 PR；Agent 按当前任务加载操作规则，换设备或换 Agent 时可从线上记录接手。

| 组件 | 用途 |
| --- | --- |
| `github-collaboration-setup` | 项目预检、初始化、增量配置、升级、诊断与治理授权 |
| `github-collaboration` | 日常 Issue、任务认领、分支、提交、PR、审查、合并与交接 |
| `github-collaboration-check` | 可选、显式调用的只读检查；收集证据、解释失败或缺口，不修复或批准 |
| 项目模板 | 保存协议、角色、授权记录、项目事实入口和 Issue／PR 格式 |

下文把三个包简称为 setup（配置）、daily（日常）和 check（只读检查）。这里给出接入顺序；Agent 执行某项操作时，仍需读取所选 Skill 中该操作的完整规则。

公开源仓为 [Paipai112/Work-with-Agent](https://github.com/Paipai112/Work-with-Agent)，仓库稳定 ID 为 `1398932546`。正式安装 `v0.2.0` 时，先核验实际 Release／标签并解析完整提交 SHA；隔离验收可显式选择已发布的 `v0.2.0-rc.1`。目录名和浮动分支不能代替固定来源，旧标签、摘要和历史证据保持原样。

发行与下载入口：[v0.2.0](https://github.com/Paipai112/Work-with-Agent/releases/tag/v0.2.0)。该页提供固定提交、三个独立包、摘要及同提交安装页；只有页面存在且标为正式发行时才作为稳定来源使用。

包校验需要 Python 3.11+。事件校验和 v0.2 正式 PR 检查另外需要显式准备 PyYAML 与 jsonschema；工具不会自动安装依赖。安装、成套升级与固定提交核验见 [安装页](docs/INSTALL.md)，实际验收证据见 [验证说明](docs/VALIDATION.md)。

## 一、协作流程

一次典型任务从认领到交接的流程：

- 首先确认职责身份、账号权限、默认分支上的协议与有效认领；Issue、评论或安装 Skill 本身不会授予权限。
- 随后在认领范围内开分支、实现并验证，提交只包含逐项检查过的精确路径。依赖未合并 PR 时，固定前置提交与净变更基线，先交付 Draft。
- PR 记录任务、认领、当前 HEAD、交付基线及实际验证结果。只为已经验收的 Issue 填写关闭语句。
- 审核绑定当前 HEAD；前置或 HEAD 变化后重新检查。合并满足独立审查、具体批准与现有 GitHub 保护要求。
- 最后回读合并和 Issue 状态，将结果、未完成项与交接事件留在 GitHub。旧会话状态未知时不能直接抢占或释放认领。

## 二、开始使用

- 配置者安装 setup，协作者安装 daily；仅需检查时可单独安装 check。setup 与 daily 已携带所需检查工具，不要求先调用 check。
- 从获核验的固定发行提交复制所选完整包到客户端的发现目录。已有同名目录时先展示来源、版本和字节差异，保留定制内容。
- 新会话中显式调用所选 Skill，确认实际路径和版本，再只读预检。Codex 项目级路径为 `.agents/skills/`，Claude Code 为 `.claude/skills/`，Pi Agent 为 `.agents/skills/`。
- 首次治理配置需人类明确授予限域 Bootstrap；已有项目核验有效 Leader。逐项批准增量差异后，完成适用的治理 PR、审批、合并与默认分支读回。

本轮 macOS／Codex 原生发现与读取记录绑定 `v0.2.0-rc.1`，后续 helper 修改按最终固定提交重新做包校验与离线回归，未重跑最终完整包原生会话。Claude Code、Pi 与其他操作系统使用前须验证对应客户端的加载行为；本轮没有这些组合的原生通过声明。安装路径见 [平台安装参考](skills/github-collaboration-setup/references/platform-installation.md)。

## 三、使用边界

所有 Agent 默认是 Member；安装 Skill、拥有 GitHub Admin／Maintain 账号或使用同一账号，都不会自动获得 Leader 身份。Leader 授权需要绑定项目、账号和职责身份，并受授权上限、账号当前权限及项目保护规则共同约束。

这些角色和文档是协作协议，角色本身不是安全沙箱，也不能隔离共享账号的凭据。现有 GitHub 保护规则仍然适用；未知或冲突的身份、授权、文件所有权和任务范围需先查明。

项目模板默认关闭 Actions、Required Checks 和 Rulesets。启用任何一项均是独立治理改动；可能触发工作流的操作需先确认工作流、权限、runner 和费用影响，并获得对应批准。私有仓库的实际额度与费用应以当前账号和组织设置为准。

本项目以 [MIT 许可证](LICENSE) 开源发布。
