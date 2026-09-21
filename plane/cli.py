import argparse
import os
from pathlib import Path
import sys
import textwrap

from .config import (
    env_file_names,
    load_plane_env,
    plane_config_paths,
    provider_env,
)
from .providers.clients import AnthropicCompatibleModelClient, OllamaModelClient, OpenAICompatibleModelClient
from .runtime import Plane, SessionStore
from .workspace import WorkspaceContext

DEFAULT_SECRET_ENV_NAMES = (
    "PLANE_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_API_TOKEN",
    "PLANE_ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "PLANE_DEEPSEEK_API_KEY",
    "DEEPSEEK_API_KEY",
    "GITHUB_PAT",
    "GH_PAT",
)

HELP_DETAILS = textwrap.dedent(
    """\
    Commands:
    /help    Show this help message.
    /memory  Show the agent's distilled working memory.
    /session Show the path to the saved session file.
    /cwd     Show or change the workspace directory (alias: /cd).
    /reset   Clear the current session history and memory.
    /exit    Exit the agent.
    """
).strip()


DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OPENAI_MODEL = "gpt-5.6-terra"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"
SECRET_ENV_NAMES_VAR = "PLANE_SECRET_ENV_NAMES"

PROVIDER_ENV_VAR = "PLANE_PROVIDER"
PROVIDER_CHOICES = ("ollama", "openai", "anthropic", "deepseek")
DEFAULT_PROVIDER = "deepseek"
# 按 --provider 的候选顺序检查专用凭据；共享 key 放在最后兜底。
PROVIDER_CREDENTIAL_NAMES = (
    ("openai", ("PLANE_OPENAI_API_KEY", "OPENAI_API_KEY", "OPENAI_API_TOKEN")),
    ("anthropic", ("PLANE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")),
    ("deepseek", ("PLANE_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY")),
)


def infer_provider_from_credentials(env=None):
    """从已配置的凭据推断 provider；没有任何可用凭据时返回空串。"""
    lookup = os.environ if env is None else env

    def has_value(name):
        return bool(str(lookup.get(name, "") or "").strip())

    for provider, names in PROVIDER_CREDENTIAL_NAMES:
        if any(has_value(name) for name in names):
            return provider
    return ""


def resolve_provider(args, env=None, announce=True):
    """决定本次运行使用哪个 provider。

    优先级：--provider > PLANE_PROVIDER > 凭据推断 > 默认值（deepseek）。
    推断结果只写到 stderr，避免污染一次性任务的 stdout。
    """
    explicit = getattr(args, "provider", None)
    if explicit:
        return explicit
    lookup = os.environ if env is None else env
    configured = str(lookup.get(PROVIDER_ENV_VAR, "") or "").strip().lower()
    if configured in PROVIDER_CHOICES:
        if announce:
            print(f"[plane] provider={configured} (from {PROVIDER_ENV_VAR})", file=sys.stderr)
        return configured
    inferred = infer_provider_from_credentials(lookup)
    if inferred:
        if announce:
            print(f"[plane] provider={inferred} (auto-detected from credentials)", file=sys.stderr)
        return inferred
    return DEFAULT_PROVIDER


def _effective_model(args, provider):
    # 模型选择优先级：
    # 1. 用户显式传入 --model
    # 2. provider 对应的环境变量
    # 3. 代码里的默认值
    explicit_model = getattr(args, "model", None)
    if explicit_model:
        return explicit_model
    if provider == "openai":
        model = provider_env("PLANE_OPENAI_MODEL", ("OPENAI_MODEL",))
        if model:
            return model
        return DEFAULT_OPENAI_MODEL
    if provider == "anthropic":
        model = provider_env("PLANE_ANTHROPIC_MODEL", ("ANTHROPIC_MODEL",))
        if model:
            return model
        return DEFAULT_ANTHROPIC_MODEL
    if provider == "deepseek":
        model = provider_env("PLANE_DEEPSEEK_MODEL", ("DEEPSEEK_MODEL",))
        if model:
            return model
        return DEFAULT_DEEPSEEK_MODEL
    return DEFAULT_OLLAMA_MODEL


def _configured_secret_names(args):
    configured_secret_names = set(DEFAULT_SECRET_ENV_NAMES)
    configured_secret_names.update(str(name).upper() for name in args.secret_env_names)
    extra_names = os.environ.get(SECRET_ENV_NAMES_VAR, "")
    if extra_names.strip():
        configured_secret_names.update(
            item.strip().upper()
            for item in extra_names.split(",")
            if item.strip()
        )
    return sorted(configured_secret_names)


