import operator
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.core.messages import PluginMessages

_SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_BOUND_PATTERN = re.compile(
    r"^(>=|<=|==|>|<)\s*(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:\.(0|[1-9]\d*))?$"
)
_COMPARATORS: dict[str, Callable[["Version", "Version"], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    ">": operator.gt,
    "<": operator.lt,
}


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = _SEMVER_PATTERN.match(value)
        if match is None:
            raise ValueError(PluginMessages.INVALID_VERSION.format(value=value))
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class VersionBound:
    comparator: str
    version: Version

    def allows(self, version: Version) -> bool:
        return _COMPARATORS[self.comparator](version, self.version)


@dataclass(frozen=True)
class VersionRange:
    bounds: tuple[VersionBound, ...]
    text: str

    @classmethod
    def parse(cls, value: str) -> "VersionRange":
        clauses = [clause.strip() for clause in value.split(",")]
        bounds = tuple(_parse_bound(clause, value) for clause in clauses)
        return cls(bounds=bounds, text=value)

    def allows(self, version: Version) -> bool:
        return all(bound.allows(version) for bound in self.bounds)

    def __str__(self) -> str:
        return self.text


def _parse_bound(clause: str, original: str) -> VersionBound:
    match = _BOUND_PATTERN.match(clause)
    if match is None:
        raise ValueError(PluginMessages.INVALID_VERSION_RANGE.format(value=original))
    comparator, *parts = match.groups()
    numbers = [int(part) if part is not None else 0 for part in parts]
    return VersionBound(comparator=comparator, version=Version(*numbers))


CORE_API_VERSION = Version(1, 6, 0)
