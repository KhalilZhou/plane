"""--cwd 参数校验的测试。"""

import pytest

import plane as plane_pkg


def _args(target, *extra):
    return plane_pkg.build_arg_parser().parse_args(["--cwd", str(target), *extra])


def test_cwd_directory_still_works(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")

    agent = plane_pkg.build_agent(_args(tmp_path))

    assert agent.workspace.cwd == str(tmp_path)


def test_cwd_rejects_file_with_clear_error(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("print('hi')\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expects a directory"):
        plane_pkg.build_agent(_args(target))


def test_cwd_rejects_missing_path(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        plane_pkg.build_agent(_args(tmp_path / "nope"))
