# Plane 模块指标报告

> 这份文件是什么：按模块汇总的评测指标报告。每个模块（Agent 主循环、上下文管理、记忆系统、检查点与恢复、工具执行与安全、评测框架、提示词缓存）各自列出一组指标表、逐条明细和结论，并附「指标怎么解读」与口径边界。所有数字都由本机离线复现，未调用真实大模型。

- 生成时间：2026-09-22 18:57
- 数据来源：`D:\AI_Project_clean\artifacts`（全部离线复现，未调用真实大模型）
- 复现方式：在项目根目录执行 `python scripts/measure_all.py`

## 0. 功能测试（pytest）

- 结果：**151 passed, 1 skipped in 184.50s (0:03:04)**（exit=0，耗时 184.9s）
- 说明：这层回答「代码有没有坏」，下面的评测回答「机制有没有用」

## 总览

| 模块 | 核心指标 | 结果 | 备注 |
| --- | --- | --- | --- |
| Agent 主循环 | 固定行为任务通过率 | 100.00% | 12/12 通过，失败归因 无 |
| 上下文管理 | prompt 平均压缩率 | 15.13% | 当前请求保留率 100.00% |
| 记忆系统 | 重复读取文件次数 | 0 vs 36 | 开记忆 vs 关记忆 |
| 检查点与恢复 | 恢复成功率 | 90.00% vs 0.00% | 误接受率 0.00% |
| 工具执行与安全 | 治理场景拦截 | 10 个场景 | 错误码分布 {'invalid_arguments': 18, 'approval_denied': 6, 'repeated_identical_call': 3} |
| 提示词缓存 | 缓存命中率 | 离线不可测 | 需要真实 provider 实验（scripts/run_provider_experiments.py） |

## 1. Agent 主循环（agent_loop.py）

**指标**

| 指标 | 数值 |
| --- | --- |
| 任务数 | 12 |
| 通过 / 失败 | 12 / 0 |
| 通过率 pass_rate | 100.00% |
| 预算内完成率 within_budget_rate | 100.00% |
| 断言通过率 verifier_pass_rate | 100.00% |
| 平均模型调用次数 | 2.00 |
| 平均工具步数 | 1.00 |
| 停机原因分布 | {"final_answer_returned": 12} |
| 失败归因分布 | {} |

**按类别（12 个任务）**

| 类别 | 任务数 | 通过 | 通过率 |
| --- | --- | --- | --- |
| documentation | 2 | 2 | 100.00% |
| durable-contract | 2 | 2 | 100.00% |
| recovery | 3 | 3 | 100.00% |
| text-edit | 2 | 2 | 100.00% |
| tool-boundary | 3 | 3 | 100.00% |

**逐任务明细**

| 任务 | 类别 | 步数/预算 | 模型调用 | 结果 | 停机原因 |
| --- | --- | --- | --- | --- | --- |
| readme_intro_locked | documentation | 1/4 | 2 | 通过 | final_answer_returned |
| readme_schema_note | documentation | 1/4 | 2 | 通过 | final_answer_returned |
| sample_beta_locked | text-edit | 1/4 | 2 | 通过 | final_answer_returned |
| sample_gamma_locked | text-edit | 1/4 | 2 | 通过 | final_answer_returned |
| invalid_patch_recovery | tool-boundary | 2/5 | 3 | 通过 | final_answer_returned |
| path_escape_recovery | tool-boundary | 2/5 | 3 | 通过 | final_answer_returned |
| repeated_read_recovery | tool-boundary | 4/6 | 5 | 通过 | final_answer_returned |
| context_reduction_checkpoint | recovery | 0/2 | 1 | 通过 | final_answer_returned |
| freshness_reanchor_resume | recovery | 0/3 | 1 | 通过 | final_answer_returned |
| workspace_mismatch_resume | recovery | 0/3 | 1 | 通过 | final_answer_returned |
| durable_promotion_accept | durable-contract | 0/2 | 1 | 通过 | final_answer_returned |
| durable_promotion_reject | durable-contract | 0/2 | 1 | 通过 | final_answer_returned |

**结论**：12 个固定行为任务全部通过，说明这批改动没有破坏既有 runtime 合同；step_budget 与 verifier 双重约束都满足，不是靠多试几次蒙过去的。

