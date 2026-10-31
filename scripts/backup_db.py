#!/usr/bin/env python3
"""RekaRasa.ai — SQLite backup and disk usage report.

Run this script periodically (cron, Render cron job, or manually) to export
a timestamped copy of the production database. The backup uses SQLite's
online backup API (sqlite3.backup), which does not block writers.

Usage:
    python scripts/backup_db.py [--output /path/to/backups] [--keep 7]

    --output   Directory to store backup files (default: ./backups)
    --keep     Number of recent backups to keep; older ones are deleted (default: 7)

The script also prints a disk usage summary so it can serve as a monitoring
probe alongside the /api/disk-usage endpoint.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def backup_database(source: Path, dest: Path) -> int:
    """Copy the source database to dest using SQLite's online backup API.

    Returns the size of the backup file in bytes.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    source_conn = sqlite3.connect(str(source))
    dest_conn = sqlite3.connect(str(dest))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()
    return dest.stat().st_size


def cleanup_old_backups(backup_dir: Path, keep: int) -> list[str]:
    """Delete backups older than the keep count, returning deleted filenames."""
    backups = sorted(backup_dir.glob("rekarasa_*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    deleted = []
    for old in backups[keep:]:
        old.unlink()
        deleted.append(old.name)
    return deleted


def disk_usage_report(data_path: Path, images_path: Path) -> dict:
    """Report the disk usage of the database and generated images."""
    report = {"database_bytes": 0, "images_bytes": 0, "total_bytes": 0, "image_count": 0}
    if data_path.is_file():
        report["database_bytes"] = data_path.stat().st_size
    if images_path.is_dir():
        total = 0
        count = 0
        for f in images_path.iterdir():
            if f.is_file():
                total += f.stat().st_size
                count += 1
        report["images_bytes"] = total
        report["image_count"] = count
    report["total_bytes"] = report["database_bytes"] + report["images_bytes"]
    report["total_mb"] = round(report["total_bytes"] / (1024 * 1024), 1)
    return report


def main():
    parser = argparse.ArgumentParser(description="Backup RekaRasa.ai SQLite database")
    parser.add_argument("--output", default="./backups", help="Backup output directory")
    parser.add_argument("--keep", type=int, default=7, help="Number of recent backups to keep")
    parser.add_argument("--db", default=None, help="Database path (overrides DATABASE_PATH env)")
    args = parser.parse_args()

    db_path = Path(args.db or os.getenv("DATABASE_PATH", "./data/rekarasa.sqlite3"))
    if not db_path.is_file():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    images_path = db_path.parent / "generated-images"
    backup_dir = Path(args.output)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"rekarasa_{timestamp}.sqlite3"

    # Disk usage report
    usage = disk_usage_report(db_path, images_path)
    print(f"Disk usage: database={usage['database_bytes']:,}B, "
          f"images={usage['images_bytes']:,}B ({usage['image_count']} files), "
          f"total={usage['total_mb']}MB")

    if usage["total_bytes"] > 0.8 * 1_073_741_824:
        print("WARNING: Disk usage exceeds 80% of 1GB threshold!", file=sys.stderr)

    # Backup
    size = backup_database(db_path, backup_file)
    print(f"Backup created: {backup_file} ({size:,} bytes)")

    # Cleanup
    deleted = cleanup_old_backups(backup_dir, args.keep)
    if deleted:
        print(f"Cleaned up {len(deleted)} old backup(s): {', '.join(deleted)}")


if __name__ == "__main__":
    main()