def _build_model_client(args):
    provider = getattr(args, "provider", "deepseek")
    # CLI 只负责把 provider 选择翻译成具体 client。
    # 真正的提示词格式、缓存支持、HTTP 协议差异，都封装在 models.py 里。
    if provider == "openai":
        model = _effective_model(args, provider)
        base_url = getattr(args, "base_url", None) or provider_env("PLANE_OPENAI_API_BASE", ("OPENAI_API_BASE",), DEFAULT_OPENAI_BASE_URL)
        api_key = provider_env(
            "PLANE_OPENAI_API_KEY",
            ("OPENAI_API_KEY",),
        )
        return OpenAICompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=getattr(args, "openai_timeout", getattr(args, "ollama_timeout", 300)),
        )
    if provider == "anthropic":
        model = _effective_model(args, provider)
        base_url = getattr(args, "base_url", None) or provider_env("PLANE_ANTHROPIC_API_BASE", ("ANTHROPIC_API_BASE",), DEFAULT_ANTHROPIC_BASE_URL)
        api_key = provider_env(
            "PLANE_ANTHROPIC_API_KEY",
            ("ANTHROPIC_API_KEY",),
        )
        return AnthropicCompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=getattr(args, "openai_timeout", getattr(args, "ollama_timeout", 300)),
        )
    if provider == "deepseek":
        model = _effective_model(args, provider)
        base_url = getattr(args, "base_url", None) or provider_env("PLANE_DEEPSEEK_API_BASE", ("DEEPSEEK_API_BASE",), DEFAULT_DEEPSEEK_BASE_URL)
        api_key = provider_env("PLANE_DEEPSEEK_API_KEY", ("DEEPSEEK_API_KEY",))
        return AnthropicCompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=getattr(args, "openai_timeout", getattr(args, "ollama_timeout", 300)),
        )

    model = _effective_model(args, provider)
    host = getattr(args, "host", DEFAULT_OLLAMA_HOST)
    return OllamaModelClient(
        model=model,
        host=host,
        temperature=args.temperature,
        top_p=args.top_p,
        timeout=args.ollama_timeout,
    )


def build_agent(args):
    """根据 CLI 参数装配出一个可运行的 Plane 实例。

    为什么存在：
    命令行参数只是字符串和开关，runtime 需要的是已经装配好的对象图：
    model client、workspace snapshot、session store、secret 配置等。
    这个函数负责把“启动参数”翻译成“agent 运行现场”。

    输入 / 输出：
    - 输入：`argparse` 解析后的 `args`
    - 输出：一个新的 `Plane`，或一个从旧 session 恢复出来的 `Plane`

    在 agent 链路里的位置：
    它是整个程序启动链路里最靠近 runtime 的装配点。`main()` 先调它，
    得到 agent 后，后面无论是 one-shot 还是 REPL 模式，都会落到 `ask()`。
    """
    # 这里是 CLI 到 runtime 的装配点：
    # 先采集工作区快照和加载项目级环境，再整理 secret 名单、模型后端和 session。
    target = Path(args.cwd)
    if not target.exists():
        raise ValueError(f"--cwd path does not exist: {args.cwd}")
    if target.is_file():
        raise ValueError(
            f"--cwd expects a directory, got a file: {args.cwd}. "
            "Point it at the folder that contains the file instead."
        )
    workspace = WorkspaceContext.build(args.cwd)
    load_plane_env()  # plane 自己的配置（安装目录 .env 或 ~/.plane/.env）
    # 工作目录里的 .env 不读：那是那个项目自己的应用配置，不该影响 plane 的模型设置。
    # provider 解析放在加载 .env 之后，这样 .env 里的凭据也能参与推断。
    args.provider = resolve_provider(args)
    configured_secret_names = _configured_secret_names(args)
    store = SessionStore(workspace.repo_root + "/.plane/sessions")
    model = _build_model_client(args)
    session_id = args.resume
    if session_id == "latest":
        session_id = store.latest()
    if session_id:
        return Plane.from_session(
            model_client=model,
            workspace=workspace,
            session_store=store,
            session_id=session_id,
            approval_policy=args.approval,
            max_steps=args.max_steps,
            max_new_tokens=args.max_new_tokens,
            secret_env_names=configured_secret_names,
        )
    return Plane(
        model_client=model,
        workspace=workspace,
        session_store=store,
        approval_policy=args.approval,
        max_steps=args.max_steps,
        max_new_tokens=args.max_new_tokens,
        secret_env_names=configured_secret_names,
    )
    


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Minimal coding agent for DeepSeek, OpenAI-compatible, Anthropic-compatible, or Ollama models.",
    )
    parser.add_argument("prompt", nargs="*", help="Optional one-shot prompt.")
    parser.add_argument("--cwd", default=".", help="Workspace directory.")
    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default=None,
        help=(
            "Model backend to use. When omitted, plane resolves it from PLANE_PROVIDER "
            "or the configured credentials (openai -> anthropic -> deepseek), "
            "falling back to deepseek."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name override. Defaults to qwen3.5:4b for Ollama, PLANE_OPENAI_MODEL for openai, PLANE_ANTHROPIC_MODEL for anthropic, and PLANE_DEEPSEEK_MODEL for deepseek when set.",
    )
    parser.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help="Ollama server URL.")
    parser.add_argument("--base-url", default=None, help="Provider API base URL for deepseek, openai, or anthropic.")
    parser.add_argument("--ollama-timeout", type=int, default=300, help="Ollama request timeout in seconds.")
    parser.add_argument("--openai-timeout", type=int, default=300, help="OpenAI-compatible request timeout in seconds.")
    parser.add_argument("--resume", default=None, help="Session id to resume or 'latest'.")
    parser.add_argument("--approval", choices=("ask", "auto", "never"), default="ask", help="Approval policy for risky tools.")
    parser.add_argument(
        "--secret-env-name",
        dest="secret_env_names",
        action="append",
        default=[],
        help="Extra environment variable names to treat as secrets for trace/report redaction.",
    )
    parser.add_argument("--max-steps", type=int, default=6, help="Maximum tool/model iterations per request.")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Maximum model output tokens per step.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature sent to Ollama.")
    parser.add_argument("--top-p", type=float, default=0.9, help="Top-p sampling value sent to Ollama.")
    return parser


