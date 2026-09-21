# 评测说明

本目录记录评测方式与结果，便于对比不同版本之间的运行时行为。

## Project pitch（项目定位）

plane 是一个面向代码仓库的轻量本地 coding agent：在模型之外提供仓库上下文、受约束的工具集、任务状态、记忆与可审计的运行工件，用于排错、改码、跑测试这类多步工程任务。

## Architecture map（架构地图）

| 模块 | 职责 |
| --- | --- |
| `plane/cli.py` | 组装配置、模型后端、工作区与运行时，进入交互或一次性任务 |
| `plane/runtime.py` | 运行时门面：拼 prompt、解析输出、执行工具、写工件 |
| `plane/context_manager.py` | 按预算在 prefix、记忆、相关记忆、历史与当前请求之间分配上下文 |
| `plane/tools.py` | 工具白名单、参数校验与执行 |
| `plane/run_store.py` | 单次运行的状态、事件与报告落盘 |

## Benchmark evidence（评测证据）

- 任务集定义在 `benchmarks/coding_tasks.json`，包含提示词、示例仓库、工具白名单、步数预算、期望工件与验收脚本。
- 任务通过需要同时满足：在预算内完成、验收脚本返回 0、期望工件存在、正常返回最终答案。
- 失败会归类为缺少工件、超出预算、验收失败、异常停止或未知原因。
- 评测工件记录代码提交、示例仓库快照摘要、模型名称与版本、解码参数、时区与区域设置，保证可复现。

## Sample run artifact list（工件清单）

- `.plane/runs/<run_id>/task_state.json`
- `.plane/runs/<run_id>/trace.jsonl`
- `.plane/runs/<run_id>/report.json`
- `.plane/sessions/<session_id>.json`
