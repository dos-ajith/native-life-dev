import struct
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import shapefile
from pyproj import CRS
from pyproj.exceptions import CRSError

from app.core.exceptions import BusinessRuleError
from app.core.messages import GeographyMessages
from app.schemas.geography import GeographySourceMode


class AdminLevel(StrEnum):
    STATE = "state"
    DISTRICT = "district"
    TALUK = "taluk"


class AdminField(StrEnum):
    STATE_NAME = "state_name"
    STATE_LGD = "state_lgd"
    DISTRICT_NAME = "district_name"
    DISTRICT_LGD = "district_lgd"
    TALUK_NAME = "taluk_name"
    TALUK_LGD = "taluk_lgd"


FIELD_ALIASES: dict[AdminField, tuple[str, ...]] = {
    AdminField.STATE_NAME: ("STATE", "STATE_UT", "STATE_NAME"),
    AdminField.STATE_LGD: ("STATE_LGD", "ST_LGD"),
    AdminField.DISTRICT_NAME: ("DISTRICT", "DIST_NAME", "DISTRICT_NAME"),
    AdminField.DISTRICT_LGD: ("DIST_LGD", "DISTRICT_LGD"),
    AdminField.TALUK_NAME: ("SUB_DIST", "SUBDIST", "SUB_DIST_NAME", "TALUK"),
    AdminField.TALUK_LGD: ("SUBDIS_LGD", "SUBDIST_LGD", "SUB_DIST_LGD", "TALUK_LGD"),
}

VILLAGE_FIELD_ALIASES = ("VILL_LGD", "VILL_NAME", "VILLAGE", "VILLAGE_LGD")
VILLAGE_LEVEL_LABEL = "village"
VILLAGE_SOURCE_REQUIRED_FIELDS = (
    AdminField.STATE_LGD,
    AdminField.STATE_NAME,
    AdminField.DISTRICT_LGD,
    AdminField.DISTRICT_NAME,
    AdminField.TALUK_LGD,
    AdminField.TALUK_NAME,
)

LEGACY_LAYER_NAMES: dict[AdminLevel, str] = {
    AdminLevel.STATE: "KERALA_STATE_BDY",
    AdminLevel.DISTRICT: "KERALA_DISTRICT_BDY",
    AdminLevel.TALUK: "KERALA_SUBDISTRICT_BDY",
}

LEVELS_MOST_SPECIFIC_FIRST = (AdminLevel.TALUK, AdminLevel.DISTRICT, AdminLevel.STATE)

LEVEL_INDICATOR_FIELDS: dict[AdminLevel, tuple[AdminField, ...]] = {
    AdminLevel.TALUK: (AdminField.TALUK_LGD, AdminField.TALUK_NAME),
    AdminLevel.DISTRICT: (AdminField.DISTRICT_LGD, AdminField.DISTRICT_NAME),
    AdminLevel.STATE: (AdminField.STATE_NAME, AdminField.STATE_LGD),
}

LEVEL_REQUIRED_FIELDS: dict[AdminLevel, tuple[AdminField, ...]] = {
    AdminLevel.TALUK: (
        AdminField.STATE_LGD,
        AdminField.DISTRICT_LGD,
        AdminField.TALUK_LGD,
        AdminField.TALUK_NAME,
    ),
    AdminLevel.DISTRICT: (
        AdminField.STATE_LGD,
        AdminField.DISTRICT_LGD,
        AdminField.DISTRICT_NAME,
    ),
    AdminLevel.STATE: (AdminField.STATE_NAME,),
}

LEVEL_CODE_FIELD: dict[AdminLevel, AdminField] = {
    AdminLevel.TALUK: AdminField.TALUK_LGD,
    AdminLevel.DISTRICT: AdminField.DISTRICT_LGD,
    AdminLevel.STATE: AdminField.STATE_LGD,
}

POLYGON_SHAPE_TYPES = frozenset({shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM})
IGNORED_ARCHIVE_DIRECTORY = "__MACOSX"
APPLEDOUBLE_PREFIX = "._"
SHAPEFILE_SUFFIX = ".shp"
PROJECTION_SUFFIX = ".prj"
UNKNOWN_CRS_LABEL = "none"
EMPTY_SAMPLE_LABEL = "none"


@dataclass(frozen=True)
class LayerProfile:
    name: str
    path: Path
    geometry_type: str
    is_polygonal: bool
    record_count: int
    field_names: tuple[str, ...]
    field_map: Mapping[AdminField, str]
    village_fields: tuple[str, ...]
    unique_code_fields: frozenset[AdminField]
    has_prj: bool
    crs: CRS | None
    sample: Mapping[str, str]


@dataclass(frozen=True)
class LayerClassification:
    name: str
    level: AdminLevel | None
    village_source: bool
    reason: str
    summary: str
    profile: LayerProfile | None


