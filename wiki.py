"""Read-only Confluence connection smoke test.

Configuration is loaded from .env:
  CONFLUENCE_BASE_URL
  CONFLUENCE_USERNAME
  CONFLUENCE_PASSWORD
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()


def main() -> None:
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
    username = os.getenv("CONFLUENCE_USERNAME", "")
    password = os.getenv("CONFLUENCE_PASSWORD", "")

    missing = [
        name
        for name, value in {
            "CONFLUENCE_BASE_URL": base_url,
            "CONFLUENCE_USERNAME": username,
            "CONFLUENCE_PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    session = requests.Session()
    session.trust_env = False

    response = session.get(
        f"{base_url}/rest/api/content",
        auth=HTTPBasicAuth(username, password),
        params={"limit": 5, "expand": "space,version"},
        timeout=20,
    )

    if response.status_code != 200:
        print(f"Login failed, status code: {response.status_code}")
        print(response.text[:1000])
        return

    data = response.json()
    print("Login succeeded.")
    print(
        {
            "baseUrl": base_url,
            "username": username,
            "size": data.get("size"),
            "limit": data.get("limit"),
            "samplePages": [
                {
                    "pageId": item.get("id"),
                    "title": item.get("title"),
                    "spaceKey": (item.get("space") or {}).get("key"),
                }
                for item in data.get("results", [])
            ],
        }
    )


if __name__ == "__main__":
    main()
