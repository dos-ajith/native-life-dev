from dataclasses import dataclass

from shapely.geometry import MultiPolygon


@dataclass(frozen=True)
class StateRecord:
    lgd_code: str
    name: str
    geom: MultiPolygon


@dataclass(frozen=True)
class DistrictRecord:
    lgd_code: str
    name: str
    geom: MultiPolygon


@dataclass(frozen=True)
class TalukRecord:
    lgd_code: str
    district_lgd_code: str
    name: str
    geom: MultiPolygon


@dataclass(frozen=True)
class VillageRecord:
    state_lgd_code: str
    state_name: str
    district_lgd_code: str
    district_name: str
    taluk_lgd_code: str
    taluk_name: str
    geom: MultiPolygon


@dataclass(frozen=True)
class AdminBoundaries:
    states: list[StateRecord]
    districts: list[DistrictRecord]
    taluks: list[TalukRecord]
