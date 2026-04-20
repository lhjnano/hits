"""HITS Command Line Interface.

Usage:
    hits                     Start web server (default)
    hits server [--port PORT] [--dev]
    hits resume [--project PATH] [--list] [--token-budget N]
    hits backup              Backup all HITS data
    hits backup --list       List backups
    hits restore             Restore latest backup
    hits restore --latest    Restore latest backup
    hits status              Show current data status
"""

import argparse
import asyncio
import json
import os
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path


HITS_HOME = Path(os.environ.get("HITS_DATA_PATH", Path.home() / ".hits"))
BACKUP_DIR = HITS_HOME / "backups"
DATA_DIR = HITS_HOME / "data"
AUTH_DIR = HITS_HOME / ".auth"


def _size_fmt(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.0f}TB"


def _count_files(directory: Path, pattern: str = "*.json") -> int:
    if not directory.exists():
        return 0
    return sum(1 for f in directory.glob(pattern) if f.name != "index.json")


def cmd_resume(args):
    """Resume work on a project - show latest checkpoint with actionable context."""
    from hits_core.service.checkpoint_service import CheckpointService
    from hits_core.service.signal_service import SignalService
    from hits_core.ai.checkpoint_compressor import CheckpointCompressor
    from hits_core.storage.file_store import FileStorage

    async def _resume():
        storage = FileStorage()
        cp_service = CheckpointService(storage=storage)
        sig_service = SignalService()
        compressor = CheckpointCompressor()

        # Determine project path
        project_path = getattr(args, "project", None)
        if project_path:
            project_path = str(Path(project_path).resolve())
        else:
            # Auto-detect from CWD
            cwd = Path.cwd().resolve()
            current = cwd
            for _ in range(10):
                if (current / ".git").exists():
                    project_path = str(current)
                    break
                parent = current.parent
                if parent == current:
                    break
                current = parent
            if not project_path:
                project_path = str(cwd)

        token_budget = getattr(args, "token_budget", 2000) or 2000

        # List mode
        if getattr(args, "list", False):
            # List all projects with checkpoints
            projects = await cp_service.list_all_projects()
            if not projects:
                print("No checkpoints found. Start working and use hits_auto_checkpoint() at session end.")
                return

            print(f"📍 Resume Points ({len(projects)} projects)\n")
            for i, p in enumerate(projects, 1):
                name = p.get("project_name", Path(p["project_path"]).name)
                pct = p.get("completion_pct", 0)
                performer = p.get("last_performer", "?")
                ts = (p.get("last_activity") or "")[:16]
                purpose = p.get("purpose", "")
                git = p.get("git_branch", "")

                progress = "█" * (pct // 10) + "░" * (10 - pct // 10)
                print(f"  {i}. {name}")
                print(f"     path: {p['project_path']}")
                print(f"     진행: {progress} {pct}%  by {performer}  at {ts}")
                if purpose:
                    print(f"     목적: {purpose}")
                if git:
                    print(f"     git: {git}")
                print()

            print("Resume: hits resume --project <path>")
            print("        npx @purpleraven/hits resume")
            return

        # Resume mode - show latest checkpoint
        print(f"📂 Resuming: {project_path}")
        print(f"{'─' * 50}\n")

        # Check for pending signals
        signals = await sig_service.check_signals(recipient="any", project_path=project_path)
        if signals:
            print("📬 Pending Signals:")
            for sig in signals:
                icon = {"urgent": "🔴", "high": "🟡"}.get(sig.priority, "🟢")
                print(f"  {icon} From {sig.sender}: {sig.summary}")
                if sig.pending_items:
                    for item in sig.pending_items[:3]:
                        print(f"    • {item}")
            print()

        # Get latest checkpoint
        checkpoint = await cp_service.get_latest_checkpoint(project_path)
        if checkpoint:
            compressed = compressor.compress_checkpoint(checkpoint, token_budget=token_budget)
            print(compressed)
        else:
            # Fallback to handover
            from hits_core.service.handover_service import HandoverService
            hs = HandoverService(storage=storage)
            summary = await hs.get_handover(project_path)
            text = summary.to_text()
            if text.strip() and "기록된 작업이 없습니다" not in text:
                print(text)
            else:
                print("No previous session data found for this project.")
                print("\nTo get started:")
                print("  1. Work on your project with an AI tool")
                print("  2. At session end, call hits_auto_checkpoint()")
                print("  3. Next session: npx @purpleraven/hits resume")

    asyncio.run(_resume())


def cmd_server(args):
    """Start the HITS web server."""
    import uvicorn
    from hits_core.api.server import APIServer

    port = getattr(args, "port", 8765) or 8765
    dev = getattr(args, "dev", False)

    server = APIServer(port=port, dev_mode=dev)
    app = server.create_app()

    print(f"HITS Web Server starting on http://127.0.0.1:{port}", flush=True)
    if dev:
        print("Development mode: CSP relaxed, CORS enabled for Vite", flush=True)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info" if dev else "warning")


def cmd_status(args):
    """Show current HITS data status."""
    print("HITS Status")
    print("=" * 40)

    # Auth
    users_file = AUTH_DIR / "users.json"
    if users_file.exists():
        users = json.loads(users_file.read_text())
        for name, info in users.items():
            role = info.get("role", "?")
            created = info.get("created_at", "?")[:10]
            print(f"  👤 {name} ({role}), created {created}")
    else:
        print("  👤 No accounts (not initialized)")

    print()

    # Data
    if DATA_DIR.exists():
        wl = _count_files(DATA_DIR / "work_logs")
        tr = _count_files(DATA_DIR / "trees")
        sig_p = _count_files(DATA_DIR / "signals" / "pending")
        sig_c = _count_files(DATA_DIR / "signals" / "consumed")
        wf = _count_files(DATA_DIR / "workflows")

        print(f"  📝 Work logs:    {wl}")
        print(f"  🌳 Trees:        {tr}")
        print(f"  📨 Signals:      {sig_p} pending, {sig_c} consumed")
        print(f"  🔄 Workflows:    {wf}")

        # Checkpoints
        cp_dir = DATA_DIR / "checkpoints"
        if cp_dir.exists():
            cp_count = sum(1 for _ in cp_dir.rglob("cp_*.json"))
            project_count = sum(1 for d in cp_dir.iterdir() if d.is_dir())
            print(f"  💾 Checkpoints:  {cp_count} ({project_count} projects)")
        else:
            print(f"  💾 Checkpoints:  0")
    else:
        print("  (no data)")

    # Secrets
    print()
    for name in (".pepper", ".jwt_secret"):
        p = HITS_HOME / name
        print(f"  🔑 {name}: {'✓' if p.exists() else '✗'}")

    # Backups
    print()
    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), reverse=True) if BACKUP_DIR.exists() else []
    print(f"  📦 Backups: {len(backups)}")