def discover_shapefiles(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() == SHAPEFILE_SUFFIX
        and not path.name.startswith(APPLEDOUBLE_PREFIX)
        and IGNORED_ARCHIVE_DIRECTORY not in path.parts
    )


def _resolve_field_map(field_names: tuple[str, ...]) -> dict[AdminField, str]:
    by_upper = {name.upper(): name for name in field_names}
    resolved: dict[AdminField, str] = {}
    for admin_field, aliases in FIELD_ALIASES.items():
        match = next((by_upper[alias] for alias in aliases if alias in by_upper), None)
        if match is not None:
            resolved[admin_field] = match
    return resolved


def _read_crs(shp_path: Path) -> tuple[bool, CRS | None]:
    prj_path = next(
        (
            candidate
            for candidate in shp_path.parent.iterdir()
            if candidate.stem == shp_path.stem and candidate.suffix.lower() == PROJECTION_SUFFIX
        ),
        None,
    )
    if prj_path is None:
        return False, None
    try:
        return True, CRS.from_wkt(prj_path.read_text())
    except (CRSError, UnicodeDecodeError):
        return True, None


def _as_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _unique_code_fields(
    reader: shapefile.Reader, field_map: Mapping[AdminField, str]
) -> frozenset[AdminField]:
    code_fields = {
        admin_field: field_map[admin_field]
        for admin_field in LEVEL_CODE_FIELD.values()
        if admin_field in field_map
    }
    seen: dict[AdminField, set[str]] = {admin_field: set() for admin_field in code_fields}
    valid = set(code_fields)
    for record in reader.iterRecords(fields=list(code_fields.values())):
        values = record.as_dict()
        for admin_field, source_name in code_fields.items():
            code = _as_text(values.get(source_name))
            if not code or code in seen[admin_field]:
                valid.discard(admin_field)
            seen[admin_field].add(code)
    return frozenset(valid)


def inspect_layer(shp_path: Path) -> LayerProfile:
    with shapefile.Reader(str(shp_path)) as reader:
        field_names = tuple(field.name for field in reader.fields[1:])
        field_map = _resolve_field_map(field_names)
        record_count = len(reader)
        sample: dict[str, str] = {}
        if record_count:
            first = reader.record(0).as_dict()
            sample = {name: _as_text(first.get(name)) for name in field_map.values()}
        unique_code_fields = _unique_code_fields(reader, field_map)
        geometry_type = reader.shapeTypeName
        is_polygonal = reader.shapeType in POLYGON_SHAPE_TYPES

    upper_names = {name.upper() for name in field_names}
    has_prj, crs = _read_crs(shp_path)
    return LayerProfile(
        name=shp_path.stem,
        path=shp_path,
        geometry_type=geometry_type,
        is_polygonal=is_polygonal,
        record_count=record_count,
        field_names=field_names,
        field_map=field_map,
        village_fields=tuple(alias for alias in VILLAGE_FIELD_ALIASES if alias in upper_names),
        unique_code_fields=unique_code_fields,
        has_prj=has_prj,
        crs=crs,
        sample=sample,
    )


def _indicated_level(profile: LayerProfile) -> AdminLevel | None:
    for level in LEVELS_MOST_SPECIFIC_FIRST:
        if any(admin_field in profile.field_map for admin_field in LEVEL_INDICATOR_FIELDS[level]):
            return level
    return None


def _legacy_level(layer_name: str) -> AdminLevel | None:
    upper_name = layer_name.upper()
    return next(
        (level for level, legacy in LEGACY_LAYER_NAMES.items() if legacy == upper_name), None
    )


def _classify_village_profile(profile: LayerProfile) -> tuple[bool, str]:
    fields = ", ".join(profile.village_fields)
    missing = [
        admin_field.value
        for admin_field in VILLAGE_SOURCE_REQUIRED_FIELDS
        if admin_field not in profile.field_map
    ]
    if missing:
        return False, GeographyMessages.LAYER_REASON_VILLAGE_INCOMPLETE.format(
            fields=fields, missing=", ".join(missing)
        )

    named_level = _legacy_level(profile.name)
    if named_level is not None:
        return False, GeographyMessages.LAYER_REASON_NAME_CONFLICT.format(
            named_level=named_level.value, level=VILLAGE_LEVEL_LABEL
        )

    return True, GeographyMessages.LAYER_REASON_VILLAGE_SOURCE.format(fields=fields)


def _classify_admin_profile(profile: LayerProfile) -> tuple[AdminLevel | None, str]:
    level = _indicated_level(profile)
    if level is None:
        return None, GeographyMessages.LAYER_REASON_NO_ADMIN_FIELDS

    missing = [
        admin_field.value
        for admin_field in LEVEL_REQUIRED_FIELDS[level]
        if admin_field not in profile.field_map
    ]
    if missing:
        return None, GeographyMessages.LAYER_REASON_INCOMPLETE_FIELDS.format(
            level=level.value, fields=", ".join(missing)
        )

    code_field = LEVEL_CODE_FIELD[level]
    if code_field in profile.field_map and code_field not in profile.unique_code_fields:
        return None, GeographyMessages.LAYER_REASON_CODES_NOT_UNIQUE.format(
            field=profile.field_map[code_field], level=level.value
        )

    named_level = _legacy_level(profile.name)
    if named_level is not None and named_level != level:
        return None, GeographyMessages.LAYER_REASON_NAME_CONFLICT.format(
            named_level=named_level.value, level=level.value
        )

    return level, GeographyMessages.LAYER_REASON_CANDIDATE.format(level=level.value)


