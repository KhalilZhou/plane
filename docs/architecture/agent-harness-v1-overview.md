# 运行时结构说明

本文描述 plane 的运行时结构：一个围绕模型的控制循环，加上仓库上下文、受约束的工具、任务状态、记忆与可审计的运行工件。

## 运行时流程

1. 构建工作区上下文与运行时前缀。
2. 把用户请求写入会话历史。
3. 为本次运行创建任务状态，并生成 run 目录。
4. 按预算拼装 prompt。
5. 请求模型返回结果。
6. 解析模型输出：工具调用、格式重试或最终答案。
7. 按运行时策略校验并执行工具。
8. 持续写入任务状态、事件、checkpoint 与报告。

## 分层

| 层 | 模块 | 职责 |
| --- | --- | --- |
| 入口 | `plane/cli.py` | 参数解析、provider 装配、REPL 与一次性任务 |
| 运行时 | `plane/runtime.py` | agent 门面：拼 prompt、解析输出、执行工具、写工件 |
| 控制循环 | `plane/agent_loop.py` | 每轮"组装 → 请求 → 解析 → 执行 → 记录" |
| 上下文 | `plane/context_manager.py`、`plane/prompt_prefix.py` | 前缀构建与预算控制 |
| 工具 | `plane/tools.py`、`plane/tool_executor.py`、`plane/tool_context.py` | 工具定义、校验、执行与窄上下文 |
| 记忆 | `plane/features/memory.py` | 工作记忆、文件摘要与长期记忆 |
| 状态与工件 | `plane/task_state.py`、`plane/run_store.py`、`plane/session_store.py`、`plane/checkpoint.py` | 状态机、落盘与恢复 |
| 模型适配 | `plane/providers/clients.py` | 统一各后端的 `complete()` 接口 |

## 运行工件

- `task_state.json`：本次运行的尝试次数、工具步数、状态、停止原因与最终答案。
- `trace.jsonl`：prompt 构建、模型请求、工具执行、checkpoint、结束等事件的时间线。
- `report.json`：运行汇总，包括 prompt 元数据、记忆变更与执行统计。

## Agent Harness v1

上述运行时结构即 Agent Harness v1：模型之外的控制循环，加上仓库上下文、受约束工具、任务状态（task state）、记忆与可审计运行工件。

## 上下文预算

每次请求的 prompt 由固定顺序的若干段组成：稳定前缀、记忆、相关记忆、历史、当前请求。各段有独立预算与下限，超出总预算时按固定顺序收缩；当前用户请求永不裁剪。
