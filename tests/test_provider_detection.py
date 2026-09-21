"""provider 自动推断的行为测试。"""

import os
from unittest.mock import patch

import plane as plane_pkg


def _build(tmp_path, argv, env):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    with patch.dict(os.environ, env, clear=True):
        args = plane_pkg.build_arg_parser().parse_args(["--cwd", str(tmp_path), *argv])
        return plane_pkg.build_agent(args)


def test_openai_key_resolves_openai(tmp_path):
    agent = _build(tmp_path, [], {"OPENAI_API_KEY": "sk-test"})
    assert "api.openai.com" in agent.model_client.base_url


def test_anthropic_key_resolves_anthropic(tmp_path):
    agent = _build(tmp_path, [], {"ANTHROPIC_API_KEY": "sk-test"})
    assert "api.anthropic.com" in agent.model_client.base_url


def test_deepseek_key_resolves_deepseek(tmp_path):
    agent = _build(tmp_path, [], {"DEEPSEEK_API_KEY": "sk-test"})
    assert "deepseek" in agent.model_client.base_url


def test_unknown_key_names_are_ignored(tmp_path):
    agent = _build(tmp_path, [], {"PLANE_GATEWAY_API_KEY": "sk-test"})
    assert "deepseek" in agent.model_client.base_url


def test_openai_wins_over_anthropic_when_both_configured(tmp_path):
    agent = _build(tmp_path, [], {"OPENAI_API_KEY": "sk-a", "ANTHROPIC_API_KEY": "sk-b"})
    assert "api.openai.com" in agent.model_client.base_url


def test_plane_provider_env_overrides_inference(tmp_path):
    agent = _build(tmp_path, [], {"PLANE_PROVIDER": "anthropic", "OPENAI_API_KEY": "sk-test"})
    assert "api.anthropic.com" in agent.model_client.base_url


def test_explicit_flag_overrides_env_and_credentials(tmp_path):
    agent = _build(tmp_path, ["--provider", "openai"], {"DEEPSEEK_API_KEY": "sk-test"})
    assert "api.openai.com" in agent.model_client.base_url
