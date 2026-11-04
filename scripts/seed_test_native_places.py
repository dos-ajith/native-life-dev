import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import MEDIA_URL_PREFIX
from app.models.gis_village import GisVillage
from app.models.popular_place import PopularPlace

TAG_NAMES = {
    "628519": "Technopark Town",
    "913454": "Land of Coconuts",
    "913451": "Cliff Beach Town",
    "628538": "Lighthouse Shore",
    "628470": "Heritage Town",
    "913469": "Temple City Suburb",
    "913452": "Hill Gateway",
    "628499": "Dam Side Village",
    "931674": "Tea Hills",
    "628166": "Backwater Village",
    "913784": "Old Port Quarter",
    "913829": "Lake Town",
}


def _copy_image(image_url: str, upload_dir: str) -> str | None:
    source = Path(upload_dir, Path(image_url).name)
    if not source.is_file():
        return None
    filename = f"{uuid.uuid4()}{source.suffix}"
    shutil.copyfile(source, Path(upload_dir, filename))
    return f"{MEDIA_URL_PREFIX}/{filename}"


def seed_test_native_places() -> None:
    upload_dir = get_settings().upload_dir
    with SessionLocal() as db:
        for lgd_code, tag_name in TAG_NAMES.items():
            row = db.execute(
                select(GisVillage, PopularPlace.image_url)
                .join(PopularPlace, PopularPlace.village_id == GisVillage.id)
                .where(GisVillage.lgd_code == lgd_code)
            ).first()
            if row is None:
                print(f"Skipped {lgd_code}: no village with a popular place image")
                continue
            village, popular_image_url = row
            village.tag_name = tag_name
            if village.image_url is None:
                village.image_url = _copy_image(popular_image_url, upload_dir)
            db.commit()
            print(f"{village.name}: '{tag_name}' {village.image_url}")


if __name__ == "__main__":
    seed_test_native_places()
