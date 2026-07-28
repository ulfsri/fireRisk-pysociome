"""
pysociome command-line interface.

Usage:
    pysociome set_api <key>   — save your Census API key to .env
"""

import argparse
from pathlib import Path


def _set_api_key(key: str) -> None:
    """Write (or update) Census_API_KEY in .env in the current directory."""
    env_path = Path.cwd() / ".env"

    if env_path.exists():
        lines = env_path.read_text().splitlines()
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("Census_API_KEY"):
                new_lines.append(f"Census_API_KEY = {key}")
                updated = True
            else:
                new_lines.append(line)
        if not updated:
            new_lines.append(f"Census_API_KEY = {key}")
        env_path.write_text("\n".join(new_lines) + "\n")
        action = "updated"
    else:
        env_path.write_text(f"Census_API_KEY = {key}\n")
        action = "created"

    print(f"Census API key {action} in {env_path}")
    print("Make sure .env is listed in your .gitignore — never commit your API key.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pysociome",
        description="pysociome utilities",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # set_api
    sp = subparsers.add_parser(
        "set_api",
        help="Save your US Census Bureau API key to a local .env file",
    )
    sp.add_argument("key", help="Your Census API key")

    args = parser.parse_args()

    if args.command == "set_api":
        _set_api_key(args.key)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
