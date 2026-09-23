from collections import Counter, defaultdict
from collections.abc import Callable, Iterable

import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from app.core.exceptions import BusinessRuleError
from app.core.messages import GeographyMessages
from app.services.geography_layer_detector import AdminLevel
from app.services.geography_records import (
    AdminBoundaries,
    DistrictRecord,
    StateRecord,
    TalukRecord,
    VillageRecord,
)


def _single_parent_by_code(
    villages: list[VillageRecord],
    code_of: Callable[[VillageRecord], str],
    parent_of: Callable[[VillageRecord], str],
    level: AdminLevel,
    parent_level: AdminLevel,
) -> dict[str, str]:
    parents: dict[str, set[str]] = defaultdict(set)
    for village in villages:
        parents[code_of(village)].add(parent_of(village))

    for code, codes in sorted(parents.items()):
        if len(codes) > 1:
            raise BusinessRuleError(
                GeographyMessages.AMBIGUOUS_PARENT_CODE.format(
                    level=level.value,
                    code=code,
                    parent_level=parent_level.value,
                    parents=", ".join(sorted(codes)),
                )
            )
    return {code: next(iter(codes)) for code, codes in parents.items()}


def _majority_name_by_code(
    villages: list[VillageRecord],
    code_of: Callable[[VillageRecord], str],
    name_of: Callable[[VillageRecord], str],
    level: AdminLevel,
) -> dict[str, str]:
    names: dict[str, Counter[str]] = defaultdict(Counter)
    for village in villages:
        names[code_of(village)][name_of(village)] += 1

    resolved: dict[str, str] = {}
    for code, counts in names.items():
        ranked = counts.most_common(2)
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            raise BusinessRuleError(
                GeographyMessages.AMBIGUOUS_NAME.format(
                    level=level.value, code=code, names=", ".join(sorted(counts))
                )
            )
        resolved[code] = ranked[0][0]
    return resolved


def _polygons(geometry: BaseGeometry) -> list[Polygon]:
    return [
        polygon
        for part in shapely.get_parts(geometry)
        for polygon in shapely.get_parts(part)
        if isinstance(polygon, Polygon) and not polygon.is_empty
    ]


def _dissolve(geometries: Iterable[BaseGeometry], level: AdminLevel, code: str) -> MultiPolygon:
    merged = shapely.union_all(list(geometries))
    if not merged.is_valid:
        merged = shapely.make_valid(merged)
    dissolved = MultiPolygon(_polygons(merged))
    if dissolved.is_empty or not dissolved.is_valid or dissolved.has_z:
        raise BusinessRuleError(
            GeographyMessages.INVALID_DERIVED_GEOMETRY.format(level=level.value, code=code)
        )
    return dissolved


def _dissolve_by_code(
    items: Iterable[tuple[str, BaseGeometry]], level: AdminLevel
) -> dict[str, MultiPolygon]:
    grouped: dict[str, list[BaseGeometry]] = defaultdict(list)
    for code, geometry in items:
        grouped[code].append(geometry)
    return {code: _dissolve(geometries, level, code) for code, geometries in grouped.items()}


def derive_admin_boundaries(villages: list[VillageRecord]) -> AdminBoundaries:
    district_by_taluk = _single_parent_by_code(
        villages,
        lambda village: village.taluk_lgd_code,
        lambda village: village.district_lgd_code,
        AdminLevel.TALUK,
        AdminLevel.DISTRICT,
    )
    state_by_district = _single_parent_by_code(
        villages,
        lambda village: village.district_lgd_code,
        lambda village: village.state_lgd_code,
        AdminLevel.DISTRICT,
        AdminLevel.STATE,
    )
    taluk_names = _majority_name_by_code(
        villages, lambda village: village.taluk_lgd_code, lambda village: village.taluk_name,
        AdminLevel.TALUK,
    )
    district_names = _majority_name_by_code(
        villages,
        lambda village: village.district_lgd_code,
        lambda village: village.district_name,
        AdminLevel.DISTRICT,
    )
    state_names = _majority_name_by_code(
        villages, lambda village: village.state_lgd_code, lambda village: village.state_name,
        AdminLevel.STATE,
    )

    taluk_geoms = _dissolve_by_code(
        ((village.taluk_lgd_code, village.geom) for village in villages), AdminLevel.TALUK
    )
    district_geoms = _dissolve_by_code(
        ((district_by_taluk[code], geom) for code, geom in taluk_geoms.items()),
        AdminLevel.DISTRICT,
    )
    state_geoms = _dissolve_by_code(
        ((state_by_district[code], geom) for code, geom in district_geoms.items()),
        AdminLevel.STATE,
    )

    return AdminBoundaries(
        states=[
            StateRecord(lgd_code=code, name=state_names[code], geom=geom)
            for code, geom in sorted(state_geoms.items())
        ],
        districts=[
            DistrictRecord(lgd_code=code, name=district_names[code], geom=geom)
            for code, geom in sorted(district_geoms.items())
        ],
        taluks=[
            TalukRecord(
                lgd_code=code,
                district_lgd_code=district_by_taluk[code],
                name=taluk_names[code],
                geom=geom,
            )
            for code, geom in sorted(taluk_geoms.items())
        ],
    )
