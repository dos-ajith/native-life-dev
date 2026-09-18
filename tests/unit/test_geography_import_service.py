import io
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import BusinessRuleError
from app.services.geography_import_service import (
    DISTRICT_LAYER_NAME,
    STATE_LAYER_NAME,
    TALUK_LAYER_NAME,
    DistrictRecord,
    StateRecord,
    TalukRecord,
    _build_transformer,
    _extract_zip_safely,
    _locate_layer_paths,
    _read_district_layer,
    _read_state_layer,
    _read_taluk_layer,
    _require_fields_present,
    _require_non_blank,
    _save_upload,
    _validate_filename,
    _validate_records,
)

SOURCE_DIR = Path(__file__).resolve().parents[2] / "data" / "gis" / "kerala_admin" / "source" / "32"
LAYER_EXTENSIONS = (".shp", ".shx", ".dbf", ".prj", ".cpg")


def _upload_file(content: bytes, filename: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "application/zip"}),
    )


def _build_source_zip(tmp_path: Path, layer_names: tuple[str, ...], nested: bool = False) -> Path:
    zip_path = tmp_path / "kerala_admin_boundary.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for layer_name in layer_names:
            for extension in LAYER_EXTENSIONS:
                source_file = SOURCE_DIR / f"{layer_name}{extension}"
                if not source_file.exists():
                    continue
                arcname = f"extracted/{layer_name}{extension}" if nested else source_file.name
                archive.write(source_file, arcname=arcname)
    return zip_path


REQUIRED_LAYER_NAMES = (STATE_LAYER_NAME, DISTRICT_LAYER_NAME, TALUK_LAYER_NAME)


@pytest.mark.skipif(not SOURCE_DIR.exists(), reason="Sample Survey of India dataset not available")
class TestRealShapefileReading:
    def test_reads_state_district_and_taluk_layers_with_correct_counts(
        self, tmp_path: Path
    ) -> None:
        zip_path = _build_source_zip(tmp_path, REQUIRED_LAYER_NAMES, nested=True)
        extract_dir = tmp_path / "extracted_root"
        extract_dir.mkdir()
        _extract_zip_safely(zip_path, extract_dir, max_uncompressed_bytes=100 * 1024 * 1024)

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

        assert len(state_records) == 1
        assert state_records[0].lgd_code == "32"
        assert state_records[0].geom.geom_type == "MultiPolygon"
        assert len(district_records) == 14
        assert len(taluk_records) == 78
        assert all(district.geom.is_valid for district in district_records)
        assert all(taluk.geom.is_valid for taluk in taluk_records)

        district_lgd_codes = {district.lgd_code for district in district_records}
        assert all(taluk.district_lgd_code in district_lgd_codes for taluk in taluk_records)

        minx, miny, maxx, maxy = state_records[0].geom.bounds
        assert 70 < minx < 80
        assert 5 < miny < 15
        assert 70 < maxx < 80
        assert 5 < maxy < 15

        _validate_records(state_records, district_records, taluk_records)


def test_validate_filename_rejects_non_zip() -> None:
    with pytest.raises(BusinessRuleError):
        _validate_filename("boundary.rar")


def test_validate_filename_rejects_missing_filename() -> None:
    with pytest.raises(BusinessRuleError):
        _validate_filename(None)


def test_validate_filename_accepts_zip_case_insensitively() -> None:
    _validate_filename("Kerala_Boundary.ZIP")


def test_save_upload_rejects_oversized_file(tmp_path: Path) -> None:
    upload = _upload_file(b"a" * 2048, "boundary.zip")
    with pytest.raises(BusinessRuleError):
        _save_upload(upload, tmp_path / "upload.zip", max_bytes=1024)


def test_save_upload_rejects_non_zip_content(tmp_path: Path) -> None:
    upload = _upload_file(b"not actually a zip file", "boundary.zip")
    with pytest.raises(BusinessRuleError):
        _save_upload(upload, tmp_path / "upload.zip", max_bytes=1024 * 1024)


def test_extract_zip_safely_rejects_path_traversal(tmp_path: Path) -> None:
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../../evil.txt", "payload")

    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(BusinessRuleError):
        _extract_zip_safely(zip_path, destination, max_uncompressed_bytes=1024 * 1024)


def test_extract_zip_safely_rejects_absolute_path_entry(tmp_path: Path) -> None:
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("/etc/passwd", "payload")

    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(BusinessRuleError):
        _extract_zip_safely(zip_path, destination, max_uncompressed_bytes=1024 * 1024)


def test_extract_zip_safely_rejects_oversized_uncompressed_content(tmp_path: Path) -> None:
    zip_path = tmp_path / "boundary.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("KERALA_STATE_BDY.shp", "x" * 2048)

    destination = tmp_path / "extracted"
    destination.mkdir()
    with pytest.raises(BusinessRuleError):
        _extract_zip_safely(zip_path, destination, max_uncompressed_bytes=1024)


