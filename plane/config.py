import os
import re
from pathlib import Path


ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _strip_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export "):].strip()
    if "=" not in line:
        raise ValueError(f"invalid .env line: {line}")
    name, value = line.split("=", 1)
    name = name.strip()
    if not ENV_KEY_PATTERN.match(name):
        raise ValueError(f"invalid .env variable name: {name}")
    return name, _strip_quotes(value)


def find_project_env(start):
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for path in (current, *current.parents):
        env_path = path / ".env"
        if env_path.is_file():
            return env_path
    return None


def env_file_names(env_path):
    """返回某个 .env 文件里定义的变量名集合；路径不是文件时返回空集合。"""
    env_path = Path(env_path)
    if not env_path.is_file():
        return set()
    names = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed:
            names.add(parsed[0])
    return names


def load_env_file(env_path, override=True):
    """加载指定的 .env 文件；文件不存在时返回空 dict。"""
    env_path = Path(env_path)
    if not env_path.is_file():
        return {}
    loaded = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        name, value = parsed
        loaded[name] = value
        if override or name not in os.environ:
            os.environ[name] = value
    return loaded


def load_project_env(start, override=True):
    """加载某个目录树里的 .env。

    注意：plane 默认**不调用**这个函数。工作目录里的 .env 属于那个项目自己，
    里面很可能是它自己的 OPENAI_API_KEY、数据库地址之类的配置，不应该影响 plane。
    需要给某个项目单独配置 plane 时，用 PLANE_CONFIG_FILE 指向专用文件。
    """
    env_path = find_project_env(start)
    if env_path is None:
        return {}
    return load_env_file(env_path, override=override)


def plane_config_paths():
    """plane 自己的配置文件位置（按优先级从低到高）。

    默认读取两处：`~/.plane/.env` 与 plane 安装目录下的 `.env`（后者覆盖前者）。
    可用 PLANE_CONFIG_FILE 指定唯一配置文件；指向不存在的路径即等于关闭全局配置。
    """
    override = str(os.environ.get("PLANE_CONFIG_FILE", "") or "").strip()
    if override:
        candidates = [Path(override)]
    else:
        candidates = []
        try:
            candidates.append(Path.home() / ".plane" / ".env")
        except RuntimeError:
            # 环境里没有 HOME/USERPROFILE 时 Path.home() 会抛错，此时只用安装目录配置。
            pass
        candidates.append(Path(__file__).resolve().parent.parent / ".env")
    return [path for path in candidates if path.is_file()]


def load_plane_env(override=True):
    """加载 plane 自己的配置，作为唯一的全局配置基线。"""
    loaded = {}
    for path in plane_config_paths():
        loaded.update(load_env_file(path, override=override))
    return loaded


def provider_env(name, legacy_names=(), default=""):
    for env_name in (name, *legacy_names):
        value = os.environ.get(env_name)
        if value:
            return value
    return default