def _classify_profile(profile: LayerProfile) -> tuple[AdminLevel | None, bool, str]:
    if not profile.is_polygonal:
        return (
            None,
            False,
            GeographyMessages.LAYER_REASON_NOT_POLYGON.format(geometry=profile.geometry_type),
        )
    if profile.record_count == 0:
        return None, False, GeographyMessages.LAYER_REASON_EMPTY
    if profile.village_fields:
        village_source, reason = _classify_village_profile(profile)
        return None, village_source, reason
    level, reason = _classify_admin_profile(profile)
    return level, False, reason


def _summarize(profile: LayerProfile, reason: str) -> str:
    sample = ", ".join(f"{name}={value}" for name, value in profile.sample.items())
    return GeographyMessages.LAYER_SUMMARY.format(
        name=profile.name,
        geometry=profile.geometry_type,
        count=profile.record_count,
        crs=profile.crs.name if profile.crs is not None else UNKNOWN_CRS_LABEL,
        fields=", ".join(profile.field_names),
        sample=sample or EMPTY_SAMPLE_LABEL,
        reason=reason,
    )


def classify_layer(shp_path: Path) -> LayerClassification:
    try:
        profile = inspect_layer(shp_path)
    except (shapefile.ShapefileException, struct.error, ValueError, OSError):
        reason = GeographyMessages.LAYER_REASON_UNREADABLE
        summary = GeographyMessages.LAYER_SUMMARY_UNREADABLE.format(
            name=shp_path.stem, reason=reason
        )
        return LayerClassification(
            name=shp_path.stem,
            level=None,
            village_source=False,
            reason=reason,
            summary=summary,
            profile=None,
        )

    level, village_source, reason = _classify_profile(profile)
    return LayerClassification(
        name=profile.name,
        level=level,
        village_source=village_source,
        reason=reason,
        summary=_summarize(profile, reason),
        profile=profile,
    )


def _select_level(
    level: AdminLevel, classifications: list[LayerClassification]
) -> LayerProfile | None:
    candidates = [
        item.profile
        for item in classifications
        if item.level == level and item.profile is not None
    ]
    if len(candidates) > 1:
        legacy_matches = [
            candidate for candidate in candidates if _legacy_level(candidate.name) == level
        ]
        if len(legacy_matches) != 1:
            raise BusinessRuleError(
                GeographyMessages.AMBIGUOUS_LAYER.format(
                    level=level.value,
                    layers=", ".join(candidate.name for candidate in candidates),
                )
            )
        return legacy_matches[0]
    return candidates[0] if candidates else None


def _select_village_layer(classifications: list[LayerClassification]) -> LayerProfile | None:
    candidates = [
        item.profile for item in classifications if item.village_source and item.profile
    ]
    if len(candidates) > 1:
        raise BusinessRuleError(
            GeographyMessages.AMBIGUOUS_LAYER.format(
                level=VILLAGE_LEVEL_LABEL,
                layers=", ".join(candidate.name for candidate in candidates),
            )
        )
    return candidates[0] if candidates else None


@dataclass(frozen=True)
class DetectedSource:
    mode: GeographySourceMode
    admin_layers: Mapping[AdminLevel, LayerProfile]
    village_layer: LayerProfile | None


def select_source(classifications: list[LayerClassification]) -> DetectedSource:
    if not classifications:
        raise BusinessRuleError(GeographyMessages.NO_SHAPEFILES)

    admin_layers = {
        level: profile
        for level in AdminLevel
        if (profile := _select_level(level, classifications)) is not None
    }
    if len(admin_layers) == len(AdminLevel):
        return DetectedSource(
            mode=GeographySourceMode.DIRECT_ADMIN_BOUNDARY,
            admin_layers=admin_layers,
            village_layer=None,
        )

    village_layer = _select_village_layer(classifications)
    if village_layer is not None:
        return DetectedSource(
            mode=GeographySourceMode.DERIVED_FROM_VILLAGE_BOUNDARY,
            admin_layers={},
            village_layer=village_layer,
        )

    raise BusinessRuleError(
        GeographyMessages.LAYERS_NOT_IDENTIFIED.format(
            levels=", ".join(level.value for level in AdminLevel if level not in admin_layers),
            report="; ".join(item.summary for item in classifications),
        )
    )


def detect_source(root: Path) -> DetectedSource:
    return select_source([classify_layer(path) for path in discover_shapefiles(root)])
