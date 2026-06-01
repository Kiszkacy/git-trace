from __future__ import annotations

import os
import sys
from typing import Any

import colorama

from git_trace.analysis import build_dependency_graph, filter_picks, CherryPickAnalysis, DependencyGraph
from git_trace.git import get_commit_diff, get_commits, Commit, resolve_hashes
from git_trace.input.args import build_args_dict
from git_trace.output.graph import display_pick_graph, display_graph
from git_trace.output.text import print_pick_result, print_pick_list, print_text_tree
from git_trace.utils import cprint, Color, SHORT_HASH_LENGTH, ERROR_COLOR, WARNING_COLOR, MAX_COMMIT_MESSAGE_LENGTH


def main():
    colorama.init()
    args: dict[str, Any] = build_args_dict()

    git_directory_path: str = os.path.join(args["repo"], ".git")
    if not os.path.isdir(git_directory_path):
        cprint(
            f"[ERROR] .git directory not found in '{os.path.abspath(args['repo'])}'. "
            "Run git-trace from the root of your git repository, "
            "or use --repo to specify the path.",
            color=ERROR_COLOR,
        )
        sys.exit(1)

    commits: list[Commit] = _fetch_commits(args["branch"], args["repo"], args["after"], args["before"], args["list"])
    if not commits:
        cprint("[ERROR] No commits found. Check that the branch name and hash bounds are correct, exiting...", color=ERROR_COLOR)
        sys.exit(2)

    if args["whitelist"] and args["blacklist"]:
        cprint("[WARNING] Both --whitelist and --blacklist provided, --whitelist takes priority and runs before --blacklist logic.", color=WARNING_COLOR)

    commit_count_before_filtering: int = len(commits)
    if args["whitelist"]:
        commits = [commit for commit in commits if commit.is_inside_hash_set(args["whitelist"])]
        cprint(f"Selected {len(commits)} out of {commit_count_before_filtering} commit(s) due to whitelist.")
    commit_count_after_whitelisting: int = len(commits)
    if args["blacklist"]:
        commits = [commit for commit in commits if not commit.is_inside_hash_set(args["blacklist"])]
        cprint(f"Skipped {commit_count_after_whitelisting - len(commits)} blacklisted commit(s).")

    if not commits:
        cprint("[ERROR] No commits left after applying filters, exiting...", color=ERROR_COLOR)
        sys.exit(3)

    if not args["list"]:
        cprint(f"Selected {len(commits)} commit(s). Analysing diffs...")

    raw_diffs: dict[str, str] = _fetch_diffs(commits, args["repo"], args["list"])
    commits_hash_dict: dict[str, Commit] = {commit.hash: commit for commit in commits}

    if not args["list"]:
        cprint("Building dependency graph...")
    dependency_graph: DependencyGraph = build_dependency_graph(commits, raw_diffs, args["ignore-paths"])
    dependency_count: int = sum(1 for dep_set in dependency_graph.relationships.values() if dep_set)
    if not args["list"]:
        cprint(f"  {dependency_count} commit(s) have at least one dependency.\n")

    if args["picks"]:
        resolved: dict[str, str | None] = resolve_hashes(list(args["picks"]), commits)
        unknown_hashes: list[str] = [short_hash for short_hash, full_hash in resolved.items() if full_hash is None]
        if unknown_hashes:
            cprint("[WARNING] The following hashes were not found in the analyzed range and will be skipped:", color=WARNING_COLOR)
            for short_hash in unknown_hashes:
                cprint(f"{' '*4}{short_hash}")

        full_pick_hashes: set[str] = {full_hash for full_hash in resolved.values() if full_hash is not None}
        cherry_pick_analysis: CherryPickAnalysis = filter_picks(full_pick_hashes, dependency_graph)

        if args["list"]:
            print_pick_list(cherry_pick_analysis.blocked, commits_hash_dict)
        else:
            print_pick_result(cherry_pick_analysis, commits_hash_dict, txt_output_path=args["txt-output"])

        if not args["no-graph"]:
            display_pick_graph(commits, commits_hash_dict, dependency_graph, cherry_pick_analysis, output_path=args["output"])
    else:
        print_text_tree(commits, commits_hash_dict, dependency_graph, txt_output_path=args["txt-output"])

        if not args["no-graph"]:
            display_graph(commits, commits_hash_dict, dependency_graph, output_path=args["output"])


def _fetch_commits(branch: str, repo_directory: str, after: str | None, before: str | None, using_list_arg: bool = False) -> list[Commit]:
    message_parts: list[str] = [f"Fetching commits on '{Color.BRIGHT_BLUE.value}{branch}{Color.RESET.value}'"]
    if after:
        message_parts.append(f"after {Color.BRIGHT_BLUE.value}{after[:SHORT_HASH_LENGTH]}{Color.RESET.value}")
    if before:
        message_parts.append(f"up to {before[:SHORT_HASH_LENGTH]}")
    if not using_list_arg:
        cprint(" ".join(message_parts) + "...")

    return get_commits(branch=branch, after=after, before=before, repo_directory=repo_directory)


def _fetch_diffs(commits: list[Commit], repo_directory: str, using_list_arg: bool = False) -> dict[str, str]:
    raw_diffs: dict[str, str] = {}
    commit_count: int = len(commits)
    message_index_padding_width: int = len(str(commit_count))
    for index, commit in enumerate(commits, 1):
        if not using_list_arg:
            message_index_prefix: str = f"[{index:>{message_index_padding_width}}/{commit_count}]"
            cprint(f"  {message_index_prefix}  {commit.hash[:SHORT_HASH_LENGTH]}  {commit.message[:MAX_COMMIT_MESSAGE_LENGTH]}")
        raw_diffs[commit.hash] = get_commit_diff(commit.hash, repo_directory=repo_directory)
    return raw_diffs


if __name__ == "__main__":
    main()
