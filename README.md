# Baton

一套基于 GitHub 的多 Agent 协作模板，以及两个相互独立的 Skill：

| 组件 | 用途 |
| --- | --- |
| `github-collaboration-setup` | 项目预检、初始化、增量配置、升级、诊断与治理授权 |
| `github-collaboration` | 日常 Issue、任务认领、分支、提交、PR、审查、合并与交接 |
| 项目模板 | 保存协议、角色、授权记录、项目事实入口和 Issue／PR 格式 |

本次固定发行版本为 `v0.1.1`，源仓为 [Paipai112/baton](https://github.com/Paipai112/baton)。安装时必须核验实际版本标签并解析完整提交 SHA，再从该 SHA 复制两个完整包；具体步骤见 [安装与项目接入](docs/INSTALL.md)，验证范围见 [发行说明](docs/RELEASE_NOTES.md)。（`v0.1.0` 为历史版本，标签与发行附件保持发布时状态。）

包校验需要 Python 3.11+，两个 Skill 的日常使用不要求安装测试项目。可选离线回归的隔离环境与依赖安装见 [安装页](docs/INSTALL.md#可选离线回归)，测试选择及证据边界见 [验证说明](docs/VALIDATION.md)。

## 一次协作长什么样

一次典型任务从认领到交接的流程：

1. **认领**：Agent 在任务 Issue 下发出认领评论，评论 URL 写入任务记录；可选的元数据检查会按 GitHub API 实拉核验该评论的存在性、作者账号与所属 Issue。
2. **开工**：从默认分支新建任务分支（命名含职责与 Issue 编号），提交保持精确暂存与可核验的提交信息。
3. **开 PR**：正文包含协作元数据块（主 Issue、关闭的 Issue、作业身份、受控账号、认领评论 URL、实际 Skill 版本），并用关闭关键字（`Closes #<编号>`）声明将关闭的 Issue。
4. **审查**：按角色与授权读取审查意见；合并遵循项目现有 GitHub 保护与审批，不因协议文本自动通过。
5. **合并后**：关闭关键字由 GitHub 在合并后生效；提交信息中的关键字不在检查范围，合并后应读回 Issue 状态确认。
6. **交接**：结果与交接记录写入 Issue 或仓库，供下一会话核验接手。

## 开始使用

1. 在获授权的目标项目中检查现有 Skill 和项目文件，将固定提交的两个完整包安装到项目级 `.agents/skills/`。同名目录已存在时，先报告来源、版本和差异，按审阅后的升级方案处理。
2. 新建 Agent 会话，分别显式调用两个 Skill，确认实际读取路径、版本和相对资源，再用 setup 执行只读预检。
3. 核验现有 Leader；首次安装由具备条件的人类明确授予限定的 Bootstrap 权限。随后展示增量配置差异，按相应授权完成治理 PR、审批、合并和默认分支读回。
4. 日常任务使用 `github-collaboration`，从当前默认分支读取项目配置、协议和授权，按 Issue／认领／分支／PR 流程交付。

已验证的主路径是 macOS 原生 Codex CLI `0.159.3` 对两个 Skill 的只读显式调用。其他平台的安装合同和适配说明不代表原生调用已经通过；接入前应在实际环境完成验证。Claude Code 的项目发现目录为 `.claude/skills/`，不能假定它会自动加载 `.agents/skills/`。详见 [平台安装参考](skills/github-collaboration-setup/references/platform-installation.md)。

## 使用边界

所有 Agent 默认是 Member；安装 Skill、拥有 GitHub Admin／Maintain 账号或使用同一账号，都不会自动获得 Leader 身份。Leader 授权需要绑定项目、账号和职责身份，并受授权上限、账号当前权限及项目保护规则共同约束。

这些角色和文档是协作协议，角色本身不是安全沙箱，也不能隔离共享账号的凭据。现有 GitHub 保护规则仍然适用；未知或冲突的身份、授权、文件所有权和任务范围需先查明。

项目模板默认关闭 Actions、Required Checks 和 Rulesets。启用任何一项均是独立治理改动；可能触发工作流的操作需先确认工作流、权限、runner 和费用影响，并获得对应批准。私有仓库的实际额度与费用应以当前账号和组织设置为准。

本项目以 [MIT 许可证](LICENSE) 开源发布。
