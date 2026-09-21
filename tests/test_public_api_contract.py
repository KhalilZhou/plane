from pathlib import Path

import plane
from plane import Plane, SessionStore, WorkspaceContext, build_agent, build_arg_parser, main


def test_public_api_exports_current_names_only():
    assert Plane is not None
    assert SessionStore is not None
    assert WorkspaceContext is not None
    assert callable(build_agent)
    assert callable(build_arg_parser)
    assert callable(main)
    assert not hasattr(plane, "MiniAgent")
    assert "MiniAgent" not in plane.__all__


def test_build_agent_returns_plane(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    args = build_arg_parser().parse_args(["--cwd", str(tmp_path), "--approval", "auto"])

    agent = build_agent(args)

    assert isinstance(agent, Plane)


def test_lightweight_package_split_uses_package_paths_without_legacy_shims():
    from plane.evaluation.evaluator import BenchmarkEvaluator
    from plane.evaluation.metrics import run_context_ablation_v2
    from plane.features.memory import LayeredMemory
    from plane.providers.clients import FakeModelClient as ProviderFakeModelClient

    assert BenchmarkEvaluator is not None
    assert LayeredMemory is not None
    assert ProviderFakeModelClient is not None
    assert callable(run_context_ablation_v2)
    for legacy_module in ("evaluator.py", "metrics.py", "models.py", "memory.py"):
        assert not (Path("plane") / legacy_module).exists()


def test_packaging_discovers_plane_subpackages():
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.setuptools.packages.find]" in pyproject_text
    assert 'include = ["plane*"]' in pyproject_text
