#!/usr/bin/env python3
"""What was shipped in a window, as one compact digest for finding post ideas.

Reads three things, all read-only:
  - kururu cards that moved to done or review in the window (kururu's own
    database, opened read-only; the newest move per card);
  - git commits in every repository directly under each root (all branches,
    no merges);
  - Markdown files changed in the window under the docs folders.

Items whose text names a private project from the config are tagged
[private: Name]; items already in the offered log are tagged [offered ...].

  python3 gather.py                      # yesterday and today (the default)
  python3 gather.py --window today       # today | yesterday | recent | week | 3d
  python3 gather.py --since 2026-11-13 --until 2026-11-16
  python3 gather.py --card KUR-288       # one card's whole body
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
DEFAULT_HOME = HOME / "Documents" / "Kururu" / "build-in-public"
DEFAULT_DB = Path(os.environ.get("KURURU_DATA_DIR") or (Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local" / "share") / "kururu")) / "kururu.db"
SUBJECT_MAX = 240


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--window", default="recent", help="today, yesterday, recent (yesterday + today), week (7 days), or Nd")
    p.add_argument("--since", help="YYYY-MM-DD, local time, inclusive")
    p.add_argument("--until", help="YYYY-MM-DD, local time, inclusive (default today)")
    p.add_argument("--home", default=str(DEFAULT_HOME), help="folder with config.md and offered.jsonl")
    p.add_argument("--db", default=str(DEFAULT_DB), help="kururu's database")
    p.add_argument("--card", help="print one card whole, by code (KUR-288) and exit")
    p.add_argument("--no-cards", action="store_true")
    p.add_argument("--no-git", action="store_true")
    p.add_argument("--no-docs", action="store_true")
    return p.parse_args()


def window(args: argparse.Namespace) -> tuple[dt.datetime, dt.datetime]:
    today = dt.date.today()
    if args.since:
        start = dt.date.fromisoformat(args.since)
        end = dt.date.fromisoformat(args.until) if args.until else today
    else:
        w = args.window
        if w == "today":
            start, end = today, today
        elif w == "yesterday":
            start = end = today - dt.timedelta(days=1)
        elif w == "recent":
            start, end = today - dt.timedelta(days=1), today
        elif w == "week":
            start, end = today - dt.timedelta(days=6), today
        elif re.fullmatch(r"\d+d", w):
            start, end = today - dt.timedelta(days=int(w[:-1]) - 1), today
        else:
            sys.exit(f"unknown window {w!r}")
    return dt.datetime.combine(start, dt.time.min), dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min)


# --- config and log ---------------------------------------------------------

def read_config(home: Path) -> dict:
    """The few things the script needs from config.md: roots, docs folders and private names."""
    cfg = {"roots": [HOME / "Desktop" / "Nyto"], "docs": [], "private": {}}
    path = home / "config.md"
    if not path.exists():
        return cfg
    section = None
    roots, docs = [], []
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        m = re.match(r"\s*-\s+(.*)", line)
        if not m or section is None:
            continue
        item = m.group(1).strip().strip("`")
        if section.startswith("project roots"):
            roots.append(Path(os.path.expanduser(item.split()[0].strip("`"))))
        elif section.startswith("docs folders"):
            docs.append(Path(os.path.expanduser(item.split()[0].strip("`"))))
        elif section.startswith(("private", "unknown")):
            # "- Name: alias, alias (a note)" -> words that mark an item as this project's
            name, _, rest = item.partition(":")
            words = [name.strip()] + [w.strip() for w in rest.split("(")[0].split(",") if w.strip()]
            label = name.strip() if section.startswith("private") else f"{name.strip()}?"
            cfg["private"][label] = [w for w in words if w]
    if roots:
        cfg["roots"] = roots
    cfg["docs"] = docs
    return cfg


def private_tags(text: str, private: dict) -> str:
    low = text.lower()
    hits = [name for name, words in private.items() if any(re.search(r"(?<![\w])" + re.escape(w.lower()) + r"(?![\w])", low) for w in words)]
    # "Name?" is a project not yet known to be the owner's or a client's: ask before naming it
    return f" [private: {', '.join(hits)}]" if hits else ""


def read_offered(home: Path) -> dict[str, str]:
    """Source key -> 'offered <date> #n' for everything offered before."""
    seen: dict[str, str] = {}
    path = home / "offered.jsonl"
    if not path.exists():
        return seen
    for line in path.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in e.get("sources", []):
            n = f" #{e['n']}" if e.get("n") else ""
            seen.setdefault(key, f"offered {e.get('date', '?')}{n} ({e.get('status', '?')})")
    return seen


# --- cards ------------------------------------------------------------------

def card_code(workspace: str | None, number: int) -> str:
    if not workspace:
        return f"#{number}"
    prefix = "".join(ch for ch in workspace if ch.isalnum())[:3].upper()
    return f"{prefix}-{number}" if prefix else f"#{number}"


def open_db(path: str) -> sqlite3.Connection | None:
    if not Path(path).exists():
        return None
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


CARDS_SQL = """
select w.name, c.number, c.column_id, max(e.at), c.title
from card_events e
join cards c on c.id = e.card_id
join boards b on b.id = c.board_id
left join workspaces w on w.key = b.workspace_key
where e.kind = 'moved' and e.to_column in ('done', 'review')
  and e.at >= ? and e.at < ?
  and c.deleted_at is null and c.column_id in ('done', 'review')
