import random
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import MEDIA_URL_PREFIX
from app.core.timezone import app_now
from app.models.category import Category
from app.models.lost_found_image import LostFoundImage
from app.models.lost_found_item import LostFoundItem, LostFoundKind
from app.models.user import User
from app.repositories.lost_found_image_repository import LostFoundImageRepository
from app.schemas.lost_found import MAX_LOST_FOUND_IMAGES, LostFoundCreate
from app.services.lost_found_service import LostFoundService
from scripts.seed_locations import SeedLocations
from scripts.seed_test_posts import seed_users

LOST_FOUND_ROOT_CATEGORY = "Lost & Found"
ITEMS_PER_USER = 3
MAX_DAYS_AGO = 14
SAMPLE_IMAGES_SUBDIR = "sample_images/lost_found"
LOCATION_SEED_OFFSET = 9000


@dataclass(frozen=True)
class LostFoundTemplate:
    kind: LostFoundKind
    category: str
    image_prefix: str | None
    title: str
    place: str
    description: str


LOST_FOUND_TEMPLATES = (
    LostFoundTemplate(
        LostFoundKind.LOST,
        "Electronics",
        "electronics-phone",
        "Lost black smartphone near {district} bus stand",
        "KSRTC Bus Stand",
        "Lost my black smartphone with a cracked screen guard while boarding a bus at the "
        "{district} bus stand in the evening. It has a blue back cover and a family photo as "
        "the lock screen. Please contact me if found. Reward offered.",
    ),
    LostFoundTemplate(
        LostFoundKind.FOUND,
        "Electronics",
        "electronics-laptop",
        "Found laptop in a cafe in {district}",
        "Coffee House, Main Road",
        "Found a silver laptop left on a table at a cafe in {district}. It is safe with the "
        "cafe manager. The owner can collect it by describing the laptop and the sticker on "
        "the lid.",
    ),
    LostFoundTemplate(
        LostFoundKind.LOST,
        "Electronics",
        "electronics-camera",
        "Lost vintage film camera at {district} beach",
        "Beach Road",
        "Lost a silver and black vintage film camera in a brown leather case near the beach "
        "in {district}. It has sentimental value as it belonged to my father. Any information "
        "is appreciated.",
    ),
    LostFoundTemplate(
        LostFoundKind.LOST,
        "Accessories",
        "accessories-wallet-watch",
        "Lost black leather wallet in {district} market",
        "Vegetable Market",
        "Lost a black leather wallet with my ID card, ATM card and some cash at the market in "
        "{district}. Please keep the cash if you want, but return the cards and ID. "
        "Reward offered.",
    ),
    LostFoundTemplate(
        LostFoundKind.FOUND,
        "Accessories",
        "accessories-shoes",
        "Found pair of white heels after wedding in {district}",
        "Town Hall Auditorium",
        "A pair of white heels was left behind after a wedding reception at the auditorium in "
        "{district}. They are with the auditorium office. Contact me with the size and brand "
        "to claim them.",
    ),
    LostFoundTemplate(
        LostFoundKind.LOST,
        "Pets",
        "pets-black-puppy",
        "Missing black Labrador puppy in {district}",
        "Temple Road Residential Area",
        "Our black Labrador puppy, about 4 months old, went missing near Temple Road in "
        "{district}. He is friendly, wears a red collar and answers to the name Bruno. Please "
        "call if you see him. Reward offered.",
    ),
    LostFoundTemplate(
        LostFoundKind.FOUND,
        "Pets",
        "pets-pug",
        "Found pug wandering near {district} school",
        "Government HSS Junction",
        "Found a fawn pug wandering near the school junction in {district}. It looks well "
        "cared for and is wearing a blue collar without a tag. It is safe with us. The owner "
        "can contact us with a photo.",
    ),
    LostFoundTemplate(
        LostFoundKind.LOST,
        "Documents",
        "documents-papers",
        "Lost file with certificates in {district}",
        "Railway Station",
        "Lost a plastic file containing my SSLC and degree certificates near the railway "
        "station in {district}. These are needed for a job interview. Please contact me if "
        "found.",
    ),
    LostFoundTemplate(
        LostFoundKind.FOUND,
        "Documents",
        None,
        "Found Aadhaar card and driving licence in {district}",
        "Petrol Pump, NH Bypass",
        "Found an Aadhaar card and a driving licence near the petrol pump on the bypass in "
        "{district}. The owner can contact me with their name and date of birth to verify "
        "and collect them.",
    ),
    LostFoundTemplate(
        LostFoundKind.LOST,
        "Bags",
        None,
        "Lost blue school bag in {district} auto rickshaw",
        "Private Bus Stand",
        "My son left his blue school bag in an auto rickshaw near the private bus stand in "
        "{district}. It has textbooks, a lunch box and a water bottle with his name. Please "
        "contact if found.",
    ),
    LostFoundTemplate(
        LostFoundKind.FOUND,
        "Bags",
        None,
        "Found travel bag at {district} railway station",
        "Railway Station Platform 2",
        "Found a grey travel bag left on a bench at the railway station in {district}. It has "
        "been handed over to the station master's office. Contact them with a description of "
        "the contents.",
    ),
    LostFoundTemplate(
        LostFoundKind.FOUND,
        "Other",
        None,
        "Found bunch of keys near {district} church",
        "St. George Church Road",
        "Found a bunch of keys with a red keychain and a small bell near the church road in "
        "{district}. There are around five keys including a bike key. Contact me to collect.",
    ),
)


