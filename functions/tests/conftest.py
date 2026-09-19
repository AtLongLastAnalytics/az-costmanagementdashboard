"""Shared fixtures for the transform tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cost_transform.config import Settings
from cost_transform.mapping import load_mapping
from cost_transform.storage import BlobInfo


class InMemoryBlobStore:
    """In-memory BlobStore used to keep tests hermetic (no Azure calls)."""

    def __init__(self):
        self.blobs = {}
        self.texts = {}

    def add(self, container, name, data, last_modified):
        self.blobs[(container, name)] = (data, last_modified)

    def list_blobs(self, container, prefix):
        return [
            BlobInfo(name, lm)
            for (c, name), (_, lm) in self.blobs.items()
            if c == container and name.startswith(prefix)
        ]

    def read_blob(self, container, name):
        return self.blobs[(container, name)][0]

    def write_blob(self, container, name, data):
        self.blobs[(container, name)] = (data, datetime.now(UTC))

    def read_text(self, container, name):
        return self.texts.get((container, name))

    def write_text(self, container, name, text):
        self.texts[(container, name)] = text


@pytest.fixture
def store():
    return InMemoryBlobStore()


@pytest.fixture
def settings():
    return Settings(storage_account_url="https://example.blob.core.windows.net")


@pytest.fixture
def mapping():
    return load_mapping()


@pytest.fixture
def sample_csv():
    return (
        b"Date,SubscriptionId,SubscriptionName,ResourceGroup,ConsumedService,"
        b"CostInBillingCurrency,BillingCurrencyCode\n"
        b"2026-07-01,sub-1,Prod Sub,rg-prod,Microsoft.Compute,12.50,USD\n"
        b"2026-07-02,sub-1,Prod Sub,rg-prod,Microsoft.Storage,3.20,USD\n"
        b"2026-07-02,sub-1,Prod Sub,rg-data,Microsoft.Sql,8.00,USD\n"
    )
