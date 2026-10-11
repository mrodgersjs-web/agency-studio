"""Command line: validate contracts, run a task, list roles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .contract import ContractError, load_contract, load_contracts
from .engine import TaskError, load_task, run_task


def _validate(args) -> int:
    target = Path(args.path)
    try:
        if target.is_dir():
            found = load_contracts(target)
            for c in found.values():
                print(f"OK  {c.path}  ({c.kind})")
            print(f"{len(found)} contracts valid")
        else:
            c = load_contract(target)
            print(f"OK  {c.path}  ({c.kind})")
    except ContractError as exc:
        print(f"INVALID\n{exc}", file=sys.stderr)
        return 1
    return 0


def _run(args) -> int:
    try:
        contracts = load_contracts(args.roles)
        task, base = load_task(args.task)
        result = run_task(task, contracts, base)
    except (ContractError, TaskError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    elif result.accepted:
        print(f"ACCEPTED  {result.task}")
    else:
        print(f"REJECTED  {result.task}")
        for v in result.violations:
            print(f"  {v}")
    return 0 if result.accepted else 1


def _roles(args) -> int:
    try:
        for c in load_contracts(args.roles).values():
            print(f"{c.name:12} {c.kind:10} {c.purpose}")
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agency-studio", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("validate", help="validate a contract file or a directory of contracts")
    p.add_argument("path")
    p.set_defaults(fn=_validate)
    p = sub.add_parser("run", help="run a task file; exit 0 accepted, 1 rejected, 2 bad input")
    p.add_argument("task")
    p.add_argument("--roles", default="roles", help="contracts directory (default: roles)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=_run)
    p = sub.add_parser("roles", help="list contracts")
    p.add_argument("--roles", default="roles")
    p.set_defaults(fn=_roles)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