group by c.id
order by coalesce(w.name, ''), max(e.at)
"""


def cards(db: sqlite3.Connection, start: dt.datetime, end: dt.datetime, private: dict, offered: dict) -> list[str]:
    rows = db.execute(CARDS_SQL, (int(start.timestamp() * 1000), int(end.timestamp() * 1000))).fetchall()
    out, last_ws = [], object()
    for ws, number, column, at, title in rows:
        if ws != last_ws:
            out.append(f"\n### {ws or 'profile board'}")
            last_ws = ws
        code = card_code(ws, number)
        when = dt.datetime.fromtimestamp(at / 1000).strftime("%m-%d %H:%M")
        tags = private_tags(f"{ws or ''} {title}", private)
        seen = f" [{offered[code]}]" if code in offered else ""
        out.append(f"- {code} {column} {when} {title}{tags}{seen}")
    return out


def one_card(db: sqlite3.Connection, code: str) -> str:
    m = re.fullmatch(r"([A-Za-z0-9]{1,3})-(\d+)", code.strip())
    if not m:
        sys.exit("card code like KUR-288")
    prefix, number = m.group(1).upper(), int(m.group(2))
    rows = db.execute(
        "select w.name, c.title, c.body, c.column_id from cards c join boards b on b.id = c.board_id "
        "left join workspaces w on w.key = b.workspace_key where c.number = ? and c.deleted_at is null",
        (number,),
    ).fetchall()
    for ws, title, body, column in rows:
        if card_code(ws, number) == f"{prefix}-{number}":
            return f"{prefix}-{number} ({ws}, {column}) {title}\n\n{body}"
    sys.exit(f"no card {code}")


# --- git ----------------------------------------------------------------------

def repos(roots: list[Path]) -> list[Path]:
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and not d.name.endswith(".worktrees") and (d / ".git").exists():
                found.append(d)
    return found


def commits(repo: Path, start: dt.datetime, end: dt.datetime, private: dict, offered: dict) -> list[str]:
    fmt = "%h%x1f%ad%x1f%s%x1e"
    try:
        raw = subprocess.run(
            ["git", "-C", str(repo), "log", "--all", "--no-merges", f"--since={start.isoformat()}", f"--until={end.isoformat()}",
             "--date=format-local:%m-%d %H:%M", f"--format={fmt}"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    out, seen_subjects = [], set()
    for rec in raw.split("\x1e"):
        parts = rec.strip("\n").split("\x1f")
        if len(parts) != 3:
            continue
        sha, when, subject = parts
        if subject in seen_subjects:  # the same change on two branches
            continue
        seen_subjects.add(subject)
        if re.match(r"(?i)^(merge|wip\b|bump|chore\(deps\))", subject):
            continue
        short = subject if len(subject) <= SUBJECT_MAX else subject[: SUBJECT_MAX - 1] + "…"
        key = f"{repo.name}@{sha}"
        seen = f" [{offered[key]}]" if key in offered else ""
        out.append(f"- {sha} {when} {short}{seen}")
    return out


# --- docs ---------------------------------------------------------------------

def docs(folders: list[Path], start: dt.datetime, end: dt.datetime, private: dict, offered: dict) -> list[str]:
    out = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.md")):
            rel = path.relative_to(folder)
            if len(rel.parts) > 2 or any(p in {"results", "transcripts", "harness", "node_modules"} for p in rel.parts):
                continue
            mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
            if not (start <= mtime < end):
                continue
            head = ""
            for line in path.read_text(errors="replace").splitlines()[:5]:
                if line.startswith("#"):
                    head = line.lstrip("# ").strip()
                    break
            short = str(path).replace(str(HOME), "~")
            seen = f" [{offered[short]}]" if short in offered else ""
            out.append(f"- {short} {mtime:%m-%d %H:%M} {head}{private_tags(str(rel) + ' ' + head, private)}{seen}")
    return out


def main() -> None:
    args = parse_args()
    home = Path(os.path.expanduser(args.home))
    cfg = read_config(home)
    db = None if args.no_cards else open_db(args.db)

    if args.card:
        if not db:
            sys.exit("kururu's database is not readable here; use Kuru's cards tool with card=<code>")
        print(one_card(db, args.card))
        return

    start, end = window(args)
    offered = read_offered(home)
    print(f"# Shipped {start:%Y-%m-%d} to {(end - dt.timedelta(days=1)):%Y-%m-%d} (local time)")
    if not (home / "config.md").exists():
        print(f"\n(no config at {home / 'config.md'}: private names are not tagged)")

    if not args.no_cards:
        print("\n## Cards moved to done or review")
        if db:
            try:
                print("\n".join(cards(db, start, end, cfg["private"], offered)) or "(none)")
            except sqlite3.Error as e:
                print(f"(database not readable: {e}; use Kuru's cards and card_history tools)")
        else:
            print("(no database here; use Kuru's cards and card_history tools)")

    if not args.no_git:
        print("\n## Commits")
        for repo in repos(cfg["roots"]):
            lines = commits(repo, start, end, cfg["private"], offered)
            if lines:
                print(f"\n### {repo.name} ({len(lines)}){private_tags(repo.name, cfg['private'])}")
                print("\n".join(lines))

    if not args.no_docs:
        print("\n## Reports and research changed")
        print("\n".join(docs(cfg["docs"], start, end, cfg["private"], offered)) or "(none)")


if __name__ == "__main__":
    main()
