"""Create the ignored root .env from the two local credential files.

This helper never prints credential values. Re-run it after either source file changes.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_secret(filename: str) -> str:
    path = ROOT / filename
    if not path.exists():
        raise SystemExit(f"Missing credential file: {filename}")
    value = path.read_text(encoding="utf-8-sig").strip()
    if not value:
        raise SystemExit(f"Credential file is empty: {filename}")
    if "\n" in value or "\r" in value:
        raise SystemExit(f"Credential file must contain one value: {filename}")
    return value


def quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def main() -> None:
    kimi_key = read_secret("Kimi k3 API Key.txt")
    mysql_password = read_secret("MySQL Root User Password.txt")
    env_text = "\n".join(
        [
            "APP_NAME=AI Detective Game",
            "APP_ENV=development",
            "API_PREFIX=/api",
            "FRONTEND_ORIGIN=http://localhost:5173",
            "",
            "MYSQL_HOST=127.0.0.1",
            "MYSQL_PORT=3306",
            "MYSQL_USER=root",
            f"MYSQL_PASSWORD={quoted(mysql_password)}",
            "MYSQL_DATABASE=ai_detective",
            "",
            "KIMI_ENABLED=true",
            f"KIMI_API_KEY={quoted(kimi_key)}",
            "KIMI_BASE_URL=https://api.moonshot.cn/v1",
            "KIMI_MODEL=kimi-k3",
            "KIMI_REASONING_EFFORT=low",
            "KIMI_TIMEOUT_SECONDS=180",
            "",
            "QUESTION_LIMIT=18",
            "",
        ]
    )
    (ROOT / ".env").write_text(env_text, encoding="utf-8")
    print("Created .env from local credential files (values hidden).")


if __name__ == "__main__":
    main()
