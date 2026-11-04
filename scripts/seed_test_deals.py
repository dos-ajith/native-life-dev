import mimetypes
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.permissions import RoleSlug
from app.core.storage import DEAL_IMAGES_SUBDIR
from app.models.business import Business
from app.models.category import Category
from app.models.deal import DEALS_ROOT_CATEGORY_NAME, Deal, DealStatus
from app.models.deal_image import DealImage
from app.models.deal_invitation import DealInvitation, DealInvitationStatus
from app.models.deal_item import DealItem
from app.models.deal_native import DealNative
from app.models.gis_village import GisVillage
from app.models.role import Role
from app.models.user import User
from app.services.deal_expiry_service import deal_clock_now

INDIVIDUAL_SELLER_EMAIL = "indi@gmail.com"
BUSINESS_OWNER_EMAIL = "business@gmail.com"
PROMOTER_EMAIL = "promoter@gmail.com"
KAZHAKKOOTAM_NAME = "Kazhakkoottam"
OTHER_NATIVE_NAME = "Thakazhy"
VALID_DAYS = 14
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
HTTP_HEADERS = {"User-Agent": "NativeLifeDevSeed/1.0 (mailto:dev@nativelife.com; deal test images)"}
HTTP_TIMEOUT_SECONDS = 60
IMAGE_WIDTH = 960
REQUEST_PAUSE_SECONDS = 2


@dataclass(frozen=True)
class SeedItem:
    name: str
    unit: str
    quantity: int
    original_price: str
    deal_price: str


@dataclass(frozen=True)
class SeedDeal:
    name: str
    description: str
    seller: str
    native: str
    pickup_location: str
    min_joiners: int
    items: tuple[SeedItem, ...]
    images: tuple[str, ...]


SEED_DEALS = (
    SeedDeal(
        "Test: Cold-Pressed Coconut Oil",
        "Individual seller deal. Cold-pressed coconut oil in bulk for the neighbourhood.",
        INDIVIDUAL_SELLER_EMAIL,
        KAZHAKKOOTAM_NAME,
        "Kazhakkoottam junction, near the bus stop",
        5,
        (SeedItem("Coconut oil", "litre", 50, "420.00", "360.00"),),
        (
            "Coconut oil bottle in the background of coconuts from Kaleeswari Farm.jpg",
            "Coconut oil bottle in the background of dried coconuts from Kaleeswari Farm.jpg",
        ),
    ),
    SeedDeal(
        "Test: Farm Fresh Eggs Tray",
        "Individual seller deal. Country eggs from a home farm.",
        INDIVIDUAL_SELLER_EMAIL,
        KAZHAKKOOTAM_NAME,
        "Near Technopark Phase 1 gate",
        8,
        (SeedItem("Country eggs", "tray (30)", 40, "240.00", "199.00"),),
        ("Egg cartons with chicken eggs 02.jpg", "Trays of eggs.jpg"),
    ),
    SeedDeal(
        "Test: Kuttanad Matta Rice",
        "Individual seller deal. Kuttanad red matta rice in 25 kg bags.",
        INDIVIDUAL_SELLER_EMAIL,
        OTHER_NATIVE_NAME,
        "Thakazhy boat jetty",
        6,
        (SeedItem("Matta rice", "bag (25kg)", 30, "1800.00", "1550.00"),),
        ("Red rice.jpg", "Rice, red-rice, AIVANAM-like.JPG"),
    ),
    SeedDeal(
        "Test: Phone Accessories Combo",
        "Business deal. Fast charger and earphones bundle.",
        BUSINESS_OWNER_EMAIL,
        KAZHAKKOOTAM_NAME,
        "Mobile shop counter, Kazhakkoottam",
        10,
        (
            SeedItem("Fast charger 33W", "piece", 60, "999.00", "699.00"),
            SeedItem("Wired earphones", "piece", 80, "499.00", "299.00"),
        ),
        ("Baseus CCCP20UE 20W USB charger-1.jpg", "Earphones BW 2011-12-10 15-49-08.JPG"),
    ),
    SeedDeal(
        "Test: Tempered Glass Offer",
        "Business deal. Tempered glass fitted free for all popular models.",
        BUSINESS_OWNER_EMAIL,
        KAZHAKKOOTAM_NAME,
        "Mobile shop counter, Kazhakkoottam",
        4,
        (SeedItem("Tempered glass", "piece", 100, "299.00", "149.00"),),
        (
            (
                "DSCF0529 A vendor sits at a market stall arranging products and promotional "
                "display cards for phone accessories and repair services.jpg"
            ),
        ),
    ),
    SeedDeal(
        "Test: Power Bank Festival Deal",
        "Business deal. 10000 mAh power banks at group price.",
        BUSINESS_OWNER_EMAIL,
        OTHER_NATIVE_NAME,
        "Thakazhy market pickup point",
        7,
        (SeedItem("Power bank 10000 mAh", "piece", 40, "1499.00", "1099.00"),),
        ("Portable power bank.jpg", "Power bank.JPG"),
    ),
)


