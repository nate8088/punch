#!/usr/bin/env python3
"""
import_harvest.py — Import time entries from Harvest CSV export into Punch.

Usage:
  docker compose exec app python scripts/import_harvest.py /path/to/harvest_time.csv

Harvest CSV export:
  In Harvest: Reports → Time → Detailed → Export (CSV)
  The CSV should have columns including:
    Date, Client, Project, Task, Notes, Hours, Billable

Run this from inside the Docker container, or with PYTHONPATH set to the app root.
"""

import sys
import csv
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add app root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import Client, TimeEntry
import math


def round_to_15(minutes):
    return math.ceil(minutes / 15) * 15


def parse_harvest_csv(filepath):
    """Parse a Harvest detailed time report CSV."""
    entries = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(row)
    return entries


def find_or_prompt_client(session, client_name, client_map):
    """Look up a Punch client by Harvest client name, prompting user if ambiguous."""
    if client_name in client_map:
        return client_map[client_name]

    clients = Client.query.filter(Client.name.ilike(f"%{client_name}%")).all()

    if not clients:
        print(f"\n  No client found matching '{client_name}'.")
        print("  Available clients:")
        all_clients = Client.query.order_by(Client.name).all()
        for i, c in enumerate(all_clients):
            print(f"    [{i}] {c.name}")
        print("    [s] Skip this client")
        choice = input("  Select: ").strip()
        if choice == "s":
            client_map[client_name] = None
            return None
        try:
            selected = all_clients[int(choice)]
            client_map[client_name] = selected
            return selected
        except (ValueError, IndexError):
            print("  Invalid choice, skipping.")
            client_map[client_name] = None
            return None

    if len(clients) == 1:
        print(f"  Matched '{client_name}' → '{clients[0].name}'")
        client_map[client_name] = clients[0]
        return clients[0]

    print(f"\n  Multiple matches for '{client_name}':")
    for i, c in enumerate(clients):
        print(f"    [{i}] {c.name}")
    choice = input("  Select: ").strip()
    try:
        selected = clients[int(choice)]
        client_map[client_name] = selected
        return selected
    except (ValueError, IndexError):
        client_map[client_name] = None
        return None


def import_harvest(filepath):
    app = create_app()

    with app.app_context():
        print(f"\nPunch — Harvest Import")
        print(f"File: {filepath}")
        print("-" * 50)

        rows = parse_harvest_csv(filepath)
        print(f"Found {len(rows)} rows in CSV.")

        client_map = {}
        imported = 0
        skipped = 0
        already_exists = 0

        for row in rows:
            # Harvest column names vary slightly by export version — normalize
            harvest_client = (
                row.get("Client") or row.get("client") or ""
            ).strip()
            date_str = (
                row.get("Date") or row.get("date") or ""
            ).strip()
            hours_str = (
                row.get("Hours") or row.get("hours") or "0"
            ).strip()
            notes = (
                row.get("Notes") or row.get("notes") or ""
            ).strip()
            billable_str = (
                row.get("Billable") or row.get("billable") or "yes"
            ).strip().lower()
            external_id = (
                row.get("ID") or row.get("id") or ""
            ).strip()

            if not harvest_client or not date_str:
                skipped += 1
                continue

            # Check for duplicate import
            if external_id:
                existing = TimeEntry.query.filter_by(
                    imported_from="harvest",
                    external_id=external_id,
                ).first()
                if existing:
                    already_exists += 1
                    continue

            client = find_or_prompt_client(db.session, harvest_client, client_map)
            if client is None:
                skipped += 1
                continue

            try:
                hours = float(hours_str)
            except ValueError:
                hours = 0

            minutes = round_to_15(hours * 60)

            try:
                started_at = datetime.strptime(date_str, "%Y-%m-%d").replace(
                    hour=9, minute=0, tzinfo=timezone.utc
                )
            except ValueError:
                try:
                    started_at = datetime.strptime(date_str, "%m/%d/%Y").replace(
                        hour=9, minute=0, tzinfo=timezone.utc
                    )
                except ValueError:
                    print(f"  Could not parse date: {date_str}, skipping.")
                    skipped += 1
                    continue

            ended_at = started_at + timedelta(minutes=minutes)

            entry = TimeEntry(
                client_id=client.id,
                started_at=started_at,
                ended_at=ended_at,
                duration_minutes=minutes,
                description=notes,
                is_billable=(billable_str in ("yes", "true", "1")),
                imported_from="harvest",
                external_id=external_id or None,
            )
            db.session.add(entry)
            imported += 1

            if imported % 50 == 0:
                db.session.commit()
                print(f"  ...{imported} entries imported so far")

        db.session.commit()

        print("\n" + "=" * 50)
        print(f"  Imported:      {imported}")
        print(f"  Already exist: {already_exists}")
        print(f"  Skipped:       {skipped}")
        print("=" * 50)
        print("\nDone. Check Punch to verify your data.\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_harvest.py <path-to-harvest-export.csv>")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    import_harvest(filepath)