#!/usr/bin/env python3
"""skills-sync: link shared agent skills into Claude Code's personal skills folder.

Shared skills live in ~/.agents/skills/<name>/, which other agents read directly.
Claude Code only reads ~/.claude/skills/<name>/SKILL.md, so for every shared skill
this tool keeps a symlink:  ~/.claude/skills/<name> -> ~/.agents/skills/<name>

Safety rules:
  * It only creates or removes symlinks that point into the shared folder
    ("managed links"). Real folders and other symlinks in ~/.claude/skills,
    such as Claude-only skills and Claude Code's own synced/ folder, are never touched.
  * Names matching a pattern in the ignore file are never linked, and an existing
    managed link with an ignored name is removed.
  * Hidden entries (names starting with ".") are always skipped.

Commands:
  skills-sync [sync] [--dry-run]   sync once (the default)
  skills-sync status               show what is linked, Claude-only, ignored, or in conflict
  skills-sync watch                keep running and re-sync whenever either folder or the
                                   ignore file changes

In Agent Hub, entrypoint.sh runs `skills-sync watch` under supervisord as the
developer user; its log is ~/.local/state/skills-sync/service.log.
"""

import argparse
import ctypes
import ctypes.util
import fcntl
import fnmatch
import os
import select
import struct
import sys
import time
from pathlib import Path

HOME = Path.home()
DEFAULT_SOURCE = HOME / ".agents" / "skills"
DEFAULT_TARGET = Path(os.environ.get("CLAUDE_CONFIG_DIR") or HOME / ".claude") / "skills"
DEFAULT_IGNORE = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "skills-sync" / "ignore"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME") or HOME / ".local" / "state") / "skills-sync"

DEFAULT_IGNORE_TEXT = """\
# skills-sync ignore file
#
# One pattern per line, matched against skill folder names with shell globs
# (*, ?, [abc]), like names in a .gitignore. A line starting with ! un-ignores.
# The last matching line wins.
#
# A shared skill whose name matches is not linked into ~/.claude/skills, and its
# link is removed if one exists. Matching folders in ~/.claude/skills are left alone.
# (Real folders there are never touched anyway; this file makes the intent explicit.)

# Claude Code's own folder for skills synced from your claude.ai account
synced
"""

RESCAN_SECONDS = 300      # full re-check even without events, as a safety net
MISSING_RETRY_SECONDS = 10
DEBOUNCE_SECONDS = 0.3


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


# --------------------------------------------------------------------------- ignore file

def load_ignore(path, create):
    if not path.exists():
        if not create:
            text = DEFAULT_IGNORE_TEXT
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(DEFAULT_IGNORE_TEXT)
            text = DEFAULT_IGNORE_TEXT
    else:
        text = path.read_text()
    rules = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pattern = line[1:].strip() if negate else line
        pattern = pattern.strip("/")
        if pattern:
            rules.append((negate, pattern))
    return rules


def is_ignored(name, rules):
    ignored = False
    for negate, pattern in rules:
        if fnmatch.fnmatchcase(name, pattern):
            ignored = not negate
    return ignored


# --------------------------------------------------------------------------- planning

class Ctx:
    def __init__(self, source, target, ignore_file):
        self.source = Path(os.path.abspath(os.path.expanduser(source)))
        self.target = Path(os.path.abspath(os.path.expanduser(target)))
        self.ignore_file = Path(os.path.abspath(os.path.expanduser(ignore_file)))
        # A link counts as ours if it points inside the shared folder, spelled either
        # way (in case ~/.agents itself is a symlink).
        self.roots = {str(self.source), os.path.realpath(self.source)}

    def is_managed(self, link_path):
        try:
            raw = os.readlink(link_path)
        except OSError:
            return False
        dest = os.path.normpath(os.path.join(os.path.dirname(link_path), raw))
        return any(dest.startswith(root + os.sep) for root in self.roots)


