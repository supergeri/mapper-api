#!/usr/bin/env python3
"""
Backfill execution_log for existing workout completions (AMA-290).

This script populates the execution_log column for completions that have
set_logs but no execution_log, converting the legacy format to the new
unified execution_log format.

Usage:
    python scripts/backfill_execution_log.py [--dry-run] [--limit N]

Options:
    --dry-run    Preview changes without updating database
    --limit N    Process only N records (for testing)
"""
import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from backend.workout_completions import merge_set_logs_to_execution_log


def get_supabase_client():
    """Create Supabase client with service role key."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)

    return create_client(url, key)


def backfill_execution_log(dry_run: bool = False, limit: int = None):
    """
    Backfill execution_log for completions with set_logs.

    Args:
        dry_run: If True, preview changes without updating
        limit: Maximum number of records to process
    """
    supabase = get_supabase_client()

    # Find completions with set_logs but no execution_log
    query = supabase.table("workout_completions") \
        .select("id, set_logs, workout_structure") \
        .not_.is_("set_logs", "null") \
        .is_("execution_log", "null")

    if limit:
        query = query.limit(limit)

    result = query.execute()

    if not result.data:
        print("No completions found that need backfilling")
        return

    print(f"Found {len(result.data)} completions to backfill")

    updated_count = 0
    error_count = 0

    for record in result.data:
        completion_id = record["id"]
        set_logs = record["set_logs"]
        workout_structure = record.get("workout_structure")

        try:
            # Merge set_logs into execution_log format
            execution_log = merge_set_logs_to_execution_log(
                workout_structure,
                set_logs
            )

            if execution_log:
                if dry_run:
                    print(f"  [DRY RUN] Would update {completion_id}")
                    print(f"    set_logs entries: {len(set_logs)}")
                    print(f"    execution_log intervals: {len(execution_log.get('intervals', []))}")
                else:
                    # Update the record
                    update_result = supabase.table("workout_completions") \
                        .update({"execution_log": execution_log}) \
                        .eq("id", completion_id) \
                        .execute()

                    if update_result.data:
                        print(f"  Updated {completion_id}")
                        updated_count += 1
                    else:
                        print(f"  WARNING: Update returned empty for {completion_id}")
                        error_count += 1
            else:
                print(f"  Skipped {completion_id}: merge returned None")

        except Exception as e:
            print(f"  ERROR processing {completion_id}: {e}")
            error_count += 1

    print()
    print("=" * 50)
    print(f"Backfill complete:")
    print(f"  Total processed: {len(result.data)}")
    if dry_run:
        print(f"  Would update: {len(result.data) - error_count}")
    else:
        print(f"  Updated: {updated_count}")
    print(f"  Errors: {error_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill execution_log for workout completions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only N records"
    )

    args = parser.parse_args()

    print("AMA-290: Backfill execution_log for workout completions")
    print("=" * 50)

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")

    backfill_execution_log(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
