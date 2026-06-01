from __future__ import annotations

import os
import webbrowser

from pyvis.network import Network

from git_trace.analysis import DependencyGraph, CherryPickAnalysis
from git_trace.git import Commit
from git_trace.output.html_injection import inject_analysis_controls, inject_analysis_legend, inject_pick_controls, inject_pick_legend, inject_styling
from git_trace.utils import SHORT_HASH_LENGTH, MAX_COMMIT_MESSAGE_LENGTH, INFO_COLOR, cprint

# TODO: make this configurable ?
NODE_LABEL_MAX_LENGTH: int = 36
NODE_HIGHLIGHT_STYLES: dict[str, str] = {"background": "#2a6496", "border": "#87ceeb"}
ANALYSIS_NODE_COLORS: dict[str, dict[str, str]] = {
    "independent": {"bg": "#4caf50", "border": "#2e7d32"},
    "has_deps":    {"bg": "#546e7a", "border": "#37474f"},
}
PICK_NODE_COLORS: dict[str, dict[str, str]] = {
    "safe":        {"bg": "#4caf50", "border": "#2e7d32"},
    "conditional": {"bg": "#1b7a4a", "border": "#0d4a2d"},
    "blocked":     {"bg": "#f44336", "border": "#b71c1c"},
    "missing":     {"bg": "#ff9800", "border": "#e65100"},
    "context":     {"bg": "#546e7a", "border": "#37474f"},
}


def build_node_color(palette_colors: dict[str, str]) -> dict:
    return {
        "background": palette_colors["bg"],
        "border":     palette_colors["border"],
        "highlight":  NODE_HIGHLIGHT_STYLES,
        "hover":      NODE_HIGHLIGHT_STYLES,
    }


# TODO: make this configurable ?
NETWORK_OPTIONS: str = """
{
  "physics": {
    "enabled": true,
    "solver": "repulsion",
    "minVelocity": 0.4,
    "repulsion": {
      "nodeDistance": 180,
      "springLength": 200,
      "springConstant": 0.04,
      "damping": 0.12
    },
    "stabilization": { "enabled": true, "iterations": 1000 }
  },
  "edges": {
    "arrows": { "to": { "enabled": true, "scaleFactor": 1.0 } },
    "color": { "color": "#aaaaaa", "highlight": "#ffffff" },
    "smooth": { "type": "dynamic" }
  },
  "interaction": {
    "hover": true,
    "tooltipDelay": 100,
    "navigationButtons": true,
    "keyboard": true
  }
}
"""


def _make_network() -> Network:
    network: Network = Network(
        height="98vh",
        width="100%",
        bgcolor="#1e1e2e",
        font_color="#eeeeee",
        directed=True,
        notebook=False,
    )
    network.set_options(NETWORK_OPTIONS)
    return network


def display_graph(commits: list[Commit], commits_hash_dict: dict[str, Commit], graph: DependencyGraph, output_path: str = "output.html"):
    network: Network = _make_network()

    for commit in commits:
        commit_hash: str = commit.hash
        has_deps: bool = bool(graph.relationships.get(commit_hash))
        palette: dict[str, str] = ANALYSIS_NODE_COLORS["has_deps" if has_deps else "independent"]
        dependency_lines: list[str] = [
            f"  • [{dependency_hash[:SHORT_HASH_LENGTH]}] {commits_hash_dict[dependency_hash].message[:MAX_COMMIT_MESSAGE_LENGTH]}"
            for dependency_hash in sorted(graph.get_dependencies_for(commit_hash))
        ]
        tooltip: str = "\n".join(
            [f"[{commit_hash[:SHORT_HASH_LENGTH]}]  {commit.message}"]
            + (["\nDepends on:"] + dependency_lines if dependency_lines else [])
        )
        network.add_node(
            commit_hash,
            label=f"{truncate_label(commit.message)}\n{commit_hash[:SHORT_HASH_LENGTH]}",
            title=tooltip,
            color=build_node_color(palette),
            font={"size": 11, "color": "#ffffff"},
            shape="box",
            margin=10,
        )

    for hash_b, dependency_set in graph.relationships.items():
        for hash_a in dependency_set:
            network.add_edge(
                hash_a, hash_b,
                title=f"[{hash_b[:SHORT_HASH_LENGTH]}] depends on [{hash_a[:SHORT_HASH_LENGTH]}]",
                color="#dddddd",
                width=1.5,
            )

    out_path: str = os.path.abspath(output_path)
    network.save_graph(out_path)
    inject_analysis_controls(out_path)
    inject_analysis_legend(out_path)
    inject_styling(out_path)
    cprint(f"[INFO] Interactive graph saved to:\n{' '*4}{out_path}\n", color=INFO_COLOR)
    webbrowser.open(f"file:///{out_path}") # TODO: make this configurable
    cprint("[INFO] Opened in your default browser.  Drag nodes freely!\n", color=INFO_COLOR)


