import shutil
import stat
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import shapefile
import shapely
from fastapi import UploadFile
from geoalchemy2.shape import from_shape
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from sqlalchemy import func, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AppError, BusinessRuleError
from app.core.messages import GeographyMessages
from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.user import User
from app.schemas.geography import GeographyImportSummary
from app.services.activity_log_service import ActivityLogService
from app.services.geography_boundary_derivation import derive_admin_boundaries
from app.services.geography_layer_detector import (
    AdminField,
    AdminLevel,
    DetectedSource,
    LayerProfile,
    detect_source,
)
from app.services.geography_records import (
    AdminBoundaries,
    DistrictRecord,
    StateRecord,
    TalukRecord,
    VillageRecord,
)

TARGET_SRID = 4326
KERALA_STATE_LGD = "32"
MIN_LONGITUDE, MAX_LONGITUDE = -180.0, 180.0
MIN_LATITUDE, MAX_LATITUDE = -90.0, 90.0

UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_UNCOMPRESSED_SIZE_MULTIPLIER = 20
GEOGRAPHY_IMPORT_ENTITY_TYPE = "geography_import"


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


def _build_transformer(layer: LayerProfile) -> Transformer:
    if not layer.has_prj:
        raise BusinessRuleError(GeographyMessages.MISSING_PRJ.format(layer=layer.name))
    if layer.crs is None:
        raise BusinessRuleError(GeographyMessages.INVALID_PRJ.format(layer=layer.name))
    return Transformer.from_crs(layer.crs, f"EPSG:{TARGET_SRID}", always_xy=True)


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


def _polygonal_parts(geometry: BaseGeometry) -> MultiPolygon | None:
    if isinstance(geometry, Polygon):
        return MultiPolygon([geometry])
    if isinstance(geometry, MultiPolygon):
        return geometry
    if geometry.geom_type == "GeometryCollection":
        parts = [
            polygon
            for part in shapely.get_parts(geometry)
            for polygon in shapely.get_parts(part)
            if isinstance(polygon, Polygon) and not polygon.is_empty
        ]
        return MultiPolygon(parts) if parts else None
    return None


def _within_wgs84_bounds(geometry: BaseGeometry) -> bool:
    minx, miny, maxx, maxy = (float(value) for value in geometry.bounds)
    return (
        MIN_LONGITUDE <= minx <= maxx <= MAX_LONGITUDE
        and MIN_LATITUDE <= miny <= maxy <= MAX_LATITUDE
    )


def _to_wgs84_multipolygon(
    source_shape: shapefile.Shape, transformer: Transformer, layer_name: str, identifier: str
) -> MultiPolygon:
    invalid_geometry = BusinessRuleError(
        GeographyMessages.INVALID_GEOMETRY.format(layer=layer_name, identifier=identifier)
    )
    if source_shape.shapeType == shapefile.NULL:
        raise invalid_geometry

    geometry_2d = shapely.force_2d(shapely_shape(source_shape.__geo_interface__))
    geometry_wgs84 = shapely_transform(transformer.transform, geometry_2d)
    if not geometry_wgs84.is_valid:
        geometry_wgs84 = shapely.make_valid(geometry_wgs84)

    multi_polygon = _polygonal_parts(geometry_wgs84)
    if multi_polygon is None or multi_polygon.is_empty or not multi_polygon.is_valid:
        raise invalid_geometry
    if not _within_wgs84_bounds(multi_polygon):
        raise BusinessRuleError(
            GeographyMessages.GEOMETRY_OUT_OF_RANGE.format(layer=layer_name, identifier=identifier)
        )
    return multi_polygon


def _field_value(fields: dict[str, Any], layer: LayerProfile, admin_field: AdminField) -> str:
    source_name = layer.field_map[admin_field]
    return _require_non_blank(fields.get(source_name), source_name, layer.name)


def _read_state_layer(layer: LayerProfile, transformer: Transformer) -> list[StateRecord]:
    lgd_field = layer.field_map.get(AdminField.STATE_LGD)
    with shapefile.Reader(str(layer.path)) as reader:
        records: list[StateRecord] = []
        for shape_record in reader.iterShapeRecords():
            fields = shape_record.record.as_dict()
            name = _field_value(fields, layer, AdminField.STATE_NAME)
            raw_lgd = fields.get(lgd_field) if lgd_field is not None else None
            lgd_code = str(raw_lgd).strip() if raw_lgd not in (None, "") else KERALA_STATE_LGD
            geom = _to_wgs84_multipolygon(shape_record.shape, transformer, layer.name, name)
            records.append(StateRecord(lgd_code=lgd_code, name=name, geom=geom))
        return records


def _read_district_layer(layer: LayerProfile, transformer: Transformer) -> list[DistrictRecord]:
    with shapefile.Reader(str(layer.path)) as reader:
        records: list[DistrictRecord] = []
        for shape_record in reader.iterShapeRecords():
            fields = shape_record.record.as_dict()
            state_lgd = _field_value(fields, layer, AdminField.STATE_LGD)
            name = _field_value(fields, layer, AdminField.DISTRICT_NAME)
            lgd_code = _field_value(fields, layer, AdminField.DISTRICT_LGD)
            _require_state_lgd(state_lgd, layer.name)
            geom = _to_wgs84_multipolygon(shape_record.shape, transformer, layer.name, lgd_code)
            records.append(DistrictRecord(lgd_code=lgd_code, name=name, geom=geom))
        return records


