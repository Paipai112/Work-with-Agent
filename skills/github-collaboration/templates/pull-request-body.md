<!-- Example only: replace every sample value, preserve the project's body structure,
and keep exactly one metadata block. Partial delivery uses closes_issues: []. -->

Closes #123

## 变更与范围

- 已认领范围：<paths or components>
- 实际变更：<paths and outcome>
- 明确排除：<unrelated or governance work>

## 验收与验证

- 验收条件：<Issue-linked criteria>
- 已执行：<commands and observed results>
- 未执行／未知：<gaps, not invented passes>

## 协作与风险

- 认领事件及评论链接：<verified links>
- 风险、回滚边界：<specific notes>
- Actions 触发和额度／成本告知：<known triggers and uncertainty>
- 剩余工作与交接：<owner, branch, HEAD, blockers>

<!-- agent-collaboration:metadata
{
  "schema_version": 1,
  "primary_issue": 123,
  "closes_issues": [123],
  "actor_id": "backend-api",
  "controlled_by": "alex",
  "controlled_by_id": 1234,
  "runtime": "codex",
  "session_id": "example-office-session",
  "skill_version": "0.1.0",
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "base_branch": "main",
  "claim_urls": ["https://github.com/example-org/example-repo/issues/123#issuecomment-1001"],
  "workflow": "daily"
}
-->

正文标题可按项目或工程工具调整；机器字段仅保留在上述 JSON 区块中。多个 Issue 可列入 closes_issues，正文关闭语句必须一致；部分交付不关闭未完成 Issue。创建前读取项目模板并替换全部示例。
