"""Entry point.

Two ways to invoke this — both end up here:
  - `graphite-mcp`              (the entry-point script installed by pip)
  - `python -m graphite_mcp`     (module form, no install needed if on path)
"""
import asyncio

from .server import run


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