def plan(ctx, create_ignore):
    rules = load_ignore(ctx.ignore_file, create=create_ignore)

    shared = set()
    if ctx.source.is_dir():
        for entry in os.scandir(ctx.source):
            if not entry.name.startswith(".") and entry.is_dir():  # follows symlinks
                shared.add(entry.name)

    existing = {}
    if ctx.target.is_dir():
        for entry in os.scandir(ctx.target):
            existing[entry.name] = entry

    actions = []  # (op, name, link_target)
    report = {"linked": [], "claude_only": [], "ignored": [], "conflicts": []}

    for name in sorted(shared):
        want = str(ctx.source / name)
        entry = existing.get(name)
        if is_ignored(name, rules):
            report["ignored"].append(name)
            if entry is not None and entry.is_symlink() and ctx.is_managed(entry.path):
                actions.append(("unlink", name, None))
            continue
        if entry is None:
            actions.append(("link", name, want))
        elif entry.is_symlink() and ctx.is_managed(entry.path):
            if os.readlink(entry.path) != want:
                actions.append(("relink", name, want))
            else:
                report["linked"].append(name)
        elif entry.is_symlink():
            report["conflicts"].append(
                (name, f"a symlink this tool didn't create is already there (-> {os.readlink(entry.path)})"))
        else:
            report["conflicts"].append(
                (name, "a real folder in the Claude skills folder has this name, so the Claude-only one is used"))

    for name, entry in sorted(existing.items()):
        if name in shared or name.startswith("."):
            continue
        if entry.is_symlink() and ctx.is_managed(entry.path):
            actions.append(("unlink", name, None))  # the shared skill is gone
        elif is_ignored(name, rules):
            report["ignored"].append(name)
        else:
            report["claude_only"].append(name)

    report["ignored"] = sorted(set(report["ignored"]))
    return actions, report


def apply(ctx, actions, dry_run):
    for op, name, dest in actions:
        path = ctx.target / name
        if dry_run:
            log(f"would {op} {name}" + (f" -> {dest}" if dest else ""))
            continue
        try:
            if op in ("link", "relink"):
                ctx.target.mkdir(parents=True, exist_ok=True)
                tmp = ctx.target / f".{name}.skills-sync-tmp"
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                os.symlink(dest, tmp)
                try:
                    if op == "link" and os.path.lexists(path):
                        raise FileExistsError(f"{path} appeared meanwhile")
                    os.replace(tmp, path)  # atomic; replaces a symlink, never follows it
                finally:
                    if os.path.lexists(tmp):
                        os.unlink(tmp)
                log(f"{op}ed {name} -> {dest}")
            elif op == "unlink":
                # Re-check right before removing: only ever delete our own links.
                if os.path.islink(path) and ctx.is_managed(path):
                    os.unlink(path)
                    log(f"unlinked {name}")
        except OSError as exc:
            log(f"error: could not {op} {name}: {exc}")


