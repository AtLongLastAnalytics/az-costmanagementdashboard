"""Load curated cost Parquet into a single DataFrame."""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from cost_transform.storage import BlobStore

_COLUMNS = [
    "date",
    "subscription_id",
    "subscription_name",
    "resource_group",
    "service_name_raw",
    "business_category",
    "cost_actual",
    "cost_amortized",
    "currency",
]


def load_curated(store: BlobStore, container: str, prefix: str) -> pd.DataFrame:
    """Read and concatenate all curated Parquet blobs under a prefix.

    Args:
        store: Blob storage abstraction.
        container: Curated container name.
        prefix: Blob name prefix (e.g. "cost").

    Returns:
        A DataFrame of all curated rows, or an empty typed frame.
    """
    frames = []
    for blob in store.list_blobs(container, prefix):
        if blob.name.endswith(".parquet"):
            frames.append(pd.read_parquet(BytesIO(store.read_blob(container, blob.name))))
    if not frames:
        return pd.DataFrame(columns=_COLUMNS)
    return pd.concat(frames, ignore_index=True)
