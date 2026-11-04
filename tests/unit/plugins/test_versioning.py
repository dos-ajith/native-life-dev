import pytest

from app.plugins.versioning import Version, VersionRange


def test_versions_compare_numerically() -> None:
    assert Version.parse("1.10.0") > Version.parse("1.9.9")
    assert str(Version.parse("2.0.1")) == "2.0.1"


@pytest.mark.parametrize("value", ["1.0", "01.0.0", "1.0.0-beta", "v1.0.0", "", "1.0.0.0"])
def test_invalid_versions_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        Version.parse(value)


def test_range_allows_versions_within_bounds() -> None:
    supported = VersionRange.parse(">=1.0,<2.0")
    assert supported.allows(Version(1, 0, 0))
    assert supported.allows(Version(1, 99, 3))
    assert not supported.allows(Version(2, 0, 0))
    assert not supported.allows(Version(0, 9, 9))


def test_exact_range() -> None:
    assert VersionRange.parse("==1.2.3").allows(Version(1, 2, 3))
    assert not VersionRange.parse("==1.2.3").allows(Version(1, 2, 4))


@pytest.mark.parametrize("value", ["", "1.0", "~=1.0", ">=1.0,", ">= x", "=>1.0"])
def test_invalid_ranges_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        VersionRange.parse(value)
