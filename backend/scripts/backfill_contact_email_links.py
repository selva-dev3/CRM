"""Safely backfill unambiguous legacy Email.contact_id relationships in batches."""

import argparse
import asyncio

from app.db.session import AsyncSessionLocal, engine
from sqlalchemy import text

BACKFILL_BATCH = text(
    """
    WITH unique_matches AS (
        SELECT e.id AS email_id, min(c.id) AS contact_id
        FROM emails AS e
        JOIN contacts AS c
          ON c.organization_id = e.organization_id
         AND lower(btrim(c.email)) = lower(btrim(e.to_email))
        WHERE e.contact_id IS NULL
        GROUP BY e.id
        HAVING count(*) = 1
        ORDER BY e.id
        LIMIT :batch_size
    )
    UPDATE emails AS e
       SET contact_id = unique_matches.contact_id
      FROM unique_matches
     WHERE e.id = unique_matches.email_id
       AND e.contact_id IS NULL
    RETURNING e.id
    """
)


async def backfill(*, batch_size: int, max_batches: int | None, dry_run: bool) -> int:
    total = 0
    batch_number = 0
    try:
        while max_batches is None or batch_number < max_batches:
            async with AsyncSessionLocal() as db:
                if dry_run:
                    count = int(
                        await db.scalar(
                            text(
                                """
                                SELECT count(*)
                                FROM (
                                    SELECT e.id
                                    FROM emails AS e
                                    JOIN contacts AS c
                                      ON c.organization_id = e.organization_id
                                     AND lower(btrim(c.email)) = lower(btrim(e.to_email))
                                    WHERE e.contact_id IS NULL
                                    GROUP BY e.id
                                    HAVING count(*) = 1
                                ) AS candidates
                                """
                            )
                        )
                        or 0
                    )
                    print(f"Unambiguous legacy email links available: {count}")  # noqa: T201
                    return count

                result = await db.execute(BACKFILL_BATCH, {"batch_size": batch_size})
                updated = len(result.fetchall())
                await db.commit()
            batch_number += 1
            total += updated
            print(  # noqa: T201
                f"Batch {batch_number}: linked {updated} emails; total={total}"
            )
            if updated < batch_size:
                break
        return total
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 10_000:
        parser.error("--batch-size must be between 1 and 10000")
    if args.max_batches is not None and args.max_batches < 1:
        parser.error("--max-batches must be positive")
    asyncio.run(
        backfill(
            batch_size=args.batch_size,
            max_batches=args.max_batches,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