def display_pick_graph(commits: list[Commit], commits_hash_dict: dict[str, Commit], graph: DependencyGraph, analysis: CherryPickAnalysis, output_path: str = "git_trace_pick_output.html"):
    network: Network = _make_network()

    safe_set: set[str] = set(analysis.safe)
    blocked_set: set[str] = set(analysis.blocked.keys())
    conditional_set: set[str] = set(analysis.conditional)
    missing_set: set[str] = {dependency_hash for dependency_hashes in analysis.blocked.values() for dependency_hash in dependency_hashes}

    for commit in commits:
        commit_hash: str = commit.hash
        role: str
        status_line: str

        if commit_hash in safe_set:
            role = "safe"
            status_line = "[✔] Safe to cherry-pick"
        elif commit_hash in conditional_set:
            role = "conditional"
            status_line = "[◑] Safe to pick, but only after blocked parent dependencies are resolved"
        elif commit_hash in blocked_set:
            role = "blocked"
            missing_msgs: list[str] = [
                f"  • [{dependency_hash[:SHORT_HASH_LENGTH]}] {commits_hash_dict.get(dependency_hash, Commit("<unknown>", "<unknown>")).message[:MAX_COMMIT_MESSAGE_LENGTH]}"
                for dependency_hash in sorted(analysis.blocked[commit_hash])
            ]
            status_line = "[✘] Blocked - missing dependencies:\n" + "\n".join(missing_msgs)
        elif commit_hash in missing_set:
            role = "missing"
            status_line = "[⚠] Not picked - required by blocked commit(s)"
        else:
            role = "context"
            status_line = "[-] Context commit (not in pick list)"

        dependency_lines: list[str] = [
            f"  • [{dependency_hash[:SHORT_HASH_LENGTH]}] {commits_hash_dict[dependency_hash].message[:MAX_COMMIT_MESSAGE_LENGTH] if dependency_hash in commits_hash_dict else ''}"
            for dependency_hash in sorted(graph.get_dependencies_for(commit_hash))
        ]
        tooltip: str = "\n".join(
            [f"[{commit_hash[:SHORT_HASH_LENGTH]}]  {commit.message}", "", status_line]
            + (["", "Depends on:"] + dependency_lines if dependency_lines else [])
        )
        network.add_node(
            commit_hash,
            label=f"{truncate_label(commit.message)}\n{commit_hash[:SHORT_HASH_LENGTH]}",
            title=tooltip,
            color=build_node_color(PICK_NODE_COLORS[role]),
            font={"size": 11, "color": "#ffffff"},
            shape="box",
            margin=10,
        )

    for hash_b, dependency_set in graph.relationships.items():
        for hash_a in dependency_set:
            is_blocking: bool = hash_b in blocked_set and hash_a in analysis.blocked.get(hash_b, set())
            network.add_edge(
                hash_a, hash_b,
                title=f"[{hash_b[:SHORT_HASH_LENGTH]}] depends on [{hash_a[:SHORT_HASH_LENGTH]}]",
                color="#ff4444" if is_blocking else "#666666",
                width=2.5 if is_blocking else 1.0,
                dashes=not is_blocking,
            )

    out_path: str = os.path.abspath(output_path)
    network.save_graph(out_path)
    inject_pick_controls(out_path)
    inject_pick_legend(out_path)
    inject_styling(out_path)
    cprint(f"[INFO] Pick graph saved to:\n{' '*4}{out_path}\n", color=INFO_COLOR)
    webbrowser.open(f"file:///{out_path}") # TODO: make this configurable
    cprint("[INFO] Opened in your default browser.\n", color=INFO_COLOR)


def truncate_label(msg: str) -> str:
    return (msg[:NODE_LABEL_MAX_LENGTH] + "…") if len(msg) > NODE_LABEL_MAX_LENGTH else msg
