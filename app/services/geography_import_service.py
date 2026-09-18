import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import shapefile
import shapely
from fastapi import UploadFile
from geoalchemy2.shape import from_shape
from pyproj import CRS, Transformer
from shapely.geometry import MultiPolygon
from shapely.geometry import shape as shapely_shape
from shapely.ops import transform as shapely_transform
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import GeographyMessages
from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.schemas.geography import GeographyImportSummary

TARGET_SRID = 4326
KERALA_STATE_LGD = "32"

STATE_LAYER_NAME = "KERALA_STATE_BDY"
DISTRICT_LAYER_NAME = "KERALA_DISTRICT_BDY"
TALUK_LAYER_NAME = "KERALA_SUBDISTRICT_BDY"
REQUIRED_LAYER_NAMES = (STATE_LAYER_NAME, DISTRICT_LAYER_NAME, TALUK_LAYER_NAME)

STATE_REQUIRED_FIELDS = ("STATE",)
DISTRICT_REQUIRED_FIELDS = ("STATE_LGD", "DISTRICT", "DIST_LGD")
TALUK_REQUIRED_FIELDS = ("STATE_LGD", "DISTRICT", "DIST_LGD", "SUB_DIST", "SUBDIS_LGD")

UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_UNCOMPRESSED_SIZE_MULTIPLIER = 20


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


def _validate_filename(filename: str | None) -> None:
    if filename is None or not filename.lower().endswith(".zip"):
        raise BusinessRuleError(GeographyMessages.INVALID_FILE_TYPE)


def _save_upload(upload: UploadFile, destination: Path, max_bytes: int) -> None:
    total_bytes = 0
    with destination.open("wb") as out_file:
        while chunk := upload.file.read(UPLOAD_CHUNK_BYTES):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise BusinessRuleError(GeographyMessages.FILE_TOO_LARGE)
            out_file.write(chunk)

    if not zipfile.is_zipfile(destination):
        raise BusinessRuleError(GeographyMessages.INVALID_ZIP)


def _is_within_directory(candidate: Path, directory: Path) -> bool:
    try:
        candidate.relative_to(directory)
    except ValueError:
        return False
    return True


