from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Commit:
    hash: str
    message: str

    def is_inside_hash_set(self, hash_set: set[str]) -> bool:
        return any(self.hash.startswith(prefix) or prefix.startswith(self.hash) for prefix in hash_set)


def run_git(*args: str, repo_directory: str) -> str:
    command: list[str] = ["git"]
    if repo_directory:
        command += ["-C", repo_directory]
    command += list(args)
    process: subprocess.CompletedProcess[str] = subprocess.run(
        command, capture_output=True, encoding="utf-8", errors="replace"
    )
    return process.stdout or ""


def get_commits(branch: str, repo_directory: str, after: str | None = None, before: str | None = None) -> list[Commit]:
    scope: str = f"{after if after else ''}{'..' if after else ''}{before if before else branch}"
    output: str = run_git("log", scope, "--reverse", "--format=%H %s", repo_directory=repo_directory)

    commits: list[Commit] = []
    for line in output.splitlines():
        line = line.strip()
        if line:
            commit_hash, _, message = line.partition(" ")
            commits.append(Commit(hash=commit_hash, message=message))

    if before and commits: # skip last commit to exclude it
        commits.pop()

    return commits


def get_commit_diff(sha: str, repo_directory: str) -> str:
    return run_git("show", "--format=", "-p", sha, repo_directory=repo_directory)


def resolve_hashes(hashes: list[str], all_commits: list[Commit]) -> dict[str, str | None]:
    full_hashes: list[str] = [commit.hash for commit in all_commits]
    result: dict[str, str | None] = {}
    for hash_ in hashes: # if user provided short hashes map them to full hashes if possible
        matches: list[str] = [full_hash for full_hash in full_hashes if full_hash.lower().startswith(hash_.lower())]
        result[hash_] = matches[0] if len(matches) == 1 else None
    return result