def cmd_backup(args):
    """Backup all HITS data to a compressed archive."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    archive_path = BACKUP_DIR / f"{backup_name}.tar.gz"

    # Collect paths to back up
    targets = []
    for name in (".auth", "data", ".pepper", ".jwt_secret"):
        p = HITS_HOME / name
        if p.exists():
            targets.append((name, p))

    if not targets:
        print("No data to backup.")
        return

    # Write to tar.gz
    with tarfile.open(str(archive_path), "w:gz") as tar:
        for name, path in targets:
            tar.add(str(path), arcname=f"{backup_name}/{name}")

    size = _size_fmt(archive_path.stat().st_size)

    # Count what was backed up
    wl = _count_files(DATA_DIR / "work_logs") if (DATA_DIR / "work_logs").exists() else 0
    tr = _count_files(DATA_DIR / "trees") if (DATA_DIR / "trees").exists() else 0

    print(f"✅ Backup complete")
    print(f"   {archive_path}")
    print(f"   Size: {size}  ({wl} work logs, {tr} trees)")


def cmd_restore(args):
    """Restore HITS data from a backup archive."""
    if not BACKUP_DIR.exists():
        print("No backups found.")
        return

    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), reverse=True)
    if not backups:
        print("No backups found.")
        return

    # Pick backup
    target_idx = getattr(args, "number", None)
    if target_idx is not None and target_idx < len(backups):
        archive = backups[target_idx]
    else:
        archive = backups[0]

    print(f"Restoring: {archive.name}")
    print()
    print("⚠  Current data will be replaced. Continue? (y/N): ", end="", flush=True)

    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if answer != "y":
        print("Cancelled.")
        return

    # Auto-backup current state before overwriting
    pre_name = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    pre_path = BACKUP_DIR / f"{pre_name}.tar.gz"
    current_targets = []
    for name in (".auth", "data", ".pepper", ".jwt_secret"):
        p = HITS_HOME / name
        if p.exists():
            current_targets.append((name, p))
    if current_targets:
        with tarfile.open(str(pre_path), "w:gz") as tar:
            for name, path in current_targets:
                tar.add(str(path), arcname=f"{pre_name}/{name}")
        print(f"   Auto-saved current state → {pre_path.name}")

    # Extract
    tmp = Path(f"/tmp/hits_restore_{os.getpid()}")
    tmp.mkdir(exist_ok=True)
    try:
        with tarfile.open(str(archive), "r:gz") as tar:
            tar.extractall(str(tmp))

        extracted = next(tmp.iterdir())  # backup_YYYYMMDD_HHMMSS/

        # Remove current data and restore
        for name in (".auth", "data"):
            src = extracted / name
            dst = HITS_HOME / name
            if src.exists():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(str(src), str(dst))
                # Fix permissions
                if name == ".auth":
                    dst.chmod(0o700)
                    for f in dst.iterdir():
                        f.chmod(0o600)

        for name in (".pepper", ".jwt_secret"):
            src = extracted / name
            dst = HITS_HOME / name
            if src.exists():
                shutil.copy2(str(src), str(dst))
                dst.chmod(0o600)

        print(f"✅ Restored from {archive.name}")
        print("   Restart the server: hits server")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_backup_list(args):
    """List available backups."""
    if not BACKUP_DIR.exists():
        print("No backups.")
        return

    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), reverse=True)
    if not backups:
        print("No backups.")
        return

    print(f"HITS Backups ({len(backups)})")
    print("-" * 50)
    for i, b in enumerate(backups):
        size = _size_fmt(b.stat().st_size)
        name = b.stem  # backup_20260419_201620
        ts = name.replace("backup_", "").replace("pre_restore_", "[auto] ")
        ts = ts.replace("_", " ")
        marker = " ← latest" if i == 0 else ""
        print(f"  #{i}  {ts}  ({size}){marker}")
    print()
    print("Restore: hits restore          (latest)")
    print("         hits restore -n 1     (#1)")


def main():
    parser = argparse.ArgumentParser(
        prog="hits",
        description="HITS - Hybrid Intel Trace System",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # server (default)
    srv = sub.add_parser("server", help="Start web server (default)")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--dev", action="store_true")

    # backup
    bk = sub.add_parser("backup", help="Backup all HITS data")
    bk.add_argument("--list", action="store_true", help="List backups")

    # restore
    rs = sub.add_parser("restore", help="Restore from backup")
    rs.add_argument("-n", "--number", type=int, default=None, help="Backup number (0=latest)")
    rs.add_argument("--latest", action="store_true", help="Restore latest (default)")

    # status
    sub.add_parser("status", help="Show current data status")

    # resume
    resume_parser = sub.add_parser("resume", help="Resume work - show latest checkpoint")
    resume_parser.add_argument("--project", "-p", type=str, default=None,
                               help="Project path (default: auto-detect from CWD)")
    resume_parser.add_argument("--list", "-l", action="store_true",
                               help="List all projects with checkpoints")
    resume_parser.add_argument("--token-budget", "-t", type=int, default=2000,
                               help="Token budget for output (default: 2000)")

    args = parser.parse_args()

    if args.command is None or args.command == "server":
        cmd_server(args)
    elif args.command == "backup":
        if getattr(args, "list", False):
            cmd_backup_list(args)
        else:
            cmd_backup(args)
    elif args.command == "restore":
        cmd_restore(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "resume":
        cmd_resume(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