def _env_file_names():
    """返回 plane 自身配置里定义过的变量名集合。

    只统计 plane 自己的配置文件：工作目录里的 .env 属于被处理的项目，
    既不参与 plane 的配置解析，也就不需要为它做变量追踪。
    """
    names = set()
    for path in plane_config_paths():
        names |= env_file_names(path)
    return names


def switch_workspace(args, target_path, loaded_env_names):
    """切换到新的工作目录，返回 (agent, 新目录的 env 变量名, 被清理掉的旧变量名)。"""
    target = Path(target_path)
    if not target.exists():
        raise ValueError(f"path does not exist: {target_path}")
    if target.is_file():
        raise ValueError(f"expects a directory, got a file: {target_path}")

    # 先清掉上一个目录独有的 .env 变量，避免它的 base/key/model 影响新目录的解析。
    new_names = _env_file_names()
    stale = sorted(set(loaded_env_names) - new_names)
    cleared_values = {name: os.environ[name] for name in stale if name in os.environ}
    for name in stale:
        os.environ.pop(name, None)

    original_cwd = args.cwd
    args.cwd = str(target)
    try:
        agent = build_agent(args)
    except Exception:
        args.cwd = original_cwd
        os.environ.update(cleared_values)
        raise
    return agent, new_names, stale


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        agent = build_agent(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    loaded_env_names = _env_file_names()

    if args.prompt:
        # one-shot 模式：只跑一次 ask，不进入 REPL 循环。
        prompt = " ".join(args.prompt).strip()
        if prompt:
            print()
            try:
                print(agent.ask(prompt))
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        return 0

    while True:
        # 交互模式：每次读取一条用户输入，交给同一个 agent，
        # 因此 session history 和 working memory 会跨轮延续。
        try:
            user_input = input("\nplane> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            return 0
        if user_input == "/help":
            print(HELP_DETAILS)
            continue
        if user_input == "/memory":
            print(agent.memory_text())
            continue
        if user_input == "/session":
            print(agent.session_path)
            continue
        if user_input == "/reset":
            agent.reset()
            print("session reset")
            continue

        if user_input in {"/cwd", "/cd"} or user_input.startswith(("/cwd ", "/cd ")):
            target = user_input.split(None, 1)[1].strip() if " " in user_input else ""
            if not target:
                print(f"workspace: {agent.workspace.cwd}")
                print(f"repo_root: {agent.workspace.repo_root}")
                print(f"session:   {agent.session_path}")
                continue
            try:
                new_agent, new_names, stale = switch_workspace(args, target, loaded_env_names)
            except ValueError as exc:
                print(f"cannot switch workspace: {exc}", file=sys.stderr)
                continue
            agent = new_agent
            loaded_env_names = new_names
            if stale:
                print("cleared stale env from previous workspace: " + ", ".join(stale))
            print(f"workspace switched to: {agent.workspace.cwd}")
            print(f"new session: {agent.session_path}")
            continue

        print()
        try:
            print(agent.ask(user_input))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