class Lock:
    def __enter__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.fh = open(STATE_DIR / "lock", "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()


def sync_once(ctx, dry_run=False):
    with Lock():
        actions, report = plan(ctx, create_ignore=not dry_run)
        apply(ctx, actions, dry_run)
    return actions, report


# --------------------------------------------------------------------------- commands

def fmt_list(items):
    return ", ".join(items) if items else "-"


def cmd_sync(ctx, args):
    actions, report = sync_once(ctx, dry_run=args.dry_run)
    if not actions:
        log("already in sync")
    for name, why in report["conflicts"]:
        log(f"skipped {name}: {why}")
    return 0


def cmd_status(ctx, args):
    actions, report = plan(ctx, create_ignore=False)
    print(f"Shared folder: {ctx.source}{'' if ctx.source.is_dir() else '  (missing)'}")
    print(f"Claude folder: {ctx.target}{'' if ctx.target.is_dir() else '  (missing)'}")
    print(f"Ignore file:   {ctx.ignore_file}{'' if ctx.ignore_file.exists() else '  (not created yet; defaults apply)'}")
    print()
    print(f"Linked      ({len(report['linked'])}): {fmt_list(report['linked'])}")
    print(f"Claude-only ({len(report['claude_only'])}): {fmt_list(report['claude_only'])}")
    print(f"Ignored     ({len(report['ignored'])}): {fmt_list(report['ignored'])}")
    print(f"Conflicts   ({len(report['conflicts'])}):" + ("" if report["conflicts"] else " -"))
    for name, why in report["conflicts"]:
        print(f"  {name}: {why}")
    if actions:
        print(f"Pending     ({len(actions)}): " + ", ".join(f"{op} {name}" for op, name, _ in actions))
        print("Run `skills-sync` to apply them.")
    return 0


# Linux inotify, called through libc so no extra packages are needed.
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_IGNORED = 0x00008000
IN_ONLYDIR = 0x01000000
IN_NONBLOCK = 0o4000
IN_CLOEXEC = 0o2000000
DIR_MASK = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_DELETE_SELF | IN_MOVE_SELF | IN_ONLYDIR
IGNORE_DIR_MASK = DIR_MASK | IN_CLOSE_WRITE
REBUILD_FLAGS = IN_IGNORED | IN_DELETE_SELF | IN_MOVE_SELF


class Inotify:
    def __init__(self):
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.libc = libc
        self.fd = libc.inotify_init1(IN_CLOEXEC | IN_NONBLOCK)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 failed")

    def add(self, path, mask):
        return self.libc.inotify_add_watch(self.fd, os.fsencode(str(path)), mask) >= 0

    def drain(self):
        flags = 0
        while True:
            try:
                buf = os.read(self.fd, 65536)
            except BlockingIOError:
                return flags
            offset = 0
            while offset < len(buf):
                _wd, mask, _cookie, length = struct.unpack_from("iIII", buf, offset)
                flags |= mask
                offset += 16 + length

    def close(self):
        os.close(self.fd)


def cmd_watch(ctx, args):
    last_conflicts = None

    def do_sync():
        nonlocal last_conflicts
        try:
            _actions, report = sync_once(ctx)
        except Exception as exc:  # keep the watcher alive; the next event retries
            log(f"error during sync: {exc}")
            return
        if report["conflicts"] != last_conflicts:
            for name, why in report["conflicts"]:
                log(f"skipped {name}: {why}")
            last_conflicts = report["conflicts"]

    log(f"watching {ctx.source} -> {ctx.target} (ignore file: {ctx.ignore_file})")

    while True:
        try:
            ino = Inotify()
        except OSError as exc:
            log(f"inotify unavailable ({exc}); falling back to checking every 5 seconds")
            while True:
                do_sync()
                time.sleep(5)

        missing = [d for d, mask in ((ctx.source, DIR_MASK),
                                     (ctx.target, DIR_MASK),
                                     (ctx.ignore_file.parent, IGNORE_DIR_MASK))
                   if not ino.add(d, mask)]
        if missing:
            log("waiting for missing folder(s): " + ", ".join(map(str, missing)))
        timeout = MISSING_RETRY_SECONDS if missing else RESCAN_SECONDS
        # Sync only once the watches exist, so a change made in between is never missed.
        do_sync()

        rebuild = False
        while not rebuild:
            ready, _, _ = select.select([ino.fd], [], [], timeout)
            if ready:
                time.sleep(DEBOUNCE_SECONDS)  # let a burst of changes settle
                if ino.drain() & REBUILD_FLAGS:
                    rebuild = True  # a watched folder was removed or moved
            elif missing:
                rebuild = True  # retry adding the watches
            do_sync()
        ino.close()


def main():
    parser = argparse.ArgumentParser(
        prog="skills-sync",
        description="Link shared skills from ~/.agents/skills into ~/.claude/skills.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="shared skills folder (default: %(default)s)")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Claude skills folder (default: %(default)s)")
    parser.add_argument("--ignore-file", default=str(DEFAULT_IGNORE), help="ignore file (default: %(default)s)")
    sub = parser.add_subparsers(dest="command")

    p_sync = sub.add_parser("sync", help="sync once (default)")
    p_sync.add_argument("--dry-run", action="store_true", help="show what would change without changing anything")
    sub.add_parser("status", help="show linked, Claude-only, ignored and conflicting skills")
    sub.add_parser("watch", help="keep running and re-sync on every change")

    # Global options are accepted after the subcommand too (e.g. `watch --source X`).
    for p in (p_sync, *[sub.choices[n] for n in ("status", "watch")]):
        p.add_argument("--source", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        p.add_argument("--target", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        p.add_argument("--ignore-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.command is None:
        args.command = "sync"
        args.dry_run = False
    ctx = Ctx(args.source, args.target, args.ignore_file)
    handler = {
        "sync": cmd_sync,
        "status": cmd_status,
        "watch": cmd_watch,
    }[args.command]
    try:
        return handler(ctx, args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
