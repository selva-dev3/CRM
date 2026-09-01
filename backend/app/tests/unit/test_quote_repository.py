from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.schema import Table

from app.models.quote import Quote
from app.repositories.deal_repository import DealRepository
from app.repositories.quote_repository import QuoteRepository
from app.schemas.crm_schemas import QuoteResponse


def result_with(*, first=None, all_rows=None, rowcount=None):
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = first
    scalars.all.return_value = all_rows or []
    result.scalars.return_value = scalars
    result.rowcount = rowcount
    return result


@pytest.mark.asyncio
async def test_get_quote_scoped_sql_contains_organization_predicate():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(first=None)

    result = await QuoteRepository().get_scoped(db, quote_id="quote-1", organization_id="org-1")

    assert result is None
    sql = str(db.execute.await_args_list[-1].args[0])
    assert "quotes.id" in sql
    assert "quotes.organization_id" in sql


@pytest.mark.asyncio
async def test_list_quotes_scoped_sql_contains_organization_predicate():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(all_rows=[])

    await QuoteRepository().list_scoped(
        db,
        organization_id="org-1",
        page=1,
        limit=20,
        status="Draft",
        search="Q-1",
    )

    sql = str(db.execute.await_args_list[-1].args[0])
    assert "quotes.organization_id" in sql
    assert "quotes.status" in sql
    assert "lower(quotes.quote_number)" in sql.lower()


@pytest.mark.asyncio
async def test_list_quotes_by_deal_sql_is_tenant_scoped():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(all_rows=[])

    await QuoteRepository().list_by_deal(db, deal_id="deal-1", organization_id="org-1")

    sql = str(db.execute.await_args_list[-1].args[0])
    assert "quotes.deal_id" in sql
    assert "quotes.organization_id" in sql


@pytest.mark.asyncio
async def test_delete_quote_sql_is_tenant_scoped():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(rowcount=1)

    deleted = await QuoteRepository().delete_scoped(db, quote_id="quote-1", organization_id="org-1")

    assert deleted is True
    sql = str(db.execute.await_args_list[-1].args[0])
    assert sql.startswith("DELETE FROM quotes")
    assert "quotes.id" in sql
    assert "quotes.organization_id" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize("rowcount", [0, 1, 2])
async def test_bulk_delete_quote_sql_is_tenant_scoped(rowcount):
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(rowcount=rowcount)

    affected = await QuoteRepository().bulk_delete_scoped(
        db,
        quote_ids=["quote-1", "foreign-quote"],
        organization_id="org-1",
    )

    assert affected == rowcount
    sql = str(db.execute.await_args_list[-1].args[0])
    assert sql.startswith("DELETE FROM quotes")
    assert "quotes.id IN" in sql
    assert "quotes.organization_id" in sql


@pytest.mark.asyncio
async def test_empty_bulk_delete_does_not_execute_sql():
    db = AsyncMock(spec=AsyncSession)

    affected = await QuoteRepository().bulk_delete_scoped(db, quote_ids=[], organization_id="org-1")

    assert affected == 0
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_deal_lookup_sql_is_tenant_scoped():
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(first=None)

    deal = await DealRepository().get_by_id_scoped(db, deal_id="deal-1", organization_id="org-1")

    assert deal is None
    sql = str(db.execute.await_args_list[-1].args[0])
    assert "deals.id" in sql
    assert "deals.organization_id" in sql


@pytest.mark.asyncio
async def test_legacy_null_deal_quote_can_be_loaded():
    quote = Quote(
        id="legacy-quote",
        organization_id="org-1",
        deal_id=None,
        quote_number="LEGACY-1",
        total_amount=100,
        status="Draft",
    )
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = result_with(first=quote)

    loaded = await QuoteRepository().get_scoped(
        db, quote_id="legacy-quote", organization_id="org-1"
    )

    assert loaded is quote
    assert loaded.deal_id is None


def test_quote_deal_id_model_contract_is_nullable_set_null_and_indexed():
    quote_table = cast(Table, Quote.__table__)
    deal_id = quote_table.c.deal_id

    assert deal_id.nullable is True
    assert {foreign_key.ondelete for foreign_key in deal_id.foreign_keys} == {"SET NULL"}
    assert any(
        [column.name for column in index.columns] == ["deal_id"] for index in quote_table.indexes
    )


def test_quote_response_exposes_nullable_deal_id():
    response = QuoteResponse(
        id="legacy-quote",
        deal_id=None,
        quote_number="LEGACY-1",
        total_amount=100,
        status="Draft",
        created_at="2026-08-01",
    )

    assert response.deal_id is None
