# 安装与项目接入

本页面向计划在获授权项目使用 `v0.1.0` 的参与者。默认接入路径是已验证的 macOS／Codex 组合：把两个完整 Skill 包放入目标项目的 `.agents/skills/`。安装和治理配置分别验收；包安装成功不授予 Leader，也不代表项目已配置完成。

## 1. 检查目标与来源

先确认目标项目根目录、客户端名称和版本、操作系统及 native／WSL 环境。查看工作区状态、现有 `.agents/skills/`、其他发现位置中的同名 Skill，以及现有 `AGENTS.md`、`CLAUDE.md` 和 `.github/` 文件。记录实际生效路径、版本、本地改动、符号链接和重复项。

源仓为 [Paipai112/baton](https://github.com/Paipai112/baton)，固定标签为 `v0.1.0`。通过已有安全认证访问源仓；不要把密码、令牌或私钥写入命令、文档或聊天。来源不可达、标签不存在、来源身份不一致时，报告具体缺口并保持只读。

核验维护者实际发布的 Release／标签记录，将标签解析为完整 40 位提交 SHA。后续源树、包摘要和安装页都使用该 SHA。标签是定位入口，固定提交才是安装依据；浮动分支不能代替它。

下面是 macOS／Linux shell 的来源读取示例，只将源仓检出到新建临时目录，不修改目标项目。应先确认本次读取和认证环境，再运行：

```sh
set -eu
source_url='https://github.com/Paipai112/baton'
release_tag='v0.1.0'
source_checkout="$(mktemp -d)"
git clone --filter=blob:none --no-checkout "$source_url" "$source_checkout/source"
git -C "$source_checkout/source" fetch origin "refs/tags/$release_tag:refs/tags/$release_tag"
resolved_sha="$(git -C "$source_checkout/source" rev-parse --verify "refs/tags/$release_tag^{commit}")"
test "${#resolved_sha}" -eq 40
git -C "$source_checkout/source" checkout --detach "$resolved_sha"
python3 "$source_checkout/source/scripts/verify_skill_packages.py" --repo-root "$source_checkout/source"
printf '固定提交：%s\n源目录：%s\n' "$resolved_sha" "$source_checkout/source"
```

本仓的包校验脚本使用 Python 3.11+ 标准库。若当前环境不能运行，应先解决校验条件或使用能检查相同清单、相对资源和摘要的等价方式。安装不需要 `npx`、第三方安装器或新增产品 CLI。

## 2. 固定两个完整包

从上一步的固定源树取出：

```text
skills/github-collaboration-setup/
skills/github-collaboration/
```

记录每个包的完整文件清单和 SHA-256 摘要，并确认 `RESOURCE_MANIFEST.json` 声明的资源与源树一致。复制整个目录，保留 `SKILL.md`、`references/`、`assets/`、`scripts/`、`agents/` 和 manifest 中实际存在的文件；仅下载入口文件不足以安装。

逐一检查目标目录和父路径：

```text
<目标项目>/.agents/skills/github-collaboration-setup/
<目标项目>/.agents/skills/github-collaboration/
```

目标不存在且路径安全时，展示具体来源、SHA、包摘要、文件清单和目标位置；在本次安装授权范围内新建父目录并复制到精确目标。复制后比较完整文件集和字节摘要，确保两个包互不嵌套且资源可在包内访问。

目标已存在时，先报告现有来源、版本、摘要、缺失／额外文件和本地差异。保留原目录，按经审阅的升级或冲突处理方案继续；不能直接合并、清空或覆盖，也不能仅凭同名与版本号认为内容相同。符号链接、未知所有权或路径越界同样需要先处理。

## 3. 在新会话验证实际加载

从目标项目根目录新建 Codex 会话，分别调用：

```text
$github-collaboration-setup
$github-collaboration
```

要求 Agent 保持只读，报告实际读取的 `SKILL.md` 路径、`metadata.version`、相对参考和资源是否可打开、项目入口的位置及同名覆盖情况。结果应与固定源包及安装记录一致；只看到文件或菜单项不能视为验证通过。若将从嵌套目录或含空格路径使用，也需在那些实际入口的新会话中验证。

本轮实测仅覆盖 macOS 原生 Codex CLI `0.159.3` 对两个 Skill 的只读显式调用。Linux、Windows native、WSL、Claude Code 和 Pi Agent 的原生调用尚未在本轮验收。其他客户端接入时使用 [平台安装参考](../skills/github-collaboration-setup/references/platform-installation.md) 中各自的发现路径和调用方式：Claude Code 项目级使用 `.claude/skills/`，Pi Agent 项目级使用 `.agents/skills/`；每种客户端／操作系统组合单独验证。

## 4. 只读预检与 Leader／Bootstrap

调用 setup 的 `diagnose` 或 `initialize`，先完成只读 preflight：核验目标 GitHub 仓库身份、默认分支及当前 SHA、登录账号和真实权限、现有保护规则、治理文件和项目事实来源，确认职责型 `actor_id`。

所有 Agent 从 Member 开始。已有治理配置时，配置及它指定的授权文件必须来自同一个已确认默认分支 SHA；核验当前 active Leader 记录及冻结权限上限。工作分支候选、Skill 安装和账号 Admin／Maintain 都不能给 Agent 自行授予 Leader。

首次安装且无既有授权时，由控制已核验 Maintain／Admin 账号的人类明确授予当前职责身份、仓库和提案范围的 Bootstrap 会话权限。若丢失最后一位 Leader，则走 Recovery 并保留原授权历史。持久 Leader 需完成对应治理 PR 的真实审批、合并和默认分支读回，不能由候选文件提前生效。

## 5. 增量配置消费项目

setup 扫描已有文件后，逐项展示项目协议、配置、授权记录、受管资源账本、Issue／PR 模板和入口受管块的差异。项目事实只索引现有需求、规格、决策、进度及验证来源；尚未确认的来源保留“未知”。已有内容、未提交改动、重复规则或受管范围冲突需按明确选择处理。文件修改、Commit、Push、PR、授权审批、合并和远端设置按各自的授权边界推进；已有有效授权无需重复获取。

在目标项目生成 `.github/agent-collaboration/INSTALL_SKILL.md` 时，用本次已核验的固定发行提交填入四项：

| 字段 | 消费项目中的值 |
| --- | --- |
| `source_repository_url` | `https://github.com/Paipai112/baton` |
| `release_tag` | `v0.1.0` |
| `resolved_commit_sha` | 本次标签解析并核验的完整 40 位 SHA |
| `installation_page_permalink` | `https://github.com/Paipai112/baton/blob/<同一完整SHA>/docs/INSTALL.md` |

将占位符替换为实际 SHA，核验永久链接能读取本页，并确认项目参与者有权访问源仓。在经审阅的项目候选中把 `installation_status` 改为 `published`，同时记录选择的项目级安装路径和调用方式。模板源码中的四个空字段和 `installation_status: unpublished` 是正常状态；不要把模板原样复制后宣布可安装，也不要为了发行而给通用模板硬编码消费项目数据。

项目配置完成的依据是已批准差异、实际适用的审批与保护门槛、合并后同一默认分支 SHA 的配置／授权读回，以及可用的固定安装入口。安装包校验通过不代替这些条件。

Actions、Required Checks 和 Rulesets 默认关闭。启用时分别提出具体资源改动；可能触发工作流的 Push、PR 或合并还需先说明实际工作流、runner、权限、预计频率及额度／费用不确定项，并获得对应批准。私有仓库可能产生费用，数额应查询当前账号和组织设置。元数据检查只检查声明字段，不能证明 Agent 加载了 Skill 或产生独立账号审查。

## 6. 日常使用与升级

在已完成治理配置的项目中调用 `$github-collaboration`。每次会话先读取当前默认分支的配置、协议、授权和固定安装入口，再选择或创建 Issue、记录对应任务认领、实施获授权范围、精确暂存、提交和建立 PR。审查／合并遵守有效角色和现有 GitHub 保护；重要结果与交接记录保存到仓库或 GitHub，供下次会话核验。

角色是协作协议，不是安全沙箱；共享账号不产生独立的 GitHub 审查身份。项目仍需按自身风险管理凭据、审查和服务器保护。

升级到未来版本时，重新解析维护者发布的固定标签并核验完整包，比较现有目录和项目受管资源差异，再按审阅后的方案更新及重新验证。已核验的包可按 Skill 规则复用验证记录，来源、路径、版本或字节改变后重新校验。

## 可选离线回归

如需复现维护者的离线测试，在已核验源树的根目录使用 Python 3.11+ 建立新隔离环境。以下 macOS／Linux 命令安装 `pyproject.toml` 声明的测试依赖，不安装本仓为 Python 项目：

```sh
test_venv="$(mktemp -d)"
python3 -m venv "$test_venv"
"$test_venv/bin/python" -m pip install 'pytest>=8,<9' 'PyYAML>=6,<7' 'jsonschema[format]>=4.23,<5'
"$test_venv/bin/python" scripts/verify_skill_packages.py
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$test_venv/bin/python" -m pytest \
  -p no:cacheprovider tests/unit tests/integration/test_probe_parser.py \
  -k 'not test_installed_pi_loader_discovers_and_expands_real_packages and not test_installed_claude_safe_initialize_registers_real_packages' -q
```

测试依赖安装需要相应软件源访问；它们不是 Skill 运行时依赖。使用上述筛选，避免启动本机其他客户端的探测；不要把未运行用例算作通过。证据和具体未验范围见 [验证说明](VALIDATION.md)。

## 可直接交给 Agent 的任务

将目标项目及职责身份填入以下任务；任务默认从只读安装检查开始，接入写入按已有授权和实际缺口继续：

```text
请在目标项目 <项目目录> 接入 Baton v0.1.0，职责身份为 <actor_id>。
先只读核验目标项目、现有同名 Skill、工作区、GitHub 身份及保护规则。
源仓固定为 https://github.com/Paipai112/baton；
核验实际 v0.1.0 Release/tag 并解析完整 40 位 SHA，从该提交取得两个完整包、
校验文件清单和资源摘要，展示项目级 .agents/skills 的安装差异。
目录已存在时报告现有来源及本地差异，保留原内容并按审阅后的方案处理。
在安装授权内复制到不存在且安全的精确目标，回读比较，并用新会话分别只读显式调用两个 Skill。
随后用 github-collaboration-setup 做 preflight，核验已有 Leader 或准备限定 Bootstrap。
从固定发行提交生成消费项目 INSTALL_SKILL.md 的四项真实元数据及同 SHA 的 docs/INSTALL.md 永久链接，
增量提出项目协议、授权、事实索引和入口改动，按已有授权完成必要审批与治理 PR。
Actions、Required Checks 和 Rulesets 保持默认关闭；如需启用，逐项说明影响并取得对应批准。
最终报告实际固定 SHA、包摘要、加载路径、项目配置读回、权限状态及尚未完成项。
```

本项目以 [MIT 许可证](../LICENSE) 开源发布。
