# 安装与项目接入

本页对应 `v0.2.0` 候选，供项目负责人和协作者准备安装或升级。只有实际 Release／标签存在且来源核验通过后，才能按正式发行接入；候选源码可用于隔离开发验收。安装包不授予 Leader，也不代表消费项目已经完成治理配置。

## 一、目标与来源

先确认目标项目根目录、客户端名称和版本、操作系统及 native／WSL 环境。查看工作区状态、现有 `.agents/skills/`、其他发现位置中的同名 Skill，以及现有 `AGENTS.md`、`CLAUDE.md` 和 `.github/` 文件。记录实际生效路径、版本、本地改动、符号链接和重复项。

远端源仓当前为 [Paipai112/baton](https://github.com/Paipai112/baton)，目标名称为 `Paipai112/Work-with-Agent`，目标标签为 `v0.2.0`。先核验仓库实际名称、稳定 ID 和维护者的发布记录；改名后使用核验过的新地址。来源不可达、标签不存在或身份不一致时保持只读，不虚填“已发布”。

使用用户已有安全认证。需要开户时引导用户在 [GitHub](https://github.com/) 注册，再由用户在本机交互式执行认证；不要在聊天、文件或日志中索要、复制或打印密码、Token、私钥。没有 Git 或远端仓库时，先说明初始化／创建的准确目标并取得批准。

核验维护者实际发布的 Release／标签记录，将标签解析为完整 40 位提交 SHA。后续源树、包摘要和安装页都使用该 SHA。标签是定位入口，固定提交才是安装依据；浮动分支不能代替它。

下面是 macOS／Linux shell 的来源读取示例，只将源仓检出到新建临时目录，不修改目标项目。应先确认本次读取和认证环境，再运行：

```sh
set -eu
source_url='https://github.com/Paipai112/baton'
release_tag='v0.2.0'
source_checkout="$(mktemp -d)"
git clone --filter=blob:none --no-checkout "$source_url" "$source_checkout/source"
git -C "$source_checkout/source" fetch origin "refs/tags/$release_tag:refs/tags/$release_tag"
resolved_sha="$(git -C "$source_checkout/source" rev-parse --verify "refs/tags/$release_tag^{commit}")"
test "${#resolved_sha}" -eq 40
git -C "$source_checkout/source" checkout --detach "$resolved_sha"
printf '固定提交：%s\n源目录：%s\n' "$resolved_sha" "$source_checkout/source"
```

取回后，先审阅固定来源中的校验程序，再在隔离环境运行：

```sh
python3 "$source_checkout/source/scripts/verify_skill_packages.py" --repo-root "$source_checkout/source"
```

校验会执行来源代码，只证明清单、相对资源和摘要一致，不能证明来源可信。压缩包顶层目录名可能随仓库改名改变；不按目录名匹配身份，始终绑定完整提交 SHA。

本仓的包校验脚本使用 Python 3.11+ 标准库。若当前环境不能运行，应先解决校验条件或使用能检查相同清单、相对资源和摘要的等价方式。安装不需要 `npx`、第三方安装器或新增产品 CLI。

## 二、完整包与安装核验

按用途选择，每个包可以单独安装：

```text
skills/github-collaboration-setup/
skills/github-collaboration/
skills/github-collaboration-check/  # 可选：只读检查任务
```

记录每个包的完整文件清单和 SHA-256 摘要，并确认 `RESOURCE_MANIFEST.json` 声明的资源与源树一致。复制整个目录，保留 `SKILL.md`、`references/`、`assets/`、`scripts/`、`agents/` 和 manifest 中实际存在的文件；仅下载入口文件不足以安装。

逐一检查目标目录和父路径：

```text
<目标项目>/.agents/skills/github-collaboration-setup/
<目标项目>/.agents/skills/github-collaboration/
```

配置者用 setup，日常协作者用 daily；独立检查任务可只用 check。setup／daily 已携带检查入口，不依赖 check。需要 check 时，精确目标为 `<目标项目>/.agents/skills/github-collaboration-check/`。

目标不存在且路径安全时，展示具体来源、SHA、包摘要、文件清单和目标位置；在安装授权范围内复制到精确目标。复制后核对完整文件集和字节，包之间不互相嵌套，不跨包读取运行资源。

目标已存在时，先报告现有来源、版本、摘要、缺失／额外文件和本地差异。保留原目录，按经审阅的升级或冲突处理方案继续；不能直接合并、清空或覆盖，也不能仅凭同名与版本号认为内容相同。符号链接、未知所有权或路径越界同样需要先处理。

使用已审阅的固定源树工具逐包核对；以下参数需换成真实路径和完整 SHA：

```text
python3 <可信源树>/shared/scripts/verify_installed_skill.py --source-repo <可信Git源树> --source-sha <完整SHA> --skill github-collaboration --installed <所核验包的精确目录>
```

- 退出 `0`／`pass` 表示该时点安装文件集和字节与指定提交一致；不验证发布标签绑定或操作授权。
- 退出 `1` 表示发现差异，退出 `2` 表示无法完成核验。工具不会安装、修复或覆盖内容。
- 标签→SHA 与仓库来源需独立核验；同名目录、版本字段或此前的成功记录都不能代替这一步。
- Git 必须支持禁止自动补取对象的 `--no-lazy-fetch`。工具不下载缺失对象；对象不足或本机 Git 不支持该安全能力时返回 unknown，由用户另行批准准备来源或升级 Git。

## 三、新会话加载

从目标项目根目录新建 Codex 会话，分别调用：

```text
$github-collaboration-setup
$github-collaboration
$github-collaboration-check
```

仅调用实际安装的包，要求 Agent 保持只读，报告实际读取路径、版本、包内资源、项目入口和同名覆盖情况。结果应与固定源包及安装记录一致；只看到文件或菜单不算加载验证。若从嵌套目录或含空格路径使用，也需验证对应入口。

本轮原生验收限 macOS／Codex，实际版本和证据记录在 [验证说明](VALIDATION.md)。其他客户端使用 [平台安装参考](../skills/github-collaboration-setup/references/platform-installation.md) 中的路径和调用方式：Claude Code 项目级为 `.claude/skills/`，Pi Agent 为 `.agents/skills/`；静态适配合同不等于原生验收通过。

## 四、预检与授权

调用 setup 的 `diagnose` 或 `initialize`，先完成只读 preflight：核验目标 GitHub 仓库身份、默认分支及当前 SHA、登录账号和真实权限、现有保护规则、治理文件和项目事实来源，确认职责型 `actor_id`。

所有 Agent 从 Member 开始。已有治理配置时，配置及它指定的授权文件必须来自同一个已确认默认分支 SHA；核验当前 active Leader 记录及冻结权限上限。工作分支候选、Skill 安装和账号 Admin／Maintain 都不能给 Agent 自行授予 Leader。

首次安装且无既有授权时，由控制已核验 Maintain／Admin 账号的人类明确授予当前职责身份、仓库和提案范围的 Bootstrap 会话权限。若丢失最后一位 Leader，则走 Recovery 并保留原授权历史。持久 Leader 需完成对应治理 PR 的真实审批、合并和默认分支读回，不能由候选文件提前生效。

事件校验和 v0.2 正式 PR 检查需要 `PyYAML>=6,<7` 与 `jsonschema[format]>=4.23,<5`。审阅固定包的 `scripts/requirements-helpers.txt`（setup／daily），或同一可信部署 SHA 的 `requirements-helpers.txt`，经环境准备批准后装入隔离环境。缺依赖返回 unknown；工具不自动安装，也不把不完整校验说成通过。

## 五、增量配置

setup 扫描已有文件后，逐项展示项目协议、配置、授权记录、受管资源账本、Issue／PR 模板和入口受管块的差异。项目事实只索引现有需求、规格、决策、进度及验证来源；尚未确认的来源保留“未知”。已有内容、未提交改动、重复规则或受管范围冲突需按明确选择处理。文件修改、Commit、Push、PR、授权审批、合并和远端设置按各自的授权边界推进；已有有效授权无需重复获取。

在目标项目生成 `.github/agent-collaboration/INSTALL_SKILL.md` 时，用本次已核验的固定发行提交填入四项：

| 字段 | 消费项目中的值 |
| --- | --- |
| `source_repository_url` | `https://github.com/Paipai112/baton` |
| `release_tag` | 实际存在且核验通过的 `v0.2.0` |
| `resolved_commit_sha` | 本次标签解析并核验的完整 40 位 SHA |
| `installation_page_permalink` | `https://github.com/Paipai112/baton/blob/<同一完整SHA>/docs/INSTALL.md` |

仓库完成改名后，上表 URL 使用经过稳定 ID 核验的新名称。将占位符替换为实际 SHA，核验永久链接能读取同 SHA 的安装页，并确认参与者可访问源仓。在经审阅的项目候选中把 `installation_status` 改为 `published`，记录安装路径和调用方式。通用模板保持四个空字段及 `unpublished`；候选不能自己补一条“已批准／已发布”就生效。

项目配置完成的依据是已批准差异、实际适用的审批与保护门槛、合并后同一默认分支 SHA 的配置／授权读回，以及可用的固定安装入口。安装包校验通过不代替这些条件。

Actions、Required Checks 和 Rulesets 默认关闭。启用时逐项展示差异并获得批准；首次可能触发的 Push／PR／合并前，说明工作流、runner、权限、预计频率和当前额度／费用。正式元数据检查核验声明、所采集事件历史及范围等一致性，不证明真人批准、实时角色权限、Skill 实际加载或 GitHub 原生独立审批。

## 六、日常使用与升级

在已完成治理配置的项目中调用 `$github-collaboration`。每次会话先读取当前默认分支的配置、协议、授权和固定安装入口，再选择或创建 Issue、记录对应任务认领、实施获授权范围、精确暂存、提交和建立 PR。审查／合并遵守有效角色和现有 GitHub 保护；重要结果与交接记录保存到仓库或 GitHub，供下次会话核验。

角色是协作协议，不是安全沙箱；共享账号不产生独立的 GitHub 审查身份。项目仍需按自身风险管理凭据、审查和服务器保护。

升级到未来版本时，重新解析维护者发布的固定标签并核验完整包，比较现有目录和项目受管资源差异，再按审阅后的方案更新及重新验证。已核验的包可按 Skill 规则复用验证记录，来源、路径、版本或字节改变后重新校验。

从 v0.1.x 升级至 v0.2 时，按以下兼容边界制定治理提案：

| 资源 | 升级要求 | 不完整时的结果 |
| --- | --- | --- |
| 正式检查链 | checker、collector、launcher、事件／范围 helper、事件 schema、requirements 来自同一可信默认 SHA；可选工作流使用配套版本 | 缺失或混配返回 unknown，不替换成候选程序 |
| PR 元数据 | 新正式路径使用 schema_version=2 和 delivery 基线字段；旧 PR 逐个明确更新 | 旧输入只允许显式 legacy diagnostic，不产生正式 PASS |
| 已安装 Skill | 所选完整包及最低版本配套升级，重新验证实际加载 | 版本符合但字节漂移仍须报告 |
| 项目规则与入口 | 对每份旧资源做三方差异比较，保留用户定制；整入口改动走治理审查 | setup 只拥有批准的区块，不获得整文件编辑权 |

- 先在隔离候选中验证真实配置原文和整套程序，再提出精确文件、Commit 归属与远端操作方案。内容处理批准不自动包含提交用户脏改动。
- 前置 PR 或认领基线变化需要独立修订和重新核验；范围扩大不能用基线更正追认。
- 回退保留旧固定包、受管基线和配置记录，通过新的治理差异恢复经批准的完整兼容组合。不得盲目回滚授权记录、清空目录或强推历史；旧包也不能覆盖期间新增的用户内容。
- 改名不改变 Skill 名、受管标记、schema 标识和 `.github/agent-collaboration/` 路径。消费者旧链接和定制分别列差异，不由源仓升级自动修改。

## 七、可选离线回归

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

测试依赖安装需要软件源访问。pytest 仅用于维护者回归；PyYAML 和 jsonschema 同时用于事件／正式检查 helper，不要求把本仓安装成 Python 项目。使用上述筛选避免启动其他客户端；未运行用例不计为通过。

## 八、接入任务示例

将目标项目及职责身份填入以下任务；任务默认从只读安装检查开始，接入写入按已有授权和实际缺口继续：

```text
请在目标项目 <项目目录> 接入 Work-with-Agent v0.2.0，职责身份为 <actor_id>。
先只读核验目标项目、现有同名 Skill、工作区、GitHub 身份及保护规则。
源仓固定为 https://github.com/Paipai112/baton；
先核验实际仓库名称与稳定 ID；若已改名，使用核验过的 Work-with-Agent 地址。
核验实际 v0.2.0 Release/tag 并解析完整 40 位 SHA；若尚未发布，停止正式安装。
从该提交按角色选择 setup、daily 或可选 check 完整包，
校验文件清单和资源摘要，展示项目级 .agents/skills 的安装差异。
目录已存在时报告现有来源及本地差异，保留原内容并按审阅后的方案处理。
在安装授权内复制到不存在且安全的精确目标，回读比较，并用新会话只读显式调用所选 Skill。
随后用 github-collaboration-setup 做 preflight，核验已有 Leader 或准备限定 Bootstrap。
从固定发行提交生成消费项目 INSTALL_SKILL.md 的四项真实元数据及同 SHA 的 docs/INSTALL.md 永久链接，
增量提出项目协议、授权、事实索引和入口改动，按已有授权完成必要审批与治理 PR。
Actions、Required Checks 和 Rulesets 保持默认关闭；如需启用，逐项说明影响并取得对应批准。
最终报告实际固定 SHA、包摘要、加载路径、项目配置读回、权限状态及尚未完成项。
```

本项目以 [MIT 许可证](../LICENSE) 开源发布。