## 2. 上下文管理（context_manager.py）

**指标**

| 指标 | 数值 |
| --- | --- |
| 配置组数 | 12 |
| 不压缩平均 prompt 字符（对照组） | 7,676.33 |
| 压缩后平均 prompt 字符 | 6,257.67 |
| 平均压缩率 | 15.13% |
| 最高压缩率 | 31.34% |
| 最低压缩率 | 0.00% |
| 当前请求保留率 | 100.00% |

**逐组配置**

| 配置 | 历史档位 | 笔记档位 | 不压缩字符 | 压缩后字符 | 压缩率 |
| --- | --- | --- | --- | --- | --- |
| short-low-short | short | low | 5,226 | 5,226 | 0.00% |
| short-low-long | short | low | 5,298 | 5,298 | 0.00% |
| short-high-short | short | high | 5,424 | 5,424 | 0.00% |
| short-high-long | short | high | 5,496 | 5,496 | 0.00% |
| medium-low-short | medium | low | 7,208 | 6,146 | 14.73% |
| medium-low-long | medium | low | 7,280 | 6,218 | 14.59% |
| medium-high-short | medium | high | 7,406 | 6,344 | 14.34% |
| medium-high-long | medium | high | 7,478 | 6,416 | 14.20% |
| long-low-short | long | low | 10,190 | 6,996 | 31.34% |
| long-low-long | long | low | 10,262 | 7,068 | 31.12% |
| long-high-short | long | high | 10,388 | 7,194 | 30.75% |
| long-high-long | long | high | 10,460 | 7,266 | 30.54% |

**结论**：同一批长上下文任务上，prompt 平均缩短 15.13%，同时当前请求保留率 100.00%——收益不是靠裁掉关键信息换来的。

## 3. 记忆系统（features/memory.py）

| 变体 | 重复读取次数 | 平均工具步数 | 平均尝试次数 | 任务正确率 | 记忆命中率 |
| --- | --- | --- | --- | --- | --- |
| memory_on | 0 | 0.00 | 1.00 | 100.00% | 100.00% |
| memory_off | 36 | 1.00 | 2.00 | 100.00% | 0.00% |
| memory_irrelevant | 36 | 1.00 | 2.00 | 100.00% | 0.00% |

**结论**：开启记忆后重复读取从 36 次降到 0 次，平均工具步数与模型往返次数同步下降，正确率与对照组持平——是净收益，不是用正确率换来的。

## 4. 检查点与恢复（checkpoint.py）

| 变体 | 恢复成功率 | 过期重锚定率 | 工作区漂移检出率 | 误接受率 |
| --- | --- | --- | --- | --- |
| resume_enabled | 90.00% | 100.00% | 100.00% | 0.00% |
| resume_disabled | 0.00% | 0.00% | 0.00% | 0.00% |

**逐任务明细（开启恢复）**

| 任务 | 类别 | 恢复状态 | 是否恢复成功 | 误接受 |
| --- | --- | --- | --- | --- |
| checkpoint_resume_goal | checkpoint_resume | partial-stale | 是 | 否 |
| checkpoint_resume_goal | checkpoint_resume | partial-stale | 是 | 否 |
| checkpoint_resume_goal | checkpoint_resume | partial-stale | 是 | 否 |
| checkpoint_resume_files | checkpoint_resume | partial-stale | 是 | 否 |
| checkpoint_resume_files | checkpoint_resume | partial-stale | 是 | 否 |
| checkpoint_resume_files | checkpoint_resume | partial-stale | 是 | 否 |
| partial_stale_single | partial_stale | partial-stale | 是 | 否 |
| partial_stale_single | partial_stale | partial-stale | 是 | 否 |
| partial_stale_single | partial_stale | partial-stale | 是 | 否 |
| partial_stale_multi | partial_stale | partial-stale | 是 | 否 |
| partial_stale_multi | partial_stale | partial-stale | 是 | 否 |
| partial_stale_multi | partial_stale | partial-stale | 是 | 否 |
| workspace_mismatch_fingerprint | workspace_mismatch | workspace-mismatch | 是 | 否 |
| workspace_mismatch_fingerprint | workspace_mismatch | workspace-mismatch | 是 | 否 |
| workspace_mismatch_fingerprint | workspace_mismatch | workspace-mismatch | 是 | 否 |
| workspace_mismatch_runtime | workspace_mismatch | workspace-mismatch | 是 | 否 |
| workspace_mismatch_runtime | workspace_mismatch | workspace-mismatch | 是 | 否 |
| workspace_mismatch_runtime | workspace_mismatch | workspace-mismatch | 是 | 否 |
| schema_mismatch_version | schema_mismatch | schema-mismatch | 是 | 否 |
| schema_mismatch_version | schema_mismatch | schema-mismatch | 是 | 否 |
| schema_mismatch_version | schema_mismatch | schema-mismatch | 是 | 否 |
| schema_mismatch_missing | schema_mismatch | no-checkpoint | 否 | 否 |
| schema_mismatch_missing | schema_mismatch | no-checkpoint | 否 | 否 |
| schema_mismatch_missing | schema_mismatch | no-checkpoint | 否 | 否 |
| partial_success_shell | partial_success_recovery | partial-stale | 是 | 否 |
| partial_success_shell | partial_success_recovery | partial-stale | 是 | 否 |
| partial_success_shell | partial_success_recovery | partial-stale | 是 | 否 |
| partial_success_tool | partial_success_recovery | partial-stale | 是 | 否 |
| partial_success_tool | partial_success_recovery | partial-stale | 是 | 否 |
| partial_success_tool | partial_success_recovery | partial-stale | 是 | 否 |

