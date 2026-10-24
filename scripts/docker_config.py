"""Generate a private API env file; never print provider keys."""
import os
from pathlib import Path
import socket


def free_port(preferred, fallback):
    for port in (preferred, fallback):
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return str(port)
            except OSError:
                pass
    raise RuntimeError(f'Ports {preferred} and {fallback} are occupied; choose ports in .env.docker')


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / '.env.docker'
    if target.exists():
        print('.env.docker exists; keeping its configuration.')
        return
    # Called after set_env.ps1 has populated this process environment.
    from dotenv import dotenv_values
    values = {**dotenv_values(root / '.env'), **os.environ}
    template = root / '.env.docker.example'
    rows = []
    for line in template.read_text(encoding='utf-8').splitlines():
        if '=' not in line or line.startswith('#'):
            rows.append(line)
            continue
        name, default = line.split('=', 1)
        if name == 'API_HOST_PORT':
            value = free_port(8000, 8002)
        elif name == 'UI_HOST_PORT':
            value = free_port(8001, 8003)
        else:
            value = values.get(name, default) or default
        if any(character in value for character in ('\n', '\r', "'")):
            raise ValueError(f'Invalid env value for {name}')
        # Literal dotenv quoting prevents interpolation of $ in any credentials.
        rows.append(f"{name}='{value}'")
    target.write_text('\n'.join(rows) + '\n', encoding='utf-8')
    print('Created .env.docker with available ports and configured provider settings; keys not printed.')


if __name__ == '__main__':
    main()
