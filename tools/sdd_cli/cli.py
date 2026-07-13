"""Thin CLI orchestrator: delegates to specialized modules."""

from __future__ import annotations

import sys

from ._shared import REPO_ROOT, CliError, parse_pairs, read_json


# ── Entry point ──────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("Python 3.11+ is required.", file=sys.stderr)
        return 2

    args = _parse_cli(argv)
    try:
        return args.func(args)
    except CliError as ex:
        print(str(ex), file=sys.stderr)
        return 1


# ── Parser ───────────────────────────────────────────────────────────────

def _parse_cli(argv: list[str] | None):
    import argparse
    parser = argparse.ArgumentParser(prog="python -m tools.sdd_cli")
    parser.set_defaults(func=_fallback)
    parser.add_argument("--root", default=str(REPO_ROOT), help="Repository root path")

    sub = parser.add_subparsers(dest="command", required=False)

    # prereqs
    prereqs = sub.add_parser("prereqs")
    prereqs.add_argument("prereqs_args", nargs="+")
    prereqs.set_defaults(func=_dispatch_prereqs)

    # environment-lab
    envlab = sub.add_parser("environment-lab")
    envlab.add_argument("envlab_args", nargs="+")
    envlab.set_defaults(func=_dispatch_environment_lab)

    # tool-installer
    tools = sub.add_parser("tool-installer")
    tools.add_argument("tool_args", nargs="+")
    tools.set_defaults(func=_dispatch_tool_installer)

    # template-installer
    tmpl = sub.add_parser("template-installer")
    tmpl.add_argument("tmpl_args", nargs="+")
    tmpl.set_defaults(func=_dispatch_template_installer)

    # guidance
    guide = sub.add_parser("guidance")
    guide.add_argument("guide_args", nargs="+")
    guide.set_defaults(func=_dispatch_guidance)

    # dev-flow
    flow = sub.add_parser("dev-flow")
    flow.add_argument("flow_args", nargs="+")
    flow.set_defaults(func=_dispatch_dev_flow)

    # memory-search
    mem = sub.add_parser("memory-search")
    mem.add_argument("mem_args", nargs="+")
    mem.set_defaults(func=_dispatch_memory_search)

    return parser.parse_args(argv)


# ── Dispatchers ──────────────────────────────────────────────────────────

def _fallback(args: Any) -> int:
    print("Top-level commands: prereqs, environment-lab, tool-installer, "
          "template-installer, guidance, dev-flow, memory-search")
    return 1


def _dispatch_prereqs(args: Any) -> int:
    from .prereqs import run_prereqs
    options = parse_pairs(getattr(args, "prereqs_args", []))
    sys.argv = ["prereqs"] + options.get("_rest", [])
    return run_prereqs(options.get("_rest", []))


def _dispatch_environment_lab(args: Any) -> int:
    from .environment_lab import run_environment_lab
    return run_environment_lab(getattr(args, "envlab_args", []))


def _dispatch_tool_installer(args: Any) -> int:
    from .tool_installer import run_tool_installer
    return run_tool_installer(getattr(args, "tool_args", []))


def _dispatch_template_installer(args: Any) -> int:
    from .template_installer import run_template_installer
    return run_template_installer(getattr(args, "tmpl_args", []))


def _dispatch_guidance(args: Any) -> int:
    from .guidance import run_guidance
    return run_guidance(getattr(args, "guide_args", []))


def _dispatch_dev_flow(args: Any) -> int:
    from .dev_flow import run_dev_flow
    return run_dev_flow(getattr(args, "flow_args", []))


def _dispatch_memory_search(args: Any) -> int:
    from .memory_search import run_memory_search
    return run_memory_search(getattr(args, "mem_args", []))