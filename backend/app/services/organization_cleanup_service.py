"""Durable cleanup: a broker outage cannot lose the committed file manifest."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
from app.services.organization_lifecycle_service import storage_key
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)


async def cleanup_organization_files(db: AsyncSession, *, limit: int = 50) -> int:
    repository = OrganizationLifecycleRepository()
    completed = 0
    items = []
    try:
        for _ in range(limit):
            item = await repository.claim_file(db)
            if item is None:
                break
            items.append(item)
            await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    candidate_keys = {item.object_key for item in items}
    retained_keys: set[str] | None = None
    for item in items:
        try:
            error = None
            if item.endpoint != settings.AWS_ENDPOINT_URL or item.bucket != settings.AWS_S3_BUCKET:
                error = "STORAGE_CONFIGURATION_CHANGED"
            elif storage_key(item.object_key, "key") != item.object_key:
                error = "INVALID_STORAGE_KEY"
            else:
                # Recheck retained references because cleanup can run after retries
                # or an operator's recovery action, well after database deletion.
                operation = await repository.get_deletion(db, item.operation_id)
                if operation is None:
                    error = "DELETION_OPERATION_MISSING"
                else:
                    if retained_keys is None:
                        retained_keys = set()
                        async for _, value, kind in repository.storage_references(
                            db, operation.organization_id
                        ):
                            key = storage_key(value, kind)
                            if key is not None and key in candidate_keys:
                                retained_keys.add(key)
                    if item.object_key in retained_keys:
                        error = "STORAGE_OBJECT_REFERENCED"
            # A slow earlier object must not let this worker act on a lease
            # already claimed by another worker after expiration.
            if not await repository.renew_file_claim(db, item):
                await db.rollback()
                continue
            await db.commit()
            if not error:
                try:
                    if not await asyncio.to_thread(s3_service.delete_file, item.object_key):
                        error = "STORAGE_DELETE_FAILED"
                except Exception:
                    error = "STORAGE_DELETE_FAILED"
            await repository.finish_file(db, item, error)
            await db.commit()
            if error:
                logger.warning(
                    "Organization file cleanup failed cleanup_id=%s code=%s", item.id, error
                )
            else:
                completed += 1
        except Exception:
            await db.rollback()
            raise
    return completed
