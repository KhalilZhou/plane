# plane

一个运行在终端里的轻量本地 coding agent。它在当前仓库中工作：先读取工作区信息，再用一组受约束的工具读文件、改文件、执行命令，并把会话与运行数据保存在本地 `.plane/` 目录。

## 适用场景

- 在本地仓库中排查测试失败、定位缺陷
- 阅读现有代码并给出修改建议
- 基于仓库现状做小步迭代，而不是脱离代码空想
- 在会话中保留上下文，支持接着上一次继续工作

## 环境要求

- Python 3.10+

## 安装

在项目根目录执行：

```bash
pip install -e .
```

安装后可用的入口：

```bash
plane
python -m plane
```

## 配置

在项目根目录创建 `.env`（可直接复制 `.env.example`），选择要使用的模型后端并填入密钥。

配置优先级：

```text
显式 CLI 参数 > .env 中的 PLANE_* 变量 > 同名旧环境变量 > 代码默认值
```

### provider 是怎么选出来的

不指定 `--provider` 时，plane 按下面顺序决定后端：

1. `--provider`（显式指定，优先级最高）
2. `.env` 或环境变量里的 `PLANE_PROVIDER`
3. 从已配置的凭据自动推断：`openai` → `anthropic` → `deepseek`
4. 都没有时回退到 `deepseek`

自动推断结果会写到 stderr，例如 `[plane] provider=openai (auto-detected from credentials)`；stdout 只保留模型回答本身，方便管道与脚本使用。想固定后端，在 `.env` 里写 `PLANE_PROVIDER=openai` 即可。

`ollama` 没有凭据可供推断，必须显式 `--provider ollama`。

### 配置从哪里来

不需要给每个被处理的文件夹都放配置文件。按优先级从高到低：

```text
显式 CLI 参数
> plane 自己的配置：plane 安装目录下的 .env，或 ~/.plane/.env
> shell / 系统环境变量
> 代码默认值
```

也就是说：把 key 放在 **plane 自己的 `.env`** 里，之后无论 `--cwd` 指向哪个文件夹都能直接用。
想指定别的配置文件位置，设置 `PLANE_CONFIG_FILE=<路径>`；把它指向不存在的路径即可关闭全局配置。

**工作目录里的 `.env` 会被完全忽略。** 那是被处理项目自己的应用配置（里面可能有它自己的
`OPENAI_API_KEY`、数据库地址等），plane 不会读它，也不会拿它当自己的模型配置。
需要给某个项目单独指定 plane 配置时，用 `PLANE_CONFIG_FILE=<该项目的 plane 配置>`。

各后端对应的变量：

| provider | base URL | API key | model |
| --- | --- | --- | --- |
| `deepseek` | `PLANE_DEEPSEEK_API_BASE` | `PLANE_DEEPSEEK_API_KEY` | `PLANE_DEEPSEEK_MODEL` |
| `openai` | `PLANE_OPENAI_API_BASE` | `PLANE_OPENAI_API_KEY` | `PLANE_OPENAI_MODEL` |
| `anthropic` | `PLANE_ANTHROPIC_API_BASE` | `PLANE_ANTHROPIC_API_KEY` | `PLANE_ANTHROPIC_MODEL` |
| `ollama` | `--host` | 不需要 | `--model` |

最小配置示例（OpenAI 兼容接口）：

```bash
PLANE_OPENAI_API_BASE="https://your-endpoint.example/v1"
PLANE_OPENAI_API_KEY="your-api-key"
PLANE_OPENAI_MODEL="your-model"
```

`.env` 已被 `.gitignore` 忽略，不要提交真实密钥。

## 快速开始

```bash
plane                                              # 交互模式
plane --provider openai                            # 指定模型后端
plane --cwd /path/to/repo                          # 指定工作目录
plane "inspect the failing tests and propose a fix" # 一次性任务
plane --resume latest                              # 继续上一次会话
plane --max-steps 20                               # 放宽单次请求的工具步数上限
```

常用参数：

- `--model` / `--base-url`：临时覆盖模型名与接口地址
- `--approval ask|auto|never`：审批策略，默认 `ask`
- `--max-new-tokens`：单轮模型输出上限
- `--secret-env-name`：额外的敏感环境变量名，用于 trace/report 脱敏

## 交互命令

| 命令 | 作用 |
| --- | --- |
| `/help` | 查看内置命令 |
| `/memory` | 查看当前工作记忆 |
| `/session` | 查看会话文件路径 |
| `/cwd <目录>` | 查看或切换工作目录（别名 `/cd`） |
| `/reset` | 清空当前会话的历史与记忆 |
| `/exit` / `/quit` | 退出 |

## 工具与安全

内置工具：`list_files`、`read_file`、`search`、`run_shell`、`write_file`、`patch_file`、`delegate`。

- 读类工具直接执行；写文件、打补丁、执行命令需要按审批策略确认。
- `delegate` 会启动一个只读的子 agent，用于受限的调查任务。
- 所有文件访问都锚定在工作区根目录内，越界路径会被拒绝。
- `run_shell` 只向子进程传递白名单环境变量，避免把密钥带进去。

## 运行数据

- `.plane/sessions/<session_id>.json`：会话状态（历史、记忆、checkpoint）
- `.plane/runs/<run_id>/task_state.json`：单次运行的状态快照
- `.plane/runs/<run_id>/trace.jsonl`：事件时间线
- `.plane/runs/<run_id>/report.json`：运行结束后的汇总报告

这些文件默认只保存在本地，不需要提交到版本库。

## 开发与测试

```bash
pytest tests -q
ruff check plane tests scripts
```


## 更多文档

README 只覆盖安装、配置与日常使用；下面两篇是本仓库的正式说明文档：

- 运行时结构与分层设计：[docs/architecture/agent-harness-v1-overview.md](docs/architecture/agent-harness-v1-overview.md)
- 评测口径与证据说明：[docs/review-pack/evaluation.md](docs/review-pack/evaluation.md)
