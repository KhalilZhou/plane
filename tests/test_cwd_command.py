"""REPL 的 /cwd 命令（切换工作目录）测试。"""

import os
from unittest.mock import patch

import pytest

import plane as plane_pkg
from plane.cli import _env_file_names, switch_workspace


def _prepare(target):
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text("demo\n", encoding="utf-8")


def _args(path):
    return plane_pkg.build_arg_parser().parse_args(["--cwd", str(path)])


def test_switch_workspace_moves_agent_and_session(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    _prepare(first)
    _prepare(second)

    args = _args(first)
    agent = plane_pkg.build_agent(args)
    names = _env_file_names()

    new_agent, new_names, stale = switch_workspace(args, str(second), names)

    assert new_agent.workspace.cwd == str(second)
    assert new_agent.session_path.parent.parent.parent == second
    assert new_names == set()
    assert stale == []
    assert args.cwd == str(second)


def test_switch_workspace_rejects_bad_targets(tmp_path):
    _prepare(tmp_path)
    args = _args(tmp_path)

    with pytest.raises(ValueError, match="does not exist"):
        switch_workspace(args, str(tmp_path / "nope"), set())

    target_file = tmp_path / "main.py"
    target_file.write_text("print('hi')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expects a directory"):
        switch_workspace(args, str(target_file), set())


def test_switch_workspace_does_not_read_workspace_env(tmp_path):
    """切换目录时，被处理项目自己的 .env 不该进入 plane 的运行环境。"""
    first = tmp_path / "a"
    second = tmp_path / "b"
    _prepare(first)
    _prepare(second)
    (first / ".env").write_text(
        "OPENAI_API_KEY=sk-old\nOPENAI_MODEL=old-model\n", encoding="utf-8"
    )

    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-keep"}, clear=True):
        args = _args(first)
        agent = plane_pkg.build_agent(args)
        names = _env_file_names()
        assert "OPENAI_API_KEY" not in os.environ
        assert os.environ["DEEPSEEK_API_KEY"] == "sk-keep"

        _, _, stale = switch_workspace(args, str(second), names)

        assert stale == []
        assert "OPENAI_API_KEY" not in os.environ
        assert os.environ["DEEPSEEK_API_KEY"] == "sk-keep"