def _user(db: Session, email: str) -> User:
    return db.scalars(select(User).where(User.email == email)).one()


def _village_id(db: Session, name: str) -> UUID:
    return db.scalars(select(GisVillage.id).where(GisVillage.name == name)).one()


def _find_deal(db: Session, name: str, seller_id: UUID) -> Deal | None:
    stmt = select(Deal).where(Deal.name == name, Deal.created_by == seller_id)
    return db.scalars(stmt).first()


def _business_id(db: Session, owner_id: UUID) -> UUID | None:
    return db.scalars(select(Business.id).where(Business.owner_id == owner_id)).first()


def _build_deal(db: Session, seed: SeedDeal, seller: User, category_id: UUID) -> Deal:
    is_business = seller.email == BUSINESS_OWNER_EMAIL
    now = deal_clock_now()
    return Deal(
        created_by=seller.id,
        business_id=_business_id(db, seller.id) if is_business else None,
        category_id=category_id,
        name=seed.name,
        description=seed.description,
        status=DealStatus.PUBLISHED,
        max_acceptances=1,
        accepted_count=1,
        min_joiners=seed.min_joiners,
        pickup_location=seed.pickup_location,
        starts_at=now,
        valid_until=now + timedelta(days=VALID_DAYS),
        submitted_at=now,
        acceptance_deadline=now + timedelta(days=3),
        published_at=now,
        natives=[DealNative(village_id=_village_id(db, seed.native), is_primary=True)],
        items=[
            DealItem(
                name=item.name,
                unit=item.unit,
                quantity=item.quantity,
                original_price=Decimal(item.original_price),
                deal_price=Decimal(item.deal_price),
                sort_order=index,
            )
            for index, item in enumerate(seed.items)
        ],
    )


def _download_commons_image(client: httpx.Client, title: str) -> tuple[bytes, str]:
    info = client.get(
        COMMONS_API_URL,
        params={
            "action": "query",
            "format": "json",
            "titles": f"File:{title}",
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "iiurlwidth": IMAGE_WIDTH,
        },
    )
    info.raise_for_status()
    page = next(iter(info.json()["query"]["pages"].values()))
    image_info = page["imageinfo"][0]
    time.sleep(REQUEST_PAUSE_SECONDS)
    response = client.get(image_info.get("thumburl") or image_info["url"])
    response.raise_for_status()
    time.sleep(REQUEST_PAUSE_SECONDS)
    return response.content, response.headers["content-type"].split(";")[0]


def _attach_images(client: httpx.Client, deal: Deal, titles: tuple[str, ...]) -> None:
    directory = Path(get_settings().private_upload_dir, DEAL_IMAGES_SUBDIR)
    directory.mkdir(parents=True, exist_ok=True)
    for position, title in enumerate(titles):
        contents, content_type = _download_commons_image(client, title)
        path = directory / f"{uuid.uuid4()}{mimetypes.guess_extension(content_type) or '.jpg'}"
        path.write_bytes(contents)
        deal.images.append(
            DealImage(
                storage_path=str(path),
                content_type=content_type,
                file_size_bytes=len(contents),
                is_thumbnail=position == 0,
                sort_order=position,
            )
        )


def seed_test_deals() -> None:
    with (
        SessionLocal() as db,
        httpx.Client(
            headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True
        ) as client,
    ):
        category_id = db.scalars(
            select(Category.id).where(Category.name == DEALS_ROOT_CATEGORY_NAME)
        ).one()
        promoter = _user(db, PROMOTER_EMAIL)
        promoter_role_id = db.scalars(select(Role.id).where(Role.slug == RoleSlug.PROMOTER)).one()
        for seed in SEED_DEALS:
            seller = _user(db, seed.seller)
            deal = _find_deal(db, seed.name, seller.id)
            if deal is None:
                deal = _build_deal(db, seed, seller, category_id)
                db.add(deal)
                db.flush()
                db.add(
                    DealInvitation(
                        deal_id=deal.id,
                        user_id=promoter.id,
                        role_id=promoter_role_id,
                        status=DealInvitationStatus.ACCEPTED,
                        notified_at=deal.submitted_at,
                        decided_at=deal.published_at,
                    )
                )
                print(f"Created: {seed.name} [{seed.native}] by {seed.seller}")
            if not deal.images:
                _attach_images(client, deal, seed.images)
                print(f"Added {len(seed.images)} image(s): {seed.name}")
            db.commit()


if __name__ == "__main__":
    seed_test_deals()