def test_extract_zip_safely_extracts_nested_folders(tmp_path: Path) -> None:
    zip_path = tmp_path / "boundary.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("some_random_folder_name/nested/KERALA_STATE_BDY.shp", "content")

    destination = tmp_path / "extracted"
    destination.mkdir()
    _extract_zip_safely(zip_path, destination, max_uncompressed_bytes=1024 * 1024)

    assert (destination / "some_random_folder_name" / "nested" / "KERALA_STATE_BDY.shp").exists()


def test_locate_layer_paths_raises_when_layer_missing(tmp_path: Path) -> None:
    (tmp_path / f"{STATE_LAYER_NAME}.shp").write_bytes(b"")
    (tmp_path / f"{DISTRICT_LAYER_NAME}.shp").write_bytes(b"")

    with pytest.raises(BusinessRuleError):
        _locate_layer_paths(tmp_path)


def test_locate_layer_paths_ignores_zip_filename_and_folder_names(tmp_path: Path) -> None:
    nested = tmp_path / "SOME_UNPREDICTABLE_EXPORT_NAME_2026"
    nested.mkdir()
    for layer_name in REQUIRED_LAYER_NAMES:
        (nested / f"{layer_name}.shp").write_bytes(b"")

    layer_paths = _locate_layer_paths(tmp_path)

    assert set(layer_paths.keys()) == set(REQUIRED_LAYER_NAMES)


def test_require_fields_present_raises_for_missing_field() -> None:
    with pytest.raises(BusinessRuleError):
        _require_fields_present({"STATE"}, ("STATE", "STATE_LGD"), STATE_LAYER_NAME)


def test_require_non_blank_raises_for_blank_value() -> None:
    with pytest.raises(BusinessRuleError):
        _require_non_blank("   ", "STATE", STATE_LAYER_NAME)


def test_require_non_blank_raises_for_none_value() -> None:
    with pytest.raises(BusinessRuleError):
        _require_non_blank(None, "STATE", STATE_LAYER_NAME)


def test_require_non_blank_returns_stripped_value() -> None:
    assert _require_non_blank("  Kerala  ", "STATE", STATE_LAYER_NAME) == "Kerala"


def _multipolygon() -> object:
    from shapely.geometry import MultiPolygon, Polygon

    return MultiPolygon([Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])])


def test_validate_records_rejects_wrong_state_lgd() -> None:
    geom = _multipolygon()
    state = StateRecord(lgd_code="99", name="Kerala", geom=geom)
    with pytest.raises(BusinessRuleError):
        _validate_records(state_records=[state], district_records=[], taluk_records=[])


def test_validate_records_rejects_duplicate_district_lgd() -> None:
    geom = _multipolygon()
    state = StateRecord(lgd_code="32", name="Kerala", geom=geom)
    districts = [
        DistrictRecord(lgd_code="593", name="Palakkad", geom=geom),
        DistrictRecord(lgd_code="593", name="Palakkad Duplicate", geom=geom),
    ]
    with pytest.raises(BusinessRuleError):
        _validate_records(state_records=[state], district_records=districts, taluk_records=[])


def test_validate_records_rejects_orphan_taluk() -> None:
    geom = _multipolygon()
    state = StateRecord(lgd_code="32", name="Kerala", geom=geom)
    districts = [DistrictRecord(lgd_code="593", name="Palakkad", geom=geom)]
    taluks = [
        TalukRecord(lgd_code="05674", district_lgd_code="999", name="Unknown Taluk", geom=geom)
    ]
    with pytest.raises(BusinessRuleError):
        _validate_records(state_records=[state], district_records=districts, taluk_records=taluks)


def test_validate_records_accepts_consistent_data() -> None:
    geom = _multipolygon()
    state = StateRecord(lgd_code="32", name="Kerala", geom=geom)
    districts = [DistrictRecord(lgd_code="593", name="Palakkad", geom=geom)]
    taluks = [TalukRecord(lgd_code="05674", district_lgd_code="593", name="Alathur", geom=geom)]
    _validate_records(state_records=[state], district_records=districts, taluk_records=taluks)


def test_validate_records_rejects_missing_state_record() -> None:
    with pytest.raises(BusinessRuleError):
        _validate_records(state_records=[], district_records=[], taluk_records=[])


def test_taluk_record_is_frozen_and_comparable() -> None:
    geom = _multipolygon()
    record = TalukRecord(lgd_code=str(uuid4()), district_lgd_code="593", name="Alathur", geom=geom)
    with pytest.raises(AttributeError):
        record.name = "Changed"  # type: ignore[misc]
