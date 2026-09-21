"""plane 自身配置与目标项目配置的优先级测试。"""

import os
from unittest.mock import patch

import plane as plane_pkg
import plane.config as plane_config
from plane.cli import _env_file_names


def _workspace(tmp_path, name):
    target = tmp_path / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text("demo\n", encoding="utf-8")
    return target


def _args(target):
    return plane_pkg.build_arg_parser().parse_args(["--cwd", str(target)])


def test_plane_config_is_used_when_workspace_has_no_env(tmp_path, monkeypatch):
    plane_env = tmp_path / "plane.env"
    plane_env.write_text(
        "OPENAI_API_KEY=sk-from-plane\n"
        "OPENAI_API_BASE=https://plane.example/v1\n"
        "OPENAI_MODEL=plane-model\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plane_config, "plane_config_paths", lambda: [plane_env])
    workspace = _workspace(tmp_path, "bare-project")

    with patch.dict(os.environ, {}, clear=True):
        agent = plane_pkg.build_agent(_args(workspace))

    assert agent.model_client.base_url.startswith("https://plane.example")
    assert agent.model_client.model == "plane-model"


def test_workspace_env_is_ignored(tmp_path, monkeypatch):
    """工作目录里的 .env 属于那个项目自己，plane 不能拿它当自己的配置。"""
    plane_env = tmp_path / "plane.env"
    plane_env.write_text(
        "OPENAI_API_KEY=sk-plane\nOPENAI_API_BASE=https://plane.example/v1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plane_config, "plane_config_paths", lambda: [plane_env])
    workspace = _workspace(tmp_path, "project")
    (workspace / ".env").write_text(
        "OPENAI_API_KEY=sk-project\n"
        "OPENAI_API_BASE=https://project.example/v1\n"
        "OPENAI_MODEL=project-model\n",
        encoding="utf-8",
    )

    with patch.dict(os.environ, {}, clear=True):
        agent = plane_pkg.build_agent(_args(workspace))

    assert agent.model_client.base_url.startswith("https://plane.example")
    assert agent.model_client.model != "project-model"


def test_workspace_env_directory_does_not_break_startup(tmp_path, monkeypatch):
    """工作目录里存在名为 .env 的目录（比如误用成 venv 名）时，plane 仍要能启动。"""
    monkeypatch.setattr(plane_config, "plane_config_paths", lambda: [])
    workspace = _workspace(tmp_path, "envdir")
    (workspace / ".env").mkdir()

    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-deepseek"}, clear=True):
        agent = plane_pkg.build_agent(_args(workspace))

    assert agent is not None
    assert _env_file_names() == set()


def test_plane_config_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(plane_config, "plane_config_paths", lambda: [])
    workspace = _workspace(tmp_path, "no-config")

    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-deepseek"}, clear=True):
        agent = plane_pkg.build_agent(_args(workspace))

    assert "deepseek" in agent.model_client.base_url
