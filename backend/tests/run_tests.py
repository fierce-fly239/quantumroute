#!/usr/bin/env python3
"""Test runner with no dependencies.

Homebrew's Python refuses `pip install pytest` without a virtual environment
(PEP 668), and forcing it risks the interpreter the rest of the project runs on.
So this runs the tests instead: it finds every `test_*` function in every
`test_*.py` file beside it and calls them.

The test files are written as plain pytest-style functions, so if anyone on the
team does set up a virtualenv, `pytest` runs these exact same files unchanged.

    python3 tests/run_tests.py
"""

import importlib
import pathlib
import sys
import traceback

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))


def main() -> int:
    files = sorted(p for p in HERE.glob("test_*.py"))
    passed: list[str] = []
    failed: list[tuple[str, str]] = []

    for path in files:
        module = importlib.import_module(f"tests.{path.stem}")
        names = sorted(n for n in dir(module) if n.startswith("test_"))
        for name in names:
            fn = getattr(module, name)
            if not callable(fn):
                continue
            label = f"{path.stem}.{name}"
            try:
                fn()
            except Exception:
                failed.append((label, traceback.format_exc()))
                print(f"FAIL  {label}")
            else:
                passed.append(label)
                print(f"ok    {label}")

    print()
    if failed:
        for label, tb in failed:
            print("=" * 70)
            print(label)
            print("-" * 70)
            print(tb)
        print(f"{len(passed)} passed, {len(failed)} FAILED")
        return 1

    print(f"{len(passed)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
