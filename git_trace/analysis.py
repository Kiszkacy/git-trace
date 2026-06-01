from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from git_trace.git import Commit


HUNK_HEADER_PATTERN: re.Pattern[str] = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class FileChange:
    path: str
    old_path: str | None = None
    hunks: list[DiffHunk] = field(default_factory=list)


@dataclass
class VirtualLine:
    content: str
    owner_hash: str | None


@dataclass
class DependencyGraph:
    relationships: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_dependency(self, commit_hash: str, parent_hash: str) -> None:
        self.relationships[commit_hash].add(parent_hash)

    def get_dependencies_for(self, commit_hash: str) -> set[str]:
        return self.relationships.get(commit_hash, set())


@dataclass
class CherryPickAnalysis:
    safe: list[str] = field(default_factory=list)
    conditional: list[str] = field(default_factory=list)
    blocked: dict[str, set[str]] = field(default_factory=dict)


def _parse_diff(diff_text: str, ignore_paths: set[str]) -> list[FileChange]:
    changes: list[FileChange] = []
    current_change: FileChange | None = None
    current_hunk: DiffHunk | None = None
    rename_from: str | None = None
    old_path_candidate: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current_change is not None:
                changes.append(current_change)
            current_change = None
            current_hunk = None
            rename_from = None
            old_path_candidate = None
        elif line.startswith("rename from "):
            rename_from = line[len("rename from "):].replace("\\", "/")
        elif line.startswith("rename to "):
            rename_to: str = line[len("rename to "):].replace("\\", "/")
            if rename_to not in ignore_paths:
                current_change = FileChange(path=rename_to, old_path=rename_from)
        elif line.startswith("--- "):
            current_hunk = None
            old_path_candidate = line[6:].replace("\\", "/") if line.startswith("--- a/") else None
        elif line.startswith("+++ "):
            current_hunk = None
            new_path: str | None = line[6:].replace("\\", "/") if line.startswith("+++ b/") else None
            canonical_path: str | None = new_path or old_path_candidate
            if canonical_path is None or canonical_path in ignore_paths:
                current_change = None
            elif current_change is not None and current_change.path == canonical_path:
                pass
            else:
                old: str | None = old_path_candidate if (old_path_candidate and new_path and old_path_candidate != new_path) else None
                current_change = FileChange(path=canonical_path, old_path=old)
        elif current_change is not None:
            hunk_match: re.Match[str] | None = HUNK_HEADER_PATTERN.match(line)
            if hunk_match:
                old_start: int = int(hunk_match.group(1))
                old_count: int = int(hunk_match.group(2)) if hunk_match.group(2) is not None else 1
                new_start: int = int(hunk_match.group(3))
                new_count: int = int(hunk_match.group(4)) if hunk_match.group(4) is not None else 1
                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                )
                current_change.hunks.append(current_hunk)
            elif current_hunk is not None and line and line[0] in ("+", "-", " "):
                current_hunk.lines.append((line[0], line[1:]))

    if current_change is not None:
        changes.append(current_change)
    return changes


# wild opus dependency graph building logic
def build_dependency_graph(commits: list[Commit], raw_diffs: dict[str, str], ignore_paths: set[str] | None = None) -> DependencyGraph:
    virtual_files: dict[str, list[VirtualLine]] = {}
    graph: DependencyGraph = DependencyGraph()
    ignore_paths = ignore_paths or set()

    for commit in commits:
        diff_text: str = raw_diffs.get(commit.hash, "")
        file_changes: list[FileChange] = _parse_diff(diff_text, ignore_paths)

        for change in file_changes:
            if change.old_path is not None and change.old_path in virtual_files:
                virtual_files[change.path] = virtual_files.pop(change.old_path)
            else:
                virtual_files.setdefault(change.path, [])

            virtual_file: list[VirtualLine] = virtual_files[change.path]
            cumulative_offset: int = 0

            for hunk in change.hunks:
                position: int = (
                    hunk.old_start if hunk.old_count == 0
                    else max(0, hunk.old_start - 1)
                ) + cumulative_offset

                while len(virtual_file) < position + hunk.old_count:
                    virtual_file.append(VirtualLine(content="", owner_hash=None))

                new_entries: list[VirtualLine] = []
                old_index: int = position

                for line_type, content in hunk.lines:
                    if line_type == " ":
                        new_entries.append(virtual_file[old_index])
                        old_index += 1
                    elif line_type == "-":
                        existing_line = virtual_file[old_index]
                        if existing_line.owner_hash is not None and existing_line.owner_hash != commit.hash:
                            graph.add_dependency(commit.hash, existing_line.owner_hash)
                        old_index += 1
                    elif line_type == "+":
                        new_entries.append(VirtualLine(content=content, owner_hash=commit.hash))

                virtual_file[position:position + hunk.old_count] = new_entries
                cumulative_offset += hunk.new_count - hunk.old_count

    return graph


def filter_picks(pick_hashes: set[str], graph: DependencyGraph) -> CherryPickAnalysis:
    blocked: dict[str, set[str]] = {}
    for commit_hash in pick_hashes:
        missing: set[str] = graph.get_dependencies_for(commit_hash) - pick_hashes
        if missing:
            blocked[commit_hash] = missing

    tainted: set[str] = set(blocked.keys())
    changed: bool = True
    while changed:
        changed = False
        for commit_hash in pick_hashes:
            if commit_hash not in tainted:
                in_pick_dependencies: set[str] = graph.get_dependencies_for(commit_hash) & pick_hashes
                if in_pick_dependencies & tainted:
                    tainted.add(commit_hash)
                    changed = True

    conditional: list[str] = [commit_hash for commit_hash in pick_hashes if commit_hash in tainted and commit_hash not in blocked]
    safe: list[str] = [commit_hash for commit_hash in pick_hashes if commit_hash not in tainted]
    return CherryPickAnalysis(
        safe=safe,
        conditional=conditional,
        blocked=blocked
    )