def _extract_zip_safely(zip_path: Path, destination: Path, max_uncompressed_bytes: int) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        total_uncompressed = sum(member.file_size for member in archive.infolist())
        if total_uncompressed > max_uncompressed_bytes:
            raise BusinessRuleError(GeographyMessages.ZIP_TOO_LARGE_UNCOMPRESSED)

        for member in archive.infolist():
            member_name = member.filename.replace("\\", "/")
            if member_name.startswith("/") or ":" in member_name:
                raise BusinessRuleError(GeographyMessages.UNSAFE_ZIP_ENTRY)
            if stat.S_ISLNK((member.external_attr >> 16) & 0xFFFF):
                raise BusinessRuleError(GeographyMessages.UNSAFE_ZIP_ENTRY)

            target_path = (destination / member_name).resolve()
            if not _is_within_directory(target_path, destination_resolved):
                raise BusinessRuleError(GeographyMessages.UNSAFE_ZIP_ENTRY)

            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def _locate_layer_paths(extract_root: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for shp_path in extract_root.rglob("*.shp"):
        layer_name = shp_path.stem.upper()
        if layer_name in REQUIRED_LAYER_NAMES and layer_name not in found:
            found[layer_name] = shp_path

    missing = [name for name in REQUIRED_LAYER_NAMES if name not in found]
    if missing:
        raise BusinessRuleError(GeographyMessages.MISSING_LAYER.format(layer=", ".join(missing)))
    return found


def _build_transformer(shp_path: Path, layer_name: str) -> Transformer:
    prj_path = shp_path.with_suffix(".prj")
    if not prj_path.exists():
        raise BusinessRuleError(GeographyMessages.MISSING_PRJ.format(layer=layer_name))
    source_crs = CRS.from_wkt(prj_path.read_text())
    return Transformer.from_crs(source_crs, f"EPSG:{TARGET_SRID}", always_xy=True)


def _require_fields_present(
    field_names: set[str], required: tuple[str, ...], layer_name: str
) -> None:
    for field in required:
        if field not in field_names:
            raise BusinessRuleError(
                GeographyMessages.MISSING_FIELD.format(field=field, layer=layer_name)
            )


def _require_non_blank(value: object, field: str, layer_name: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise BusinessRuleError(
            GeographyMessages.NULL_REQUIRED_VALUE.format(field=field, layer=layer_name)
        )
    return text


def _require_state_lgd(value: str, layer_name: str) -> None:
    if value != KERALA_STATE_LGD:
        raise BusinessRuleError(
            GeographyMessages.INVALID_STATE_LGD.format(expected=KERALA_STATE_LGD, actual=value)
        )


def _to_wgs84_multipolygon(
    raw_geometry: dict[str, object], transformer: Transformer, layer_name: str, identifier: str
) -> MultiPolygon:
    geometry = shapely_shape(raw_geometry)
    geometry_2d = shapely.force_2d(geometry)
    geometry_wgs84 = shapely_transform(transformer.transform, geometry_2d)

    if not geometry_wgs84.is_valid:
        geometry_wgs84 = shapely.make_valid(geometry_wgs84)

    if geometry_wgs84.geom_type == "Polygon":
        multi_polygon = MultiPolygon([geometry_wgs84])
    elif geometry_wgs84.geom_type == "MultiPolygon":
        multi_polygon = geometry_wgs84
    else:
        raise BusinessRuleError(
            GeographyMessages.INVALID_GEOMETRY.format(layer=layer_name, identifier=identifier)
        )

    if not multi_polygon.is_valid or multi_polygon.is_empty:
        raise BusinessRuleError(
            GeographyMessages.INVALID_GEOMETRY.format(layer=layer_name, identifier=identifier)
        )
    return multi_polygon


def _read_state_layer(shp_path: Path, transformer: Transformer) -> list[StateRecord]:
    with shapefile.Reader(str(shp_path)) as reader:
        field_names = {field.name for field in reader.fields[1:]}
        _require_fields_present(field_names, STATE_REQUIRED_FIELDS, STATE_LAYER_NAME)

        records: list[StateRecord] = []
        for shape_record in reader.iterShapeRecords():
            fields = shape_record.record.as_dict()
            name = _require_non_blank(fields.get("STATE"), "STATE", STATE_LAYER_NAME)
            raw_lgd = fields.get("STATE_LGD")
            lgd_code = str(raw_lgd).strip() if raw_lgd not in (None, "") else KERALA_STATE_LGD
            geom = _to_wgs84_multipolygon(
                shape_record.shape.__geo_interface__, transformer, STATE_LAYER_NAME, name
            )
            records.append(StateRecord(lgd_code=lgd_code, name=name, geom=geom))
        return records


def _read_district_layer(shp_path: Path, transformer: Transformer) -> list[DistrictRecord]:
    with shapefile.Reader(str(shp_path)) as reader:
        field_names = {field.name for field in reader.fields[1:]}
        _require_fields_present(field_names, DISTRICT_REQUIRED_FIELDS, DISTRICT_LAYER_NAME)

        records: list[DistrictRecord] = []
        for shape_record in reader.iterShapeRecords():
            fields = shape_record.record.as_dict()
            state_lgd = _require_non_blank(
                fields.get("STATE_LGD"), "STATE_LGD", DISTRICT_LAYER_NAME
            )
            name = _require_non_blank(fields.get("DISTRICT"), "DISTRICT", DISTRICT_LAYER_NAME)
            lgd_code = _require_non_blank(fields.get("DIST_LGD"), "DIST_LGD", DISTRICT_LAYER_NAME)
            _require_state_lgd(state_lgd, DISTRICT_LAYER_NAME)
            geom = _to_wgs84_multipolygon(
                shape_record.shape.__geo_interface__, transformer, DISTRICT_LAYER_NAME, lgd_code
            )
            records.append(DistrictRecord(lgd_code=lgd_code, name=name, geom=geom))
        return records


def _read_taluk_layer(shp_path: Path, transformer: Transformer) -> list[TalukRecord]:
    with shapefile.Reader(str(shp_path)) as reader:
        field_names = {field.name for field in reader.fields[1:]}
        _require_fields_present(field_names, TALUK_REQUIRED_FIELDS, TALUK_LAYER_NAME)

        records: list[TalukRecord] = []
        for shape_record in reader.iterShapeRecords():
            fields = shape_record.record.as_dict()
            state_lgd = _require_non_blank(fields.get("STATE_LGD"), "STATE_LGD", TALUK_LAYER_NAME)
            _require_non_blank(fields.get("DISTRICT"), "DISTRICT", TALUK_LAYER_NAME)
            district_lgd = _require_non_blank(fields.get("DIST_LGD"), "DIST_LGD", TALUK_LAYER_NAME)
            name = _require_non_blank(fields.get("SUB_DIST"), "SUB_DIST", TALUK_LAYER_NAME)
            lgd_code = _require_non_blank(fields.get("SUBDIS_LGD"), "SUBDIS_LGD", TALUK_LAYER_NAME)
            _require_state_lgd(state_lgd, TALUK_LAYER_NAME)
            geom = _to_wgs84_multipolygon(
                shape_record.shape.__geo_interface__, transformer, TALUK_LAYER_NAME, lgd_code
            )
            records.append(
                TalukRecord(
                    lgd_code=lgd_code, district_lgd_code=district_lgd, name=name, geom=geom
                )
            )
        return records


def _validate_records(
    state_records: list[StateRecord],
    district_records: list[DistrictRecord],
    taluk_records: list[TalukRecord],
) -> None:
    if len(state_records) != 1:
        raise BusinessRuleError(
            GeographyMessages.UNEXPECTED_STATE_RECORD_COUNT.format(count=len(state_records))
        )
    _require_state_lgd(state_records[0].lgd_code, STATE_LAYER_NAME)

    seen_district_codes: set[str] = set()
    for district in district_records:
        if district.lgd_code in seen_district_codes:
            raise BusinessRuleError(
                GeographyMessages.DUPLICATE_DISTRICT_LGD.format(code=district.lgd_code)
            )
        seen_district_codes.add(district.lgd_code)

    seen_taluk_codes: set[str] = set()
    for taluk in taluk_records:
        if taluk.lgd_code in seen_taluk_codes:
            raise BusinessRuleError(
                GeographyMessages.DUPLICATE_TALUK_LGD.format(code=taluk.lgd_code)
            )
        seen_taluk_codes.add(taluk.lgd_code)
        if taluk.district_lgd_code not in seen_district_codes:
            raise BusinessRuleError(
                GeographyMessages.ORPHAN_TALUK_DISTRICT.format(
                    name=taluk.name, code=taluk.district_lgd_code
                )
            )


def _upsert_state(db: Session, record: StateRecord) -> tuple[UUID, bool]:
    insert_stmt = pg_insert(GisState).values(
        lgd_code=record.lgd_code,
        name=record.name,
        geom=from_shape(record.geom, srid=TARGET_SRID),
    )
    upsert_stmt: Any = insert_stmt.on_conflict_do_update(
        index_elements=[GisState.lgd_code],
        set_={
            "name": insert_stmt.excluded.name,
            "geom": insert_stmt.excluded.geom,
            "updated_at": func.now(),
        },
    ).returning(GisState.id, literal_column("(xmax = 0)").label("inserted"))
    row = db.execute(upsert_stmt).one()
    return row.id, bool(row.inserted)


def _upsert_districts(
    db: Session, records: list[DistrictRecord], state_id: UUID
) -> tuple[dict[str, UUID], int, int]:
    if not records:
        return {}, 0, 0
    values = [
        {
            "state_id": state_id,
            "lgd_code": record.lgd_code,
            "name": record.name,
            "geom": from_shape(record.geom, srid=TARGET_SRID),
        }
        for record in records
    ]
    insert_stmt = pg_insert(GisDistrict).values(values)
    upsert_stmt: Any = insert_stmt.on_conflict_do_update(
        index_elements=[GisDistrict.lgd_code],
        set_={
            "state_id": insert_stmt.excluded.state_id,
            "name": insert_stmt.excluded.name,
            "geom": insert_stmt.excluded.geom,
            "updated_at": func.now(),
        },
    ).returning(
        GisDistrict.id, GisDistrict.lgd_code, literal_column("(xmax = 0)").label("inserted")
    )
    rows = db.execute(upsert_stmt).all()
    id_by_lgd_code = {row.lgd_code: row.id for row in rows}
    created = sum(1 for row in rows if row.inserted)
    return id_by_lgd_code, created, len(rows) - created


def _upsert_taluks(
    db: Session, records: list[TalukRecord], district_id_by_lgd_code: dict[str, UUID]
) -> tuple[int, int]:
    if not records:
        return 0, 0
    values = [
        {
            "district_id": district_id_by_lgd_code[record.district_lgd_code],
            "lgd_code": record.lgd_code,
            "name": record.name,
            "geom": from_shape(record.geom, srid=TARGET_SRID),
        }
        for record in records
    ]
    insert_stmt = pg_insert(GisTaluk).values(values)
    upsert_stmt: Any = insert_stmt.on_conflict_do_update(
        index_elements=[GisTaluk.lgd_code],
        set_={
            "district_id": insert_stmt.excluded.district_id,
            "name": insert_stmt.excluded.name,
            "geom": insert_stmt.excluded.geom,
            "updated_at": func.now(),
        },
    ).returning(literal_column("(xmax = 0)").label("inserted"))
    rows = db.execute(upsert_stmt).all()
    created = sum(1 for row in rows if row.inserted)
    return created, len(rows) - created


class GeographyImportService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def import_zip(self, upload: UploadFile, max_upload_bytes: int) -> GeographyImportSummary:
        _validate_filename(upload.filename)

        with tempfile.TemporaryDirectory(
            prefix="gis-import-", ignore_cleanup_errors=True
        ) as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            zip_path = tmp_dir / "upload.zip"
            _save_upload(upload, zip_path, max_upload_bytes)

            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir()
            _extract_zip_safely(
                zip_path, extract_dir, max_upload_bytes * MAX_UNCOMPRESSED_SIZE_MULTIPLIER
            )

            layer_paths = _locate_layer_paths(extract_dir)

            state_records = _read_state_layer(
                layer_paths[STATE_LAYER_NAME],
                _build_transformer(layer_paths[STATE_LAYER_NAME], STATE_LAYER_NAME),
            )
            district_records = _read_district_layer(
                layer_paths[DISTRICT_LAYER_NAME],
                _build_transformer(layer_paths[DISTRICT_LAYER_NAME], DISTRICT_LAYER_NAME),
            )
            taluk_records = _read_taluk_layer(
                layer_paths[TALUK_LAYER_NAME],
                _build_transformer(layer_paths[TALUK_LAYER_NAME], TALUK_LAYER_NAME),
            )

            _validate_records(state_records, district_records, taluk_records)

            state_id, state_inserted = _upsert_state(self._db, state_records[0])
            district_id_by_lgd_code, districts_created, districts_updated = _upsert_districts(
                self._db, district_records, state_id
            )
            taluks_created, taluks_updated = _upsert_taluks(
                self._db, taluk_records, district_id_by_lgd_code
            )

        return GeographyImportSummary(
            state_count=len(state_records),
            district_count=len(district_records),
            taluk_count=len(taluk_records),
            created=(1 if state_inserted else 0) + districts_created + taluks_created,
            updated=(0 if state_inserted else 1) + districts_updated + taluks_updated,
            failed=0,
        )
