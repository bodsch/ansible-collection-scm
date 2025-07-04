#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import requests
from typing import List

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class GitHubCleaner:
    """
    """

    def __init__(self, token: str, repo: str, user: str, keep: int):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"token {token}"})
        self.base = "https://api.github.com"
        self.owner, self.repo = user, repo
        self.keep = keep

    def list_workflows(self) -> List[dict]:
        url = f"{self.base}/repos/{self.owner}/{self.repo}/actions/workflows"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json().get("workflows", [])

    def list_all_runs(self, wf_id: int) -> List[dict]:
        runs = []
        url = f"{self.base}/repos/{self.owner}/{self.repo}/actions/workflows/{wf_id}/runs"
        params = {"per_page": 100}
        while url:
            r = self.session.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            runs.extend(data.get("workflow_runs", []))
            url = r.links.get("next", {}).get("url")
        return sorted(runs, key=lambda x: x["created_at"], reverse=True)

    def cleanup(self):
        logger.info("Cleaning up workflows for %s/%s (keep=%d)",
                    self.owner, self.repo, self.keep)
        for wf in self.list_workflows():
            wf_id, name = wf["id"], wf["name"]
            runs = self.list_all_runs(wf_id)
            to_delete = [run["id"] for run in runs[self.keep:]]
            if to_delete:
                logger.info(" → Deleting %d runs of '%s'",
                            len(to_delete), name)
                for rid in to_delete:
                    url = f"{self.base}/repos/{self.owner}/{self.repo}/actions/runs/{rid}"
                    dr = self.session.delete(url)
                    dr.raise_for_status()


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup old GitHub Actions runs")
    parser.add_argument("--token",
                        default=os.getenv("GH_TOKEN"),
                        help="GitHub access token (oder GH_TOKEN)")
    parser.add_argument("--repo",
                        default=os.getenv("GH_REPOSITORY"),
                        help="Repository-Name, z.B. 'org/repo' (oder GH_REPOSITORY)")
    parser.add_argument("--user",
                        default=os.getenv("GH_USERNAME"),
                        help="GitHub-Benutzer (oder GH_USERNAME)")
    parser.add_argument("--keep", type=int,
                        default=int(os.getenv("GH_KEEP_WORKFLOWS", "2")),
                        help="Anzahl der Runs, die erhalten bleiben (oder GH_KEEP_WORKFLOWS)")

    args = parser.parse_args()

    # Validierung aller nötigen Werte
    missing = []
    for name, val in [("token", args.token), ("repo", args.repo), ("user", args.user)]:
        if not val:
            missing.append(name.upper())
    if missing:
        logger.error(
            "fehlende Parameter: %s (als Flag oder Env-Variable setzen)", ", ".join(missing))
        sys.exit(1)

    cleaner = GitHubCleaner(
        token=args.token,
        repo=args.repo,
        user=args.user,
        keep=args.keep
    )
    cleaner.cleanup()


if __name__ == "__main__":
    main()
