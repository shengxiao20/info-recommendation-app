"""Load a required KEY=value file without external dependencies or secret defaults."""
import os
import re


def load_environment(path):
    # Read and validate the entire file before changing the process environment.
    entries = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError(f'{path.name} 第 {number} 行格式错误：应为 KEY=value')
        if name in entries:
            raise ValueError(f'{path.name} 第 {number} 行重复配置：{name}')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'{path.name} 第 {number} 行引号未闭合')
            value = value[1:-1]
        entries[name] = value
    # Explicitly exported variables take precedence over values in .env.
    for name, value in entries.items():
        os.environ.setdefault(name, value)


def require_environment(name):
    if name not in os.environ:
        raise ValueError(f'缺少 {name}，请在 .env 中配置')
    value = os.environ[name].strip()
    if not value:
        raise ValueError(f'{name} 不能为空，请在 .env 中配置')
    return value
