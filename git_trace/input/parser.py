from __future__ import annotations

import argparse

from git_trace import __version__
from git_trace.utils import Color


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-trace",
        description="Visualise and analyse git commit dependencies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f" A {Color.BOLD.value}{Color.BRIGHT_BLUE.value}config.yml{Color.RESET.value} file if present in the current directory is loaded automatically and"
            " can set any of these options. CLI arguments take priority over config.yml,"
            " which takes priority over .txt auto-load files.\n\n"
            "examples:\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace                                     {Color.RESET.value}# analyse main, full history\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--after {Color.YELLOW.value}abc1234                 {Color.RESET.value}# analyse dev after a commit\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--after {Color.YELLOW.value}abc {Color.CYAN.value}--before {Color.YELLOW.value}def        {Color.RESET.value}# analyse a commit range\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--whitelist {Color.YELLOW.value}picks.txt           {Color.RESET.value}# whitelist via file\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--whitelist {Color.YELLOW.value}h1 h2 h3            {Color.RESET.value}# whitelist inline\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--no-graph                      {Color.RESET.value}# text-only output\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--after {Color.YELLOW.value}abc {Color.CYAN.value}--picks {Color.YELLOW.value}h1 h2       {Color.RESET.value}# check if cherry picking is safe\n"
            f"  {Color.BOLD.value}{Color.MAGENTA.value}git-trace {Color.GREEN.value}dev {Color.CYAN.value}--picks {Color.YELLOW.value}picks.txt               {Color.RESET.value}# cherry pick safety check via file\n"
        ).strip(),
    )
    # positional args
    parser.add_argument(
        "branch",
        nargs="?",
        default=argparse.SUPPRESS,
        help=f"branch to analyse {Color.BRIGHT_BLACK.value}(default: main){Color.RESET.value}.",
    )
    # optional args
    parser.add_argument(
        "--after",
        metavar="HASH",
        default=argparse.SUPPRESS,
        help=f"only include commits after this hash {Color.BRIGHT_BLACK.value}(excluding it){Color.RESET.value}.",
    )
    parser.add_argument(
        "--before",
        metavar="HASH",
        default=argparse.SUPPRESS,
        help=f"only include commits up to this hash {Color.BRIGHT_BLACK.value}(excluding it){Color.RESET.value}.",
    )
    parser.add_argument(
        "--blacklist",
        nargs="+",
        metavar="HASH_OR_FILE",
        default=argparse.SUPPRESS,
        help=(
            f"commit hashes to ignore during analysis, OR a single path to a file containing them {Color.BRIGHT_BLACK.value}(one per line){Color.RESET.value}. "
            "Auto-loaded from blacklist.txt if the file exists and the flag is omitted."
        ),
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        default=argparse.SUPPRESS,
        help=f"path to a YAML config file {Color.BRIGHT_BLACK.value}(default: config.yml){Color.RESET.value}. Values are overridden by explicit CLI args.",
    )
    parser.add_argument(
        "--ignore-paths",
        nargs="+",
        metavar="PATH_OR_FILE",
        default=argparse.SUPPRESS,
        help=(
            "repo-relative paths to exclude from diff analysis, OR a single path to a "
            f"file containing them {Color.BRIGHT_BLACK.value}(one per line){Color.RESET.value}. "
            "Auto-loaded from ignore-paths.txt if the file exists and the flag is omitted."
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=argparse.SUPPRESS,
        help=(
            f"works only if used alongside --picks. Prints a simple list of blocked commit hashes {Color.BRIGHT_BLACK.value}(one per line, outputs nothing if no dependencies are found){Color.RESET.value} instead of the formatted text tree. "
            "Combine with --no-graph to suppress HTML output as well."
        ),
    )
    parser.add_argument(
        "--no-graph",
        action="store_true",
        default=argparse.SUPPRESS,
        help="skip HTML graph generation and print only the text output.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help=f"output path for the HTML graph {Color.BRIGHT_BLACK.value}(default: output.html){Color.RESET.value}.",
    )
    parser.add_argument(
        "--picks",
        nargs="+",
        metavar="HASH_OR_FILE",
        default=argparse.SUPPRESS,
        help=(
            "commit hashes to cherry-pick, OR a single path to a file containing them. "
            "When provided, analysis additionally reports which commits are safe to "
            "pick and which are blocked by missing dependencies. "
            "Auto-loaded from picks.txt if the file exists and the flag is omitted."
        ),
    )
    parser.add_argument(
        "--repo",
        metavar="DIR",
        default=argparse.SUPPRESS,
        help=f"path to the git repository root {Color.BRIGHT_BLACK.value}(default: current directory){Color.RESET.value}.",
    )
    parser.add_argument(
        "--txt-output",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="write the text output to this file.",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"git-trace {__version__}",
    )
    parser.add_argument(
        "--whitelist",
        nargs="+",
        metavar="HASH_OR_FILE",
        default=argparse.SUPPRESS,
        help=(
            "only analyse these commit hashes, OR a single path to a file "
            f"containing them {Color.BRIGHT_BLACK.value}(one per line){Color.RESET.value}. Runs before --blacklist logic. "
            "Auto-loaded from whitelist.txt if the file exists and the flag is omitted."
        ),
    )

    return parser
