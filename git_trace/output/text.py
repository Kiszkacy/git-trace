from __future__ import annotations

from git_trace.analysis import DependencyGraph, CherryPickAnalysis
from git_trace.git import Commit
from git_trace.utils import SHORT_HASH_LENGTH, cprint, INFO_COLOR, Color, MAX_COMMIT_MESSAGE_LENGTH


def print_text_tree(commits: list[Commit], commits_hash_dict: dict[str, Commit], graph: DependencyGraph, txt_output_path: str | None = None):
    title: str = "Commit dependency tree  (○ = independent  ● = has dependencies)"
    lines: list[str] = [title]
    cprint(title, color=Color.CYAN)
    for commit in commits:
        line: str = f"  [{'●' if graph.relationships.get(commit.hash) else '○'}] [{commit.hash[:SHORT_HASH_LENGTH]}]  {commits_hash_dict[commit.hash].message[:MAX_COMMIT_MESSAGE_LENGTH]}"
        lines.append(line)
        cprint(line)

        for dependency_hash in sorted(graph.get_dependencies_for(commit.hash)):
            line = f"{' '*8}└─ depends on  [{dependency_hash[:SHORT_HASH_LENGTH]}]  {commits_hash_dict[dependency_hash].message[:MAX_COMMIT_MESSAGE_LENGTH]}"
            lines.append(line)
            cprint(line)

    if txt_output_path:
        with open(txt_output_path, "w", encoding="utf-8") as file_handle:
            file_handle.write("\n".join(lines) + "\n")
        cprint(f"[INFO] Text tree saved to:\n{' '*4}{txt_output_path}\n", color=INFO_COLOR)


def print_pick_result(analysis: CherryPickAnalysis, commits_hash_dict: dict[str, Commit], txt_output_path: str | None = None):
    title: str = "Cherry-pick dependency results"
    lines: list[str] = [title]
    cprint(title, color=Color.CYAN)

    subtitle: str = f"\n  [✔]  {len(analysis.safe)} commit(s) safe to pick:"
    lines.append(subtitle)
    cprint(subtitle)
    for commit_hash in analysis.safe:
        message: str = commits_hash_dict[commit_hash].message[:MAX_COMMIT_MESSAGE_LENGTH] if commit_hash in commits_hash_dict else "<unknown>"
        line: str = f"{' '*4}[{commit_hash[:SHORT_HASH_LENGTH]}]  {message}"
        lines.append(line)
        cprint(line)

    subtitle: str = f"\n  [◑]  {len(analysis.conditional)} commit(s) safe to pick - only after blocked parent deps are resolved:"
    lines.append(subtitle)
    cprint(subtitle)
    for commit_hash in analysis.conditional:
        message = commits_hash_dict[commit_hash].message[:MAX_COMMIT_MESSAGE_LENGTH] if commit_hash in commits_hash_dict else "<unknown>"
        line = f"{' ' * 4}[{commit_hash[:SHORT_HASH_LENGTH]}]  {message}"
        lines.append(line)
        cprint(line)

    subtitle: str = f"\n  [✘]  {len(analysis.blocked)} commit(s) blocked (depend on commits not in the pick list):"
    lines.append(subtitle)
    cprint(subtitle)
    for commit_hash, missing in sorted(analysis.blocked.items()):
        message = commits_hash_dict[commit_hash].message[:MAX_COMMIT_MESSAGE_LENGTH] if commit_hash in commits_hash_dict else "<unknown>"
        line = f"{' ' * 4}[{commit_hash[:SHORT_HASH_LENGTH]}]  {message}"
        lines.append(line)
        cprint(line)

        for dependency_hash in sorted(missing):
            dependency_message: str = commits_hash_dict[dependency_hash].message[:MAX_COMMIT_MESSAGE_LENGTH] if dependency_hash in commits_hash_dict else "<not in range>"
            line = f"{' '*8}└─ missing  [{dependency_hash[:SHORT_HASH_LENGTH]}]  {dependency_message}"
            lines.append(line)
            cprint(line)

    if txt_output_path:
        with open(txt_output_path, "w", encoding="utf-8") as file_handle:
            file_handle.write("\n".join(lines) + "\n")
        cprint(f"[INFO] Pick result saved to:\n{' '*4}{txt_output_path}\n", color=INFO_COLOR)


# TODO: blocked or blocked + conditional ? & with or without messages ?
def print_pick_list(blocked: dict[str, set[str]], commits_hash_dict: dict[str, Commit]):
    missing_hashes: set[str] = {dependency_hash for dependency_hashes in blocked.values() for dependency_hash in dependency_hashes}
    for dependency_hash in sorted(missing_hashes):
        message: str = commits_hash_dict[dependency_hash].message if dependency_hash in commits_hash_dict else "<unknown>"
        cprint(f"{dependency_hash[:SHORT_HASH_LENGTH]} {message}")
