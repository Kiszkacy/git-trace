from __future__ import annotations

import argparse
import copy
import os
from dataclasses import dataclass
from typing import Any, Callable

import yaml

from git_trace.input.parser import build_cli_parser
from git_trace.utils import cprint, WARNING_COLOR, yaml2list, INFO_COLOR, read_cleaned_file


@dataclass(frozen=True)
class ArgumentDefinition:
    identifier: str
    yaml_identifier: str | None = None
    conversion_from_yaml: Callable | None = None
    default_value: Any | None = None


CLI_ARGUMENTS_LIST: tuple[ArgumentDefinition, ...] = (
    #                  Identifier      YAML Key        Converter       Default Value
    ArgumentDefinition("after",        "after",        bool),
    ArgumentDefinition("before",       "before",       str),
    ArgumentDefinition("blacklist",    "blacklist", yaml2list, "blacklist.txt"),
    ArgumentDefinition("branch",       "branch",       str,            "main"),
    ArgumentDefinition("config",                                       default_value="config.yml"),
    ArgumentDefinition("ignore_paths", "ignore-paths", yaml2list, "ignore_paths.txt"),
    ArgumentDefinition("list",                                         default_value=False),
    ArgumentDefinition("no_graph",     "no-graph",     bool,           False),
    ArgumentDefinition("output",       "output",       str,            "./output.html"),
    ArgumentDefinition("picks",        "picks", yaml2list, "picks.txt"),
    ArgumentDefinition("repo",         "repo",         str,            "./"),
    ArgumentDefinition("txt_output",   "txt-output",   str),
    ArgumentDefinition("whitelist",    "whitelist", yaml2list, "whitelist.txt"),
)
CLI_ARGUMENTS: dict[str, ArgumentDefinition] = {arg.identifier: arg for arg in CLI_ARGUMENTS_LIST}


def build_args_dict() -> dict[str, Any]:
    parser: argparse.ArgumentParser = build_cli_parser()
    args: argparse.Namespace = parser.parse_args()

    provided_via_cli: set[str] = {
        arg.identifier
        for arg in CLI_ARGUMENTS_LIST
        if hasattr(args, arg.identifier)
    }

    config_path: str = getattr(args, "config", None) or "./config.yml"
    config: dict[str, Any] | None = _load_config(config_path)
    if config:
        args = _fill_out_args_with_config_values(args, config, provided_via_cli)

    args.blacklist = _check_if_autoloading_list_input(getattr(args, "blacklist", None), "./blacklist.txt", "blacklist")
    args.ignore_paths = _check_if_autoloading_list_input(getattr(args, "ignore_paths", None), "./ignore_paths.txt", "ignore_paths")
    args.picks = _check_if_autoloading_list_input(getattr(args, "picks", None), "./picks.txt", "picks")
    args.whitelist = _check_if_autoloading_list_input(getattr(args, "whitelist", None), "./whitelist.txt", "whitelist")

    blacklist: set[str] | None = _resolve_hash_list_input(args.blacklist, "blacklist") if args.blacklist else None
    ignore_paths: set[str] = _resolve_file_paths_input(args.ignore_paths, "ignore_paths") if args.ignore_paths else None
    picks: set[str] | None = _resolve_hash_list_input(args.picks, "picks") if args.picks else None
    whitelist: set[str] | None = _resolve_hash_list_input(args.whitelist, "whitelist") if args.whitelist else None

    result: dict[str, Any] = {
        "after":        getattr(args, "after", None)        or CLI_ARGUMENTS["after"].default_value,
        "before":       getattr(args, "before", None)       or CLI_ARGUMENTS["before"].default_value,
        "blacklist":    blacklist,
        "branch":       getattr(args, "branch", None)       or CLI_ARGUMENTS["branch"].default_value,
        "config":       getattr(args, "config", None)       or CLI_ARGUMENTS["config"].default_value,
        "ignore-paths": ignore_paths,
        "list":         getattr(args, "list", None)         or CLI_ARGUMENTS["list"].default_value,
        "no-graph":     getattr(args, "no_graph", None)     or CLI_ARGUMENTS["no_graph"].default_value,
        "output":       getattr(args, "output", None)       or CLI_ARGUMENTS["output"].default_value,
        "picks":        picks,
        "repo":         getattr(args, "repo", None)         or CLI_ARGUMENTS["repo"].default_value,
        "txt-output":   getattr(args, "txt_output", None)   or CLI_ARGUMENTS["txt_output"].default_value,
        "whitelist":    whitelist,
    }
    return result


def _load_config(path: str) -> dict[str, Any] | None:
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as file:
        data: dict[str, Any] | None = yaml.safe_load(file) or None

    if data is None or not isinstance(data, dict):
        cprint(f"[WARNING] Could not load config from '{path}', check if it's a correct YAML mapping, ignoring.", color=WARNING_COLOR)
        return None

    cprint(f"[INFO] Loaded config from '{path}'.", color=INFO_COLOR)
    return data


def _fill_out_args_with_config_values(args: argparse.Namespace, config: dict[str, Any], provided_via_cli: set[str]) -> argparse.Namespace:
    new_args: argparse.Namespace = copy.deepcopy(args)

    for argument in CLI_ARGUMENTS_LIST:
        if argument.identifier in provided_via_cli or argument.yaml_identifier is None:
            continue
        raw_value: Any = config.get(argument.yaml_identifier)
        if raw_value is None:
            continue

        if argument.conversion_from_yaml is None:
            converted_value: Any = raw_value
        else:
            converted_value: Any = argument.conversion_from_yaml(raw_value)

        if converted_value is not None:
            setattr(new_args, argument.identifier, converted_value)

    return new_args


def _check_if_autoloading_list_input(values: list[str] | None, default_file_path: str, argument_identifier: str) -> list[str] | None:
    if values is not None:
        return values
    if os.path.isfile(default_file_path):
        cprint(f"[INFO] Auto-loading {argument_identifier} from '{default_file_path}'")
        return [default_file_path]
    return None


def _resolve_hash_list_input(values: list[str], argument_identifier: str) -> set[str]:
    if len(values) == 1 and os.path.isfile(file_path := values[0]):
        loaded: set[str] = _load_commit_set(file_path)
        cprint(f"[INFO] Loaded {len(loaded)} {'hash' if len(loaded) == 1 else 'hashes'} from '{file_path}' (via {argument_identifier})", color=INFO_COLOR)
        return loaded
    return {hash_.lower() for hash_ in values}


def _resolve_file_paths_input(values: list[str], argument_identifier: str) -> set[str]:
    if len(values) == 1 and os.path.isfile(file_path := values[0]):
        loaded: set[str] = _load_ignore_paths(file_path)
        cprint(f"[INFO] Loaded {len(loaded)} {'path' if len(loaded) == 1 else 'paths'} from '{file_path}' (via {argument_identifier})", color=INFO_COLOR)
        return loaded
    return {path.replace("\\", "/") for path in values}


def _load_commit_set(path: str) -> set[str]:
    return {line.lower() for line in read_cleaned_file(path)}


def _load_ignore_paths(path: str) -> set[str]:
    return {line.replace("\\", "/") for line in read_cleaned_file(path)}
