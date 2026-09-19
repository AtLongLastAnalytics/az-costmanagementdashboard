"""Blob storage access for the transform function."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class BlobInfo:
    """Metadata about a stored blob."""

    name: str
    last_modified: datetime


class BlobStore(Protocol):  # pragma: no cover
    """Blob operations the transform depends on (mocked in tests)."""

    def list_blobs(self, container: str, prefix: str) -> list[BlobInfo]:
        """List blobs in a container under a name prefix."""
        ...

    def read_blob(self, container: str, name: str) -> bytes:
        """Read a blob's bytes."""
        ...

    def write_blob(self, container: str, name: str, data: bytes) -> None:
        """Write bytes to a blob, overwriting any existing blob."""
        ...

    def read_text(self, container: str, name: str) -> str | None:
        """Read a blob as text, or None if it does not exist."""
        ...

    def write_text(self, container: str, name: str, text: str) -> None:
        """Write text to a blob, overwriting any existing blob."""
        ...


class AzureBlobStore:  # pragma: no cover
    """BlobStore backed by Azure Storage, authenticated via managed identity."""

    def __init__(self, account_url: str) -> None:
        """Create a client for the given storage account URL."""
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        self._client = BlobServiceClient(account_url, credential=DefaultAzureCredential())

    def list_blobs(self, container: str, prefix: str) -> list[BlobInfo]:
        """List blobs in a container under a name prefix."""
        client = self._client.get_container_client(container)
        blobs = client.list_blobs(name_starts_with=prefix)
        return [BlobInfo(b.name, b.last_modified) for b in blobs]

    def read_blob(self, container: str, name: str) -> bytes:
        """Read a blob's bytes."""
        client = self._client.get_blob_client(container, name)
        return client.download_blob().readall()

    def write_blob(self, container: str, name: str, data: bytes) -> None:
        """Write bytes to a blob, overwriting any existing blob."""
        client = self._client.get_blob_client(container, name)
        client.upload_blob(data, overwrite=True)

    def read_text(self, container: str, name: str) -> str | None:
        """Read a blob as text, or None if it does not exist."""
        from azure.core.exceptions import ResourceNotFoundError

        client = self._client.get_blob_client(container, name)
        try:
            return client.download_blob().readall().decode("utf-8")
        except ResourceNotFoundError:
            return None

    def write_text(self, container: str, name: str, text: str) -> None:
        """Write text to a blob, overwriting any existing blob."""
        client = self._client.get_blob_client(container, name)
        client.upload_blob(text.encode("utf-8"), overwrite=True)
