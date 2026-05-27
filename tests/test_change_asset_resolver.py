"""Tests for change-target asset resolution."""

import pytest

from src.utils.change_asset_resolver import (
    extract_asset_from_change_description,
    resolve_change_target_asset,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Rename column company_name to legal_name on public.customers", "public.customers"),
        ("Drop column freight on orders", "public.orders"),
        ("ALTER TABLE public.products ADD COLUMN sku text", "public.products"),
        ("migrate data to warehouse.facts", "warehouse.facts"),
    ],
)
def test_extract_asset_from_change(text, expected):
    assert extract_asset_from_change_description(text) == expected


def test_extract_ignores_rename_to_column_name():
    assert extract_asset_from_change_description("Rename column company_name to legal_name") is None


def test_resolve_prefers_change_text_over_field():
    effective, meta = resolve_change_target_asset(
        "public.orders",
        "Rename column company_name to legal_name on public.customers",
    )
    assert effective == "public.customers"
    assert meta["source"] == "change_text"
    assert "public.orders" in meta["warning"]


def test_resolve_falls_back_to_field():
    effective, meta = resolve_change_target_asset("public.orders", "Rename order_id column")
    assert effective == "public.orders"
    assert meta["source"] == "field"
    assert "warning" not in meta
