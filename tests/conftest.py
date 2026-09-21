"""测试环境隔离：默认不读取本机真实的 plane 全局配置。

直接替换 plane.config.plane_config_paths，而不是只设置环境变量——
因为有些测试会用 patch.dict(..., clear=True) 清空环境变量，那样环境变量式的隔离会失效。

plane.cli 里若也按名字导入了 plane_config_paths（REPL 的 /cwd 命令会用到），
需要一并替换，否则打桩只对 config 模块生效。
"""

import pytest

import plane.cli as plane_cli
import plane.config as plane_config


@pytest.fixture(autouse=True)
def isolate_plane_config(monkeypatch):
    monkeypatch.setattr(plane_config, "plane_config_paths", lambda: [])
    if hasattr(plane_cli, "plane_config_paths"):
        monkeypatch.setattr(plane_cli, "plane_config_paths", lambda: [])