def _category_ids(db: Session) -> dict[str, UUID]:
    root = aliased(Category)
    rows = db.execute(
        select(Category.name, Category.id)
        .join(root, root.id == Category.parent_id)
        .where(root.name == LOST_FOUND_ROOT_CATEGORY)
    ).all()
    ids = {name: category_id for name, category_id in rows}
    missing = {template.category for template in LOST_FOUND_TEMPLATES} - ids.keys()
    if missing:
        raise RuntimeError(f"Missing lost & found categories: {sorted(missing)}")
    return ids


def _sample_image_names(upload_dir: str) -> list[str]:
    directory = Path(upload_dir) / SAMPLE_IMAGES_SUBDIR
    names = sorted(path.name for path in directory.glob("*.jpg"))
    if not names:
        raise RuntimeError(f"No sample images found in {directory}")
    return names


def _already_seeded(db: Session, users: list[User]) -> bool:
    user_ids = [user.id for user in users]
    stmt = select(LostFoundItem.id).where(LostFoundItem.user_id.in_(user_ids)).limit(1)
    return db.scalar(stmt) is not None


def _attach_images(
    images: LostFoundImageRepository, item_id: UUID, prefix: str | None, names: list[str]
) -> None:
    if prefix is None:
        return
    category_prefix = prefix.split("-")[0]
    primary = [name for name in names if name.startswith(prefix)]
    extras = [name for name in names if name.startswith(category_prefix) and name not in primary]
    picked = primary + random.sample(extras, min(len(extras), MAX_LOST_FOUND_IMAGES - 2))
    for sort_order, name in enumerate(picked[:MAX_LOST_FOUND_IMAGES]):
        images.add(
            LostFoundImage(
                item_id=item_id,
                image_url=f"{MEDIA_URL_PREFIX}/{SAMPLE_IMAGES_SUBDIR}/{name}",
                sort_order=sort_order,
            )
        )


def _seed_items(db: Session, users: list[User], upload_dir: str) -> None:
    locations = SeedLocations(db, LOCATION_SEED_OFFSET)
    category_ids = _category_ids(db)
    image_names = _sample_image_names(upload_dir)
    items = LostFoundService(db)
    images = LostFoundImageRepository(db)
    today = app_now().date()
    for user_index, user in enumerate(users):
        for item_index in range(ITEMS_PER_USER):
            sequence = user_index * ITEMS_PER_USER + item_index
            template = LOST_FOUND_TEMPLATES[sequence % len(LOST_FOUND_TEMPLATES)]
            spot = locations.spot(sequence)
            payload = LostFoundCreate(
                kind=template.kind,
                category_id=category_ids[template.category],
                title=template.title.format(district=spot.district_name),
                description=template.description.format(district=spot.district_name),
                location_name=f"{template.place}, {spot.district_name}",
                latitude=spot.latitude,
                longitude=spot.longitude,
                occurred_on=today - timedelta(days=sequence % MAX_DAYS_AGO),
                contact_info=user.phone or user.email or "",
            )
            item = items.create(payload, [], upload_dir, user)
            _attach_images(images, item.id, template.image_prefix, image_names)
    print(f"Seeded {len(users) * ITEMS_PER_USER} test lost & found items")


def seed_test_lost_found() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        if _already_seeded(db, users):
            print("Test lost & found items already exist; skipping")
            return
        _seed_items(db, users, get_settings().upload_dir)
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_lost_found()