**结论**：关掉检查点后恢复成功率直接归零，说明恢复完全依赖这套机制；唯一未恢复成功的是「故意不给任何恢复依据」的场景，而误接受率始终为 0——系统不会把不可信状态当成可信状态继续跑。

## 5. 工具执行与安全（tool_executor.py / security.py）

| 指标 | 数值 |
| --- | --- |
| 治理场景数 | 10 |
| 运行次数（含重复） | 30 |
| 错误码分布 | {"invalid_arguments": 18, "approval_denied": 6, "repeated_identical_call": 3} |
| 安全事件分布 | {"path_escape": 6, "approval_denied": 3, "read_only_block": 3} |
| 环境跳过 | {"symlink_not_permitted": 3} |

**结论**：越界路径、非法参数、重复调用等场景都被拦截并结构化记录；环境跳过项（如 Windows 下不允许普通用户创建符号链接）如实标注，不计入失败。

## 6. 评测与可复现（evaluation/）

| 项 | 数值 |
| --- | --- |
| harness 任务数 | 12 |
| 可复现性字段 | {"decoding": {"max_new_tokens": 64, "temperature": 0.0, "top_p": 1.0}, "fixture_snapshot_id": "sha256:1bac1437e9e4a567cf2314c418bebd163324f4dc3006b528eb28eeb2a281218e", "locale": "Chinese (Simplified)_China.936", "model_name": "FakeModelClient", "model_version": "scripted-deterministic", "timezone": "Asia/Shanghai"} |
| 产物目录 | D:\AI_Project_clean\artifacts |

**产物清单**

- `artifacts/harness-regression-v2.json`　12 个任务逐条明细
- `artifacts/context-ablation-v2.json`　12 组配置的 prompt 与压缩率
- `artifacts/memory-ablation-v2.json`　12 任务 × 3 变体
- `artifacts/recovery-ablation-v2.json`　10 任务 × 2 变体
- `artifacts/security-suite.json`　安全治理场景
- `docs/metrics/plane-benchmark-core-report.md`　核心报告（英文指标名）
- `docs/metrics/module-metrics.md`　**本文件**

**结论**：评测全程离线、可重复执行，产物落盘可复查；指标口径与原始产物一一对应，不存在手工填写的数字。

## 7. 提示词缓存（providers/clients.py）

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 缓存命中率 | 离线不可测 | 本地没有真实后端缓存，只有真实 provider 实验能测 |
| 需运行 | `scripts/run_provider_experiments.py` | 会消耗真实 token，产出 pass_rate / attempts / tool_steps / cache_hit_rate |

**结论**：这一层的数字必须来自真实 provider，离线报告里如实标注为不可测，不用占位数字凑格式。

---

口径边界：Harness 回归只证明 runtime 合同稳定，不证明模型能力上限；上下文 / 记忆 / 恢复三组消融只证明模块收益，不与 provider benchmark 混写。
