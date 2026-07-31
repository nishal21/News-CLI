"""CLI entry — thin argparse wrapper around the Textual app."""

from __future__ import annotations

import argparse
import sys

from worldnews import __version__
from worldnews.storage import CustomFeeds
from worldnews.terminal_setup import configure_terminal
from worldnews.text_display import normalize_script_mode


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worldnews",
        description="World News CLI — terminal news reader (Textual TUI)",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--chat", action="store_true", help="Open AI chat on launch")
    p.add_argument("--summary", action="store_true", help="Open summary digest mode")
    p.add_argument("--offline", action="store_true", help="Start in offline mode")
    p.add_argument(
        "--add-feed",
        nargs=2,
        metavar=("NAME", "URL"),
        help="Add a custom RSS feed and exit",
    )
    p.add_argument(
        "--category",
        "-c",
        metavar="NAME",
        help="Start on a category (e.g. tech, sports, ai)",
    )
    p.add_argument(
        "--plain",
        "--ascii",
        dest="plain",
        action="store_true",
        help="Latin-only TUI for complex scripts (no Malayalam/Arabic glyphs)",
    )
    p.add_argument(
        "--native-titles",
        dest="native_titles",
        action="store_true",
        help="Show native-script titles in the list (may overlap on Windows Terminal)",
    )
    return p


def main_entry() -> None:
    # UTF-8 + Windows VT before any prints / Textual
    configure_terminal()

    parser = build_parser()
    args, _unknown = parser.parse_known_args()

    if args.add_feed:
        name, url = args.add_feed
        feeds = CustomFeeds()
        if feeds.add(name, url):
            print(f"Added feed: {name}")
        else:
            print("Feed already exists", file=sys.stderr)
            sys.exit(1)
        return

    start_mode = None
    if args.chat:
        start_mode = "chat"
    elif args.summary:
        start_mode = "summary"
    elif args.offline:
        start_mode = "offline"

    script_mode = None
    if getattr(args, "plain", False):
        script_mode = "plain"
    elif getattr(args, "native_titles", False):
        script_mode = "native"
    if script_mode:
        script_mode = normalize_script_mode(script_mode)

    from worldnews.app import run_app

    run_app(
        start_feed=args.category,
        start_mode=start_mode,
        script_mode=script_mode,
    )


def main() -> None:
    main_entry()


if __name__ == "__main__":
    main_entry()
