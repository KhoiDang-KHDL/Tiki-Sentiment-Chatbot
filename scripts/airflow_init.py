"""Seed local development auth without printing passwords or replacing existing ones."""
import json
import os
from pathlib import Path


def main():
    path = Path(os.environ["AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        password = os.environ["TIKI_ADMIN_PASSWORD"]
        if len(password) < 16 or password == "GENERATE_WITH_SETUP":
            raise ValueError("Run scripts/airflow.ps1 setup to generate credentials")
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"admin": password}, stream)
        path.chmod(0o600)
    print("Airflow database and local admin auth initialized.")


if __name__ == "__main__":
    main()
