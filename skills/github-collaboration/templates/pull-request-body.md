<!-- 正文标题和排版可以沿用项目／工程工具结构；保留范围、验收、真实验证、风险／回滚及剩余工作。 -->

## 关联 Issue 与结果

<!-- 填写主任务、关联任务和交付结果。只为实际完成且验收通过的 Issue 写显式关闭语句，并与下方 closes_issues 完全一致；部分交付可以保持主任务打开。 -->

## 变更与范围

<!-- 说明结果、修改路径和明确排除的范围。 -->

## 验收与验证

<!-- 列出验收结果、实际执行的检查及证据、未验证部分；复用的审查证据需适用于当前内容版本。 -->

## 协作与风险

<!-- 记录认领、交接、审批、用户可见影响和回滚边界。不要粘贴凭证。 -->

## 剩余工作

<!-- 说明阻塞、下一步及接手信息；目标为集成分支时，说明默认分支最终交付仍剩什么。叠加交付登记前置 PR 固定 HEAD、开发基线、净 diff 与合并顺序；前置未合并只能 Draft，合并后按当前基线重新检查及审核，squash/rebase 不默认净增量已收敛。 -->

<!-- 下方是唯一机器 metadata 区块。0 和 __SETUP_REQUIRED__ 均是未填写候选值；closes_issues 可为空。workflow 为 daily 或 setup。delivery 两基线填写完整 SHA；无前置时 predecessors=[]、merge_order=[本 PR 真实编号]，先创建 Draft 取得编号再补齐，不完整候选不能通过正式检查。development_base_sha 是有效 claim 当前基线；net_diff_base_sha 是当前净 diff 基线。 -->
<!-- agent-collaboration:metadata
{
  "schema_version": 2,
  "primary_issue": 0,
  "closes_issues": [],
  "actor_id": "__SETUP_REQUIRED__",
  "controlled_by": "__SETUP_REQUIRED__",
  "controlled_by_id": 0,
  "runtime": "__SETUP_REQUIRED__",
  "session_id": "__SETUP_REQUIRED__",
  "skill_version": "0.2.0",
  "head_sha": "__SETUP_REQUIRED__",
  "base_branch": "__SETUP_REQUIRED__",
  "claim_urls": ["__SETUP_REQUIRED__"],
  "workflow": "daily",
  "delivery": {
    "development_base_sha": "__SETUP_REQUIRED__",
    "net_diff_base_sha": "__SETUP_REQUIRED__",
    "predecessors": [],
    "merge_order": []
  }
}
-->