def _read_taluk_layer(layer: LayerProfile, transformer: Transformer) -> list[TalukRecord]:
    with shapefile.Reader(str(layer.path)) as reader:
        records: list[TalukRecord] = []
        for shape_record in reader.iterShapeRecords():
            fields = shape_record.record.as_dict()
            state_lgd = _field_value(fields, layer, AdminField.STATE_LGD)
            district_lgd = _field_value(fields, layer, AdminField.DISTRICT_LGD)
            name = _field_value(fields, layer, AdminField.TALUK_NAME)
            lgd_code = _field_value(fields, layer, AdminField.TALUK_LGD)
            _require_state_lgd(state_lgd, layer.name)
            geom = _to_wgs84_multipolygon(shape_record.shape, transformer, layer.name, lgd_code)
            records.append(
                TalukRecord(
                    lgd_code=lgd_code, district_lgd_code=district_lgd, name=name, geom=geom
                )
            )
        return records


def _read_village_layer(layer: LayerProfile, transformer: Transformer) -> list[VillageRecord]:
    with shapefile.Reader(str(layer.path)) as reader:
        records: list[VillageRecord] = []
        for record_number, shape_record in enumerate(reader.iterShapeRecords(), start=1):
            fields = shape_record.record.as_dict()
            state_lgd = _field_value(fields, layer, AdminField.STATE_LGD)
            _require_state_lgd(state_lgd, layer.name)
            records.append(
                VillageRecord(
                    state_lgd_code=state_lgd,
                    state_name=_field_value(fields, layer, AdminField.STATE_NAME),
                    district_lgd_code=_field_value(fields, layer, AdminField.DISTRICT_LGD),
                    district_name=_field_value(fields, layer, AdminField.DISTRICT_NAME),
                    taluk_lgd_code=_field_value(fields, layer, AdminField.TALUK_LGD),
                    taluk_name=_field_value(fields, layer, AdminField.TALUK_NAME),
                    geom=_to_wgs84_multipolygon(
                        shape_record.shape, transformer, layer.name, f"#{record_number}"
                    ),
                )
            )
        return records


def _read_direct_boundaries(layers: Mapping[AdminLevel, LayerProfile]) -> AdminBoundaries:
    state_layer = layers[AdminLevel.STATE]
    district_layer = layers[AdminLevel.DISTRICT]
    taluk_layer = layers[AdminLevel.TALUK]
    return AdminBoundaries(
        states=_read_state_layer(state_layer, _build_transformer(state_layer)),
        districts=_read_district_layer(district_layer, _build_transformer(district_layer)),
        taluks=_read_taluk_layer(taluk_layer, _build_transformer(taluk_layer)),
    )


def _read_boundaries(source: DetectedSource) -> tuple[AdminBoundaries, int | None]:
    if source.village_layer is None:
        return _read_direct_boundaries(source.admin_layers), None
    villages = _read_village_layer(source.village_layer, _build_transformer(source.village_layer))
    return derive_admin_boundaries(villages), len(villages)


def _validate_records(
    state_records: list[StateRecord],
    district_records: list[DistrictRecord],
    taluk_records: list[TalukRecord],
) -> None:
    if len(state_records) != 1:
        raise BusinessRuleError(
            GeographyMessages.UNEXPECTED_STATE_RECORD_COUNT.format(count=len(state_records))
        )
    _require_state_lgd(state_records[0].lgd_code, AdminLevel.STATE.value)

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


def _failure_reason(error: Exception) -> str:
    return error.message if isinstance(error, AppError) else type(error).__name__


class GeographyImportService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._activity_logs = ActivityLogService(db)

    def import_zip(
        self, upload: UploadFile, max_upload_bytes: int, actor: User
    ) -> GeographyImportSummary:
        import_id = uuid4()
        upload_metadata = {"filename": upload.filename}
        self._log(actor, ActivityAction.GEOGRAPHY_IMPORT_STARTED, import_id, upload_metadata)
        try:
            summary = self._import(upload, max_upload_bytes)
            self._log(
                actor,
                ActivityAction.GEOGRAPHY_IMPORT_COMPLETED,
                import_id,
                {**upload_metadata, **summary.model_dump(mode="json")},
            )
        except Exception as error:
            self._db.rollback()
            self._log(
                actor,
                ActivityAction.GEOGRAPHY_IMPORT_FAILED,
                import_id,
                {**upload_metadata, "error": _failure_reason(error)},
            )
            raise
        return summary

    def _log(
        self, actor: User, action: str, import_id: UUID, metadata: dict[str, Any]
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=GEOGRAPHY_IMPORT_ENTITY_TYPE,
            entity_id=import_id,
            metadata=metadata,
        )

    def _import(self, upload: UploadFile, max_upload_bytes: int) -> GeographyImportSummary:
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

            source = detect_source(extract_dir)
            boundaries, villages_processed = _read_boundaries(source)
            state_records = boundaries.states
            district_records = boundaries.districts
            taluk_records = boundaries.taluks

            _validate_records(state_records, district_records, taluk_records)

            state_id, state_inserted = _upsert_state(self._db, state_records[0])
            district_id_by_lgd_code, districts_created, districts_updated = _upsert_districts(
                self._db, district_records, state_id
            )
            taluks_created, taluks_updated = _upsert_taluks(
                self._db, taluk_records, district_id_by_lgd_code
            )

        return GeographyImportSummary(
            source_mode=source.mode,
            villages_processed=villages_processed,
            state_count=len(state_records),
            district_count=len(district_records),
            taluk_count=len(taluk_records),
            created=(1 if state_inserted else 0) + districts_created + taluks_created,
            updated=(0 if state_inserted else 1) + districts_updated + taluks_updated,
            failed=0,
        )
