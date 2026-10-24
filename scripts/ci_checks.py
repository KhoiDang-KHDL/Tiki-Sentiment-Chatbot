"""Static checks using only repository files, never private env values."""
import json
from pathlib import Path
import tomllib
import yaml


def main():
    root = Path(__file__).resolve().parents[1]
    count = 0
    for directory in ('source', 'scripts', 'tests', 'airflow/dags'):
        for path in (root / directory).rglob('*.py'):
            compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec')
            count += 1
    for path in (root / 'monitoring').rglob('*.yml'):
        yaml.safe_load(path.read_text(encoding='utf-8'))
    for name in ('docker-compose.yml', 'docker-compose.airflow.yml', '.github/workflows/ci.yml'):
        yaml.safe_load((root / name).read_text(encoding='utf-8'))
    tomllib.loads((root / '.chainlit/config.toml').read_text(encoding='utf-8'))
    dashboard = json.loads((root / 'monitoring/grafana/dashboards/tiki-api.json').read_text(encoding='utf-8'))
    if dashboard.get('uid') != 'tiki-api' or not dashboard.get('panels'):
        raise ValueError('Grafana dashboard is missing its UID or panels')
    print(f'Compiled {count} Python files; YAML, TOML and Grafana JSON are valid.')


if __name__ == '__main__':
    main()
