"""Update version-comparison tests."""

from multitapkey.core.updater import (
    compare_versions,
)


def test_compare_versions_basic():
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.1", "1.0.0") == 1
    assert compare_versions("1.0.0", "1.0.1") == -1


def test_compare_versions_major_minor():
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("1.10.0", "1.9.0") == 1


def test_compare_versions_length():
    assert compare_versions("1.0", "1.0.0") == 0
    assert compare_versions("1.0.1", "1.0") == 1


def test_compare_versions_with_prefix():
    assert compare_versions("v1.2.0", "1.1.9") == 1
