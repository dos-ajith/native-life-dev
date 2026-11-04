import re
import time
from dataclasses import dataclass
from io import BytesIO

import httpx
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.models.gis_village import GisVillage
from app.models.user import User
from app.repositories.popular_place_repository import PopularPlaceRepository
from app.schemas.popular_place import PopularPlaceCreate
from app.services.popular_place_service import PopularPlaceService

WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
HTTP_HEADERS = {"User-Agent": "NativeLifeDevSeed/1.0 (mailto:dev@nativelife.com; popular places test data)"}
HTTP_TIMEOUT_SECONDS = 30
THUMBNAIL_WIDTH_PATTERN = re.compile(r"/\d+px-")
THUMBNAIL_WIDTH = "/960px-"
SEED_ADMIN_EMAIL = "dev@nativelife.com"
REQUEST_PAUSE_SECONDS = 3
VECTOR_IMAGE_EXTENSION = ".svg"


@dataclass(frozen=True)
class PopularPlaceSeed:
    lgd_code: str
    wikipedia_title: str


POPULAR_PLACES = (
    PopularPlaceSeed("628519", "Kazhakkoottam"),
    PopularPlaceSeed("913454", "Neyyattinkara"),
    PopularPlaceSeed("913451", "Varkala"),
    PopularPlaceSeed("628538", "Vizhinjam Lighthouse"),
    PopularPlaceSeed("628470", "Attingal"),
    PopularPlaceSeed("913469", "Sasthamangalam"),
    PopularPlaceSeed("913452", "Nedumangad"),
    PopularPlaceSeed("628499", "Aruvikkara"),
    PopularPlaceSeed("931674", "Munnar"),
    PopularPlaceSeed("628166", "Kumarakom"),
    PopularPlaceSeed("913784", "Fort Kochi"),
    PopularPlaceSeed("913829", "Ashtamudi Lake"),
)


def _image_url(client: httpx.Client, title: str) -> str | None:
    response = client.get(WIKIPEDIA_SUMMARY_URL.format(title=title.replace(" ", "_")))
    response.raise_for_status()
    summary = response.json()
    original = summary.get("originalimage", {}).get("source")
    if original is None or original.lower().endswith(VECTOR_IMAGE_EXTENSION):
        return None
    thumbnail = summary.get("thumbnail", {}).get("source")
    if thumbnail is not None:
        return str(THUMBNAIL_WIDTH_PATTERN.sub(THUMBNAIL_WIDTH, thumbnail, count=1))
    return str(original)


def _download(client: httpx.Client, url: str) -> UploadFile:
    response = client.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0]
    return UploadFile(
        BytesIO(response.content),
        filename=url.rsplit("/", 1)[-1],
        headers=Headers({"content-type": content_type}),
    )


def _seed_one(
    db: Session,
    client: httpx.Client,
    seed: PopularPlaceSeed,
    sort_order: int,
    admin: User,
    upload_dir: str,
) -> None:
    village = db.scalar(select(GisVillage).where(GisVillage.lgd_code == seed.lgd_code))
    if village is None:
        print(f"Skipped {seed.wikipedia_title}: no GIS village with LGD code {seed.lgd_code}")
        return
    if PopularPlaceRepository(db).exists_for_village(village.id):
        print(f"Already popular: {village.name}")
        return
    try:
        image_url = _image_url(client, seed.wikipedia_title)
        if image_url is None:
            print(f"Skipped {village.name}: no Wikipedia image for '{seed.wikipedia_title}'")
            return
        PopularPlaceService(db).create(
            PopularPlaceCreate(village_id=village.id, sort_order=sort_order),
            _download(client, image_url),
            upload_dir,
            admin,
        )
    except (AppError, httpx.HTTPError) as error:
        db.rollback()
        print(f"Skipped {village.name}: {error}")
        return
    print(f"Added popular place: {village.name} ({image_url})")


def seed_popular_places() -> None:
    upload_dir = get_settings().upload_dir
    with (
        SessionLocal() as db,
        httpx.Client(
            headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True
        ) as client,
    ):
        admin = db.scalar(select(User).where(User.email == SEED_ADMIN_EMAIL))
        if admin is None:
            raise RuntimeError(f"Run scripts/seed.py first: {SEED_ADMIN_EMAIL} is missing")
        for sort_order, seed in enumerate(POPULAR_PLACES):
            _seed_one(db, client, seed, sort_order, admin, upload_dir)
            time.sleep(REQUEST_PAUSE_SECONDS)


if __name__ == "__main__":
    seed_popular_places()
