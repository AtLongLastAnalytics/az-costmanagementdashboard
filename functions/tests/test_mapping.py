"""Tests for the service-to-category mapping."""

import pytest

from cost_transform.mapping import load_mapping, map_service


@pytest.fixture
def mapping():
    return load_mapping()


def test_known_service_maps_to_category(mapping):
    assert map_service("Microsoft.Compute", mapping) == "Servers"


def test_mapping_is_case_insensitive(mapping):
    assert map_service("microsoft.storage", mapping) == "Storage"


def test_whitespace_is_trimmed(mapping):
    assert map_service("  Microsoft.Sql  ", mapping) == "Databases"


def test_unknown_service_defaults_to_other(mapping):
    assert map_service("Contoso.Widgets", mapping) == "Other"
