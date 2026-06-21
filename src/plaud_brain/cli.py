"""Command-line interface for plaud-brain."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from plaud_brain import __version__
from plaud_brain.config import Config, ConfigError, _strip_bearer, load_config
from plaud_brain.pipeline import Pipeline
from plaud_brain.sources import CloudSource, UsbSource
from plaud_brain.state import ProcessedStore

ENV_PATH = Path(".env")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _err(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------


def cmd_auth(args: argparse.Namespace) -> int:
    token = args.token
    if not token:
        print(
            "Paste your PLAUD token (the 'tokenstr' value from web.plaud.ai "
            "local storage).\nIt may start with 'bearer '. Input is hidden if "
            "your terminal supports it.",
            file=sys.stderr,
        )
        try:
            import getpass

            token = getpass.getpass("PLAUD_TOKEN: ")
        except (EOFError, KeyboardInterrupt):
            return _err("cancelled")
    token = _strip_bearer(token)
    if not token:
        return _err("empty token")
    _upsert_env("PLAUD_TOKEN", token)
    print(f"Saved PLAUD_TOKEN to {ENV_PATH.resolve()}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cfg = _load(args)
    from plaud_brain.plaud import PlaudCloudClient, PlaudError

    try:
        client = PlaudCloudClient(cfg.plaud.token, region=cfg.plaud.region)
        recordings = client.list_recordings(limit=args.limit)
    except PlaudError as exc:
        return _err(str(exc))
    if not recordings:
        print("No recordings found.")
        return 0
    store = ProcessedStore(cfg.pipeline.state_path)
    for r in recordings:
        done = "✓" if store.has(f"cloud:{r.id}") else " "
        date = r.created_at.strftime("%Y-%m-%d %H:%M")
        mins = r.duration_ms // 60000
        print(f"[{done}] {date}  {mins:>3}m  {r.title}  ({r.id})")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    cfg = _load(args)
    sources = _build_sources(cfg, args.source)
    if not sources:
        return _err(
            "no sources enabled. Use --source cloud (needs PLAUD_TOKEN) or "
            "set [usb].mount_path for --source usb."
        )

    if not args.dry_run and not cfg.gemini.api_key:
        return _err("GEMINI_API_KEY is not set (needed for transcription). Add it to .env.")

    pipeline = Pipeline(cfg, log=_log)
    try:
        result = pipeline.run(
            sources,
            limit=args.limit,
            reprocess=args.reprocess,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ConfigError) as exc:
        return _err(str(exc))

    print(
        f"\nDone. processed={result.processed} skipped={result.skipped} "
        f"failed={result.failed}",
        file=sys.stderr,
    )
    for note in result.notes:
        print(note)
    return 1 if result.failed and result.processed == 0 else 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = _load(args)
    store = ProcessedStore(cfg.pipeline.state_path)
    entries = store.entries
    print(f"State file: {cfg.pipeline.state_path}")
    print(f"Processed recordings: {len(entries)}")
    by_source: dict[str, int] = {}
    for e in entries.values():
        by_source[e.get("source", "?")] = by_source.get(e.get("source", "?"), 0) + 1
    for src, n in sorted(by_source.items()):
        print(f"  {src}: {n}")
    if args.verbose:
        for uid, e in sorted(entries.items(), key=lambda kv: kv[1].get("processed_at", "")):
            print(f"  {e.get('processed_at', '?')}  {uid}  -> {e.get('note_path')}")
    return 0


def _normalize_uid(value: str) -> str:
    """Accept a raw recording id or a full uid; default cloud ids to 'cloud:'."""
    return value if value.startswith(("cloud:", "usb:")) else f"cloud:{value}"


def cmd_skip(args: argparse.Namespace) -> int:
    """Mark recordings as handled so sync ignores them, without processing them.

    Useful for the PLAUD demo recordings or empty/aborted clips you never
    want in your vault. Pass the ids shown in `plaud-brain list`.
    """
    cfg = _load(args)
    store = ProcessedStore(cfg.pipeline.state_path)

    # Best-effort: look up nice titles from the cloud so `status` reads well.
    titles: dict[str, str] = {}
    if cfg.plaud.token:
        try:
            from plaud_brain.plaud import PlaudCloudClient

            client = PlaudCloudClient(cfg.plaud.token, region=cfg.plaud.region)
            for r in client.list_recordings(limit=max(cfg.plaud.list_limit, len(args.ids))):
                titles[r.id] = r.title
        except Exception:  # noqa: BLE001 - titles are cosmetic; ignore failures
            pass

    for raw in args.ids:
        uid = _normalize_uid(raw)
        plain = uid.split(":", 1)[1]
        title = titles.get(plain, plain)
        store.mark(uid, source="skip", note_path="(skipped)", title=title)
        print(f"skipping: {title} ({plain})")
    print(f"\n{len(args.ids)} recording(s) will now be ignored by sync.")
    return 0


def cmd_unskip(args: argparse.Namespace) -> int:
    """Undo a skip (or remove any recording from the processed state)."""
    cfg = _load(args)
    store = ProcessedStore(cfg.pipeline.state_path)
    for raw in args.ids:
        uid = _normalize_uid(raw)
        if store.forget(uid):
            print(f"un-skipped: {uid}")
        else:
            print(f"not in state: {uid}")
    return 0


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _load(args: argparse.Namespace) -> Config:
    try:
        return load_config(args.config)
    except ConfigError as exc:
        raise SystemExit(_err(str(exc))) from None


def _build_sources(cfg: Config, which: str) -> list:
    sources: list = []
    if which in ("cloud", "all") and cfg.plaud.token:
        sources.append(CloudSource(cfg))
    if which in ("usb", "all") and cfg.usb.enabled:
        sources.append(UsbSource(cfg))
    return sources


def _upsert_env(key: str, value: str) -> None:
    lines: list[str] = []
    found = False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
# Parser
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plaud-brain",
        description="Pull PLAUD Note recordings, transcribe & summarize with "
        "Gemini, and file them into an Obsidian vault.",
    )
    p.add_argument("--version", action="version", version=f"plaud-brain {__version__}")
    p.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to config.toml (default: ./config.toml if present).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("auth", help="Save your PLAUD token to .env")
    pa.add_argument("token", nargs="?", help="Token value (omit to enter it interactively)")
    pa.set_defaults(func=cmd_auth)

    pl = sub.add_parser("list", help="List recent cloud recordings")
    pl.add_argument("-n", "--limit", type=int, default=20)
    pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("sync", help="Process new recordings into your vault")
    ps.add_argument(
        "--source",
        choices=["cloud", "usb", "all"],
        default="all",
        help="Which source(s) to pull from (default: all).",
    )
    ps.add_argument(
        "-n", "--limit", type=int, default=None, help="Max recordings to process per source."
    )
    ps.add_argument(
        "--reprocess",
        action="store_true",
        help="Re-process recordings even if already in the state file.",
    )
    ps.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be processed without calling Gemini or writing notes.",
    )
    ps.set_defaults(func=cmd_sync)

    pst = sub.add_parser("status", help="Show processing state")
    pst.add_argument("-v", "--verbose", action="store_true")
    pst.set_defaults(func=cmd_status)

    psk = sub.add_parser(
        "skip",
        help="Mark recordings as handled so sync ignores them (e.g. demo clips)",
    )
    psk.add_argument("ids", nargs="+", help="Recording id(s) from `plaud-brain list`")
    psk.set_defaults(func=cmd_skip)

    pus = sub.add_parser("unskip", help="Undo skip / forget a recording from state")
    pus.add_argument("ids", nargs="+", help="Recording id(s) to remove from state")
    pus.set_defaults(func=cmd_unskip)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return _err("interrupted")
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
