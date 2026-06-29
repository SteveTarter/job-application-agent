#!/usr/bin/env python

import json
import sys
import urllib.error
import urllib.request


def fetch_repos(username):
    username = username.strip()
    if "/" in username:
        username = username.rstrip("/").split("/")[-1]
    url = f"https://api.github.com/users/{username}/repos"
    req = urllib.request.Request(url, headers={"User-Agent": "ADK-Agent-Skill"})

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            repos = []
            for item in data:  # Retrieve all available repos
                repos.append(
                    {
                        "name": item.get("name"),
                        "description": item.get("description") or "",
                        "language": item.get("language") or "Python",
                    }
                )
            return repos
    except Exception as e:
        raise RuntimeError(f"Failed to fetch repositories from GitHub for user '{username}': {e}")


if __name__ == "__main__":
    username = "SteveTarter"
    if len(sys.argv) > 1:
        username = sys.argv[1]

    repos = fetch_repos(username)
    print(json.dumps(repos, indent=2))
