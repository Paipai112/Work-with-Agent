# 验证范围与复现

本页区分本地确定性测试、实际客户端行为、GitHub 实仓和服务端强制门槛。v0.2.0 为候选，交付三个独立 Skill、项目模板和随包脚本；旧版证据保留为历史记录，不外推为候选全部通过。

## 一、v0.2.0 候选验收

本轮原生平台范围限定 macOS／Codex，不运行 Claude Code、Pi 或 Windows 原生验收。发行门槛包括以下三条链：

| 链路 | 验证内容 | 证据边界 |
| --- | --- | --- |
| 配置与包 | 真实候选原文解析、schema、固定 checker；三包各自完整、精确差异和字节核验 | 不授予安装或治理权限 |
| GitHub 元数据 | 同一可信 SHA 的采集与检查，分页、漂移、事件历史、范围及叠加交付 | 模拟 API 与实仓分别记录；可选 Actions 另批 |
| Codex 行为 | 固定任务下实际读取、操作选择、权限与审批边界；静态及实际读取量分别测量 | 只读场景不等于执行了 Commit／Push／PR；不外推其他客户端 |

候选仍在本地集成验收中。当前已有的局部结果不作为最终固定候选的整体通过声明；正式报告须绑定最终提交、命令、结果和未覆盖事项，再决定发布。

## 二、历史证据

### 1. v0.1.1

- 离线回归：378 项通过、6 项排除（已安装 Claude/Pi 的原生探测，明确排除、不算通过）。较 v0.1.0 新增 29 项，覆盖认领评论核验、关闭关键字与治理路径收紧、检查输出提示、工作流采集等行为。
- 包校验：两个自包含目录、资源 manifest、引用与辅助脚本语法全部通过；发行快照与清单重建后复算一致。
- schema、PR 元数据检查、受管块和文件安全测试属于确定性验证；场景文件描述预期行为，不能作为 Agent 实际行为或 GitHub 服务端强制证据。

### 2. v0.1.0

- Codex CLI `0.159.3`、`gpt-6.1-sol` / `ultra`：两个独立的新会话分别显式调用 setup 和 daily Skill；观察到项目入口自动加载、包内所需参考全文读取、默认 Member 和只读边界。两个隔离 fixture 的文件字节在调用前后均未变化。v0.1.1 未重跑客户端原生加载，不将结论外推为其他平台或本版本已重新通过。
- v0.1.0 的固定发行取回、安装与读回记录见该版本 Release 与验收附件。

内部原始会话、测试账号标识及私有测试仓治理记录没有随源码发行。这里是维护者的范围说明，不冒充公开原始日志。需要独立审计时应取得获授权证据或在自己的隔离测试仓复验。

## 三、离线复现

需要 Python 3.11+；测试依赖列在 `pyproject.toml` 的 `project.optional-dependencies.test`。三个 Skill 不要求将本仓安装成 Python 项目；事件和正式 PR 检查工具另需 helpers 依赖，须经批准准备，缺少时报告 unknown。

```sh
python3 scripts/verify_skill_packages.py
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest \
  -p no:cacheprovider tests/unit tests/integration/test_probe_parser.py \
  -k 'not test_installed_pi_loader_discovers_and_expands_real_packages and not test_installed_claude_safe_initialize_registers_real_packages' -q
```

请先在隔离虚拟环境按上述声明安装测试依赖。不要把不带筛选的 `pytest` 当作纯离线命令：部分用例会启动本机安装的其他客户端。也不要运行 `probe_repository.py`、平台探测或 Agent 行为场景而假定它们没有网络、凭据、模型或费用影响。

## 四、验证边界

- 完整九组合原生矩阵；Windows、Linux 和其他客户端本轮不验。
- 所有日常写操作、持久 Leader 激活以及项目治理 PR 的真人审批链。
- 可选 Actions / Required Checks / Rulesets 的真实服务端拦截。模板存在不代表已启用；发行本身不启用这些设施。

安装可用、项目配置完成和 GitHub 强制执行是三个不同结论。具体项目须按实际账号权限、现有保护、精确授权和合并后同 SHA 回读决定是否完成配置；不能由本页替代。
