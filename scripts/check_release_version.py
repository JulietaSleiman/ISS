"""Valida la versión sin importar PyQt ni ejecutar la aplicación o un build."""
import ast
import os
from pathlib import Path
import re
import sys


def read_version(source):
    module = ast.parse(Path(source).read_text(encoding='utf-8'))
    values = [
        node.value for node in module.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'CURRENT_VERSION' for target in node.targets)
    ]
    if len(values) != 1:
        raise ValueError('CURRENT_VERSION debe estar definida una sola vez.')
    value = ast.literal_eval(values[0])
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('CURRENT_VERSION debe tener formato numerico mayor.menor.parche.')
    return value


def validate_tag(tag, version):
    if not re.fullmatch(r'v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', tag):
        raise ValueError('Tag invalido: se requiere vMAYOR.MENOR.PARCHE.')
    if tag != 'v' + version:
        raise ValueError(f'El tag {tag} no coincide con CURRENT_VERSION={version}.')


def main():
    try:
        version = read_version(Path(__file__).resolve().parents[1] / 'src/core/updater.py')
        tag = os.environ.get('RELEASE_TAG')
        if tag is not None:
            validate_tag(tag, version)
        print(f'Version validada: {version}')
        return 0
    except (OSError, ValueError, SyntaxError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
