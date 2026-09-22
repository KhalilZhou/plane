# Plane Benchmark Core Report

> 这份文件是什么：四组离线评测（Harness 回归 / 上下文消融 / 记忆消融 / 恢复消融）的指标汇总，用来回答「这些机制到底有没有用」。逐条明细见同目录 module-metrics.md 与 artifacts/ 下的 JSON。

这轮 benchmark 只收缩到 Harness regression、context ablation、working memory ablation 和 recovery ablation 四层，不把 provider、run aggregation 或 durable memory 的别的结论揉进来。

## Harness Regression
- 固定 regression 任务数：12
- pass_rate：100.00%
- within_budget_rate：100.00%
- verifier_pass_rate：100.00%

## Context Ablation
- 配置数：12
- avg_full_prompt_chars：6257.67
- avg_raw_prompt_chars：7676.33
- avg_prompt_compression_ratio：15.13%
- max_prompt_compression_ratio：31.34%
- current_request_preserved_rate：100.00%

## Working Memory Ablation
- memory_on repeated_reads：0
- memory_off repeated_reads：36
- memory_on avg_tool_steps：0.00
- memory_on correct_rate：100.00%
- memory_hit_rate：100.00%

## Recovery / Resume Ablation
- resume_success_rate：90.00%
- stale_reanchor_rate：100.00%
- workspace_drift_detection_rate：100.00%
- resume_false_accept_rate：0.00%

## 可以安全写进简历的指标
- avg_full_prompt_chars
- avg_raw_prompt_chars
- avg_prompt_compression_ratio
- max_prompt_compression_ratio
- repeated_reads
- avg_tool_steps
- correct_rate
- resume_success_rate
- workspace_drift_detection_rate
- resume_false_accept_rate

## 只适合放文档/面试展开的指标
- current_request_preserved_rate
- memory_hit_rate
- stale_reanchor_rate
- failure_category_counts

## 口径边界
- Harness regression 只证明 runtime 合同稳定，不证明 provider 上限。
- Context、memory、recovery 这三层只证明模块收益，不和 provider benchmark 混写。
