from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.permissions import RoleSlug
from app.core.security import hash_password
from app.core.timezone import app_now
from app.main import app
from app.models.category import Category
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from app.models.user_has_role import user_has_roles
from app.plugins.media import MEDIA_URL_PREFIX, delete_plugin_image
from app.repositories.role_repository import RoleRepository
from scripts.seed import DEFAULT_USER_PASSWORD

ADMIN_EMAIL = "dev@nativelife.com"
PLUGIN_KEY = "ecommerce"
API_PREFIX = get_settings().api_v1_prefix
PRODUCT_IMAGES_ROOT = Path(get_settings().upload_dir, "plugins", PLUGIN_KEY)
PRODUCT_IMAGES_URL_ROOT = f"{MEDIA_URL_PREFIX}/plugins/{PLUGIN_KEY}"
IMAGE_CONTENT_TYPE = "image/jpeg"
PRODUCTS_PAGE_SIZE = 100
LOW_STOCK_THRESHOLD = 5


@dataclass(frozen=True)
class SeedProduct:
    sku: str
    name: str
    description: str
    selling_price: str
    original_price: str
    quantity: int
    category: str
    images: tuple[str, ...]
    bulk: bool = False
    individual: bool = False


@dataclass(frozen=True)
class SeedBusiness:
    owner_email: str
    first_name: str
    last_name: str
    phone: str
    name: str
    description: str
    category_slug: str
    latitude: float
    longitude: float
    products: tuple[SeedProduct, ...]


SEED_BUSINESSES = (
    SeedBusiness(
        "electronics.owner@test.nativelife.com",
        "Ravi",
        "Menon",
        "+919400100000",
        "Test: Kazhakkoottam Mobile Hub",
        "Mobiles, chargers and accessories near Technopark.",
        "business-product-ecommerce-electronics",
        8.5683,
        76.8728,
        (
            SeedProduct(
                "ELEC-CHG-33W",
                "Fast Charger 33W",
                "33W USB-C fast charger with short-circuit protection.",
                "699.00",
                "999.00",
                60,
                "Electronics",
                (
                    "1fedc0a9-0f4f-48c9-a08a-4114b81e7338.jpg",
                    "23539041-6c03-4592-b239-f0932d22a959.jpg",
                ),
                bulk=True,
                individual=True,
            ),
            SeedProduct(
                "ELEC-PWR-10K",
                "Power Bank 10000 mAh",
                "Slim 10000 mAh power bank with dual USB output.",
                "1099.00",
                "1499.00",
                40,
                "Electronics",
                (
                    "1978e67e-3ba5-493c-98d6-3ff03451adcd.jpg",
                    "86355c35-be8f-4aa8-a58f-2603c32accf3.jpg",
                ),
                bulk=True,
            ),
            SeedProduct(
                "ELEC-EAR-WIRED",
                "Wired Earphones",
                "In-ear wired earphones with inline mic.",
                "299.00",
                "499.00",
                80,
                "Electronics",
                ("311043c5-cbf0-43d4-8867-5fd616939b58.jpg",),
                individual=True,
            ),
            SeedProduct(
                "ELEC-BT-SPK",
                "Bluetooth Speaker",
                "Portable Bluetooth speaker, 8 hours playback.",
                "1299.00",
                "1799.00",
                25,
                "Electronics",
                ("9f1e8142-9219-46c2-8616-b85580763d19.jpg",),
                individual=True,
            ),
        ),
    ),
    SeedBusiness(
        "fashion.owner@test.nativelife.com",
        "Divya",
        "Nair",
        "+919400100001",
        "Test: Thakazhy Handloom House",
        "Kerala handloom sarees, mundus and cotton wear.",
        "business-product-ecommerce-fashion",
        9.3667,
        76.4167,
        (
            SeedProduct(
                "FASH-MUNDU-SET",
                "Cotton Mundu Set",
                "Handloom double mundu for festive and daily wear.",
                "950.00",
                "1200.00",
                45,
                "Apparel",
                ("5d1ecf0f-0276-44ab-ba73-ec7b6cfb3c81.jpg",),
                bulk=True,
            ),
            SeedProduct(
                "FASH-SHAWL-WOOL",
                "Woollen Shawl",
                "Warm woollen shawl with woven border.",
                "799.00",
                "1099.00",
                20,
                "Apparel",
                ("98ab4bee-f9a4-435b-b702-bbe6e9e586ff.jpg",),
            ),
        ),
    ),
    SeedBusiness(
        "grocery.owner@test.nativelife.com",
        "Suresh",
        "Kumar",
        "+919400100002",
        "Test: Native Farm Fresh Grocers",
        "Farm-direct staples, spices and cold-pressed oils.",
        "business-product-ecommerce-grocery",
        8.5683,
        76.8728,
        (
            SeedProduct(
                "GROC-COCONUT-OIL-1L",
                "Cold-Pressed Coconut Oil 1L",
                "Traditional cold-pressed coconut oil, 1 litre bottle.",
                "360.00",
                "420.00",
                80,
                "Groceries",
                ("c3010235-9f80-43ba-8883-16f890718860.jpg",),
                bulk=True,
                individual=True,
            ),
            SeedProduct(
                "GROC-EGGS-TRAY",
                "Country Eggs Tray (30)",
                "Farm-fresh country eggs, tray of 30.",
                "199.00",
                "240.00",
                40,
                "Groceries",
                ("c5431511-a306-449c-99c6-80d9df42e148.jpg",),
                individual=True,
            ),
            SeedProduct(
                "GROC-PEPPER-250G",
                "Black Pepper 250g",
                "Whole black pepper from Wayanad, 250 g.",
                "260.00",
                "320.00",
                70,
                "Groceries",
                ("42a8a5f8-a0e2-45b3-b0d1-ef96085cbdb2.jpg",),
                bulk=True,
                individual=True,
            ),
            SeedProduct(
                "GROC-BANANA-CHIPS",
                "Banana Chips 500g",
                "Crispy Kerala banana chips fried in coconut oil.",
                "180.00",
                "220.00",
                90,
                "Groceries",
                ("80d04a06-b3be-45f2-a207-5cbc46e32def.jpg",),
                individual=True,
            ),
        ),
    ),
    SeedBusiness(
        "home.owner@test.nativelife.com",
        "Anita",
        "George",
        "+919400100003",
        "Test: Thakazhy Home & Living",
        "Kitchenware, decor and daily home essentials.",
        "business-product-ecommerce-home-living",
        9.3667,
        76.4167,
        (
            SeedProduct(
                "HOME-CLAY-POT",
                "Clay Cooking Pot",
                "Handmade clay pot for fish curry and slow cooking.",
                "450.00",
                "600.00",
                50,
                "Home & Kitchen",
                ("017a9a47-65eb-45b8-8724-23fc479221ef.jpg",),
                bulk=True,
            ),
        ),
    ),
)


def _verify_business_role(db: Session, user_id: UUID) -> None:
    role_id = db.scalars(
        select(Role.id).where(Role.slug == RoleSlug.BUSINESS_SERVICE_PROVIDER)
    ).one()
    db.execute(
        update(user_has_roles)
        .where(
            user_has_roles.c.user_id == user_id,
            user_has_roles.c.role_id == role_id,
            user_has_roles.c.verified_at.is_(None),
        )
        .values(verified_at=app_now())
    )


def _get_or_create_owner(seed: SeedBusiness) -> UUID:
    with SessionLocal() as db:
        owner = db.scalars(select(User).where(User.email == seed.owner_email)).first()
        if owner is None:
            roles = RoleRepository(db)
            role_slugs = (RoleSlug.INDIVIDUAL_USER, RoleSlug.BUSINESS_SERVICE_PROVIDER)
            owner = User(
                first_name=seed.first_name,
                last_name=seed.last_name,
                email=seed.owner_email,
                phone=seed.phone,
                password_hash=hash_password(DEFAULT_USER_PASSWORD),
                status=UserStatus.ACTIVE,
                user_type=UserType.PUBLIC,
                email_verified_at=app_now(),
                roles=[
                    role for slug in role_slugs if (role := roles.get_by_slug(slug)) is not None
                ],
            )
            db.add(owner)
            db.flush()
            print(f"Created business user: {seed.owner_email} / {DEFAULT_USER_PASSWORD}")
        _verify_business_role(db, owner.id)
        db.commit()
        return owner.id


def _category_id(slug: str) -> UUID:
    with SessionLocal() as db:
        return db.scalars(select(Category.id).where(Category.slug == slug)).one()


def _data(response: httpx.Response) -> Any:
    if response.status_code >= httpx.codes.BAD_REQUEST:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.text}")
    return response.json()["data"]


def _login(client: TestClient, email: str) -> dict[str, str]:
    data = _data(
        client.post(
            f"{API_PREFIX}/auth/login", json={"email": email, "password": DEFAULT_USER_PASSWORD}
        )
    )
    return {"Authorization": f"Bearer {data['access_token']}"}


def _find_business(client: TestClient, owner_headers: dict[str, str], name: str) -> dict | None:
    page = _data(client.get(f"{API_PREFIX}/me/businesses", headers=owner_headers))
    return next((item for item in page["items"] if item["name"] == name), None)


def _ensure_business(
    client: TestClient,
    admin_headers: dict[str, str],
    owner_headers: dict[str, str],
    owner_id: UUID,
    seed: SeedBusiness,
) -> UUID:
    existing = _find_business(client, owner_headers, seed.name)
    if existing is not None:
        return UUID(existing["id"])
    created = _data(
        client.post(
            f"{API_PREFIX}/admin/businesses",
            headers=admin_headers,
            data={
                "owner_id": str(owner_id),
                "name": seed.name,
                "description": seed.description,
                "category_id": str(_category_id(seed.category_slug)),
                "latitude": str(seed.latitude),
                "longitude": str(seed.longitude),
            },
        )
    )
    print(f"Created business: {seed.name}")
    return UUID(created["id"])


def _enable_plugin(client: TestClient, owner_headers: dict[str, str], business_id: UUID) -> None:
    _data(
        client.post(
            f"{API_PREFIX}/me/businesses/{business_id}/plugins/{PLUGIN_KEY}",
            headers=owner_headers,
        )
    )


def _plugin_url(business_id: UUID, path: str) -> str:
    return f"{API_PREFIX}/plugins/{PLUGIN_KEY}/businesses/{business_id}/{path}"


def _product_categories(
    client: TestClient, owner_headers: dict[str, str], business_id: UUID
) -> dict[str, str]:
    data = _data(client.get(_plugin_url(business_id, "product-categories"), headers=owner_headers))
    return {category["name"]: category["id"] for category in data}


def _existing_skus(
    client: TestClient, owner_headers: dict[str, str], business_id: UUID
) -> set[str]:
    page = _data(
        client.get(
            _plugin_url(business_id, "products"),
            headers=owner_headers,
            params={"page_size": PRODUCTS_PAGE_SIZE},
        )
    )
    return {item["sku"] for item in page["items"]}


def _reuse_committed_images(
    business_id: UUID, stored_images: list[dict[str, Any]], paths: list[Path]
) -> None:
    with SessionLocal() as db:
        for stored, path in zip(stored_images, paths, strict=True):
            db.execute(
                text("UPDATE plg_ecommerce_product_images SET url = :url WHERE id = :id"),
                {"url": f"{PRODUCT_IMAGES_URL_ROOT}/{business_id}/{path.name}", "id": stored["id"]},
            )
        db.commit()
    for stored in stored_images:
        delete_plugin_image(stored["url"])


def _create_product(
    client: TestClient,
    owner_headers: dict[str, str],
    business_id: UUID,
    category_ids: dict[str, str],
    seed: SeedProduct,
) -> None:
    paths = [PRODUCT_IMAGES_ROOT / str(business_id) / name for name in seed.images]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{seed.sku}: missing image(s) {missing}")
    files = [("images", (path.name, path.read_bytes(), IMAGE_CONTENT_TYPE)) for path in paths]
    form = {
        "name": seed.name,
        "sku": seed.sku,
        "description": seed.description,
        "selling_price": seed.selling_price,
        "original_price": seed.original_price,
        "category_id": category_ids[seed.category],
        "quantity": str(seed.quantity),
        "low_stock_threshold": str(LOW_STOCK_THRESHOLD),
        "is_bulk_promotable": str(seed.bulk).lower(),
        "is_individually_promotable": str(seed.individual).lower(),
    }
    created = _data(
        client.post(
            _plugin_url(business_id, "products"), headers=owner_headers, data=form, files=files
        )
    )
    _reuse_committed_images(business_id, created["images"], paths)
    print(f"  Created product {seed.sku} with {len(files)} image(s)")


def seed_test_products() -> None:
    with TestClient(app) as client:
        admin_headers = _login(client, ADMIN_EMAIL)
        for seed in SEED_BUSINESSES:
            owner_id = _get_or_create_owner(seed)
            owner_headers = _login(client, seed.owner_email)
            business_id = _ensure_business(client, admin_headers, owner_headers, owner_id, seed)
            _enable_plugin(client, owner_headers, business_id)
            category_ids = _product_categories(client, owner_headers, business_id)
            existing = _existing_skus(client, owner_headers, business_id)
            print(f"{seed.name}: {len(existing)} existing product(s)")
            for product in seed.products:
                if product.sku not in existing:
                    _create_product(client, owner_headers, business_id, category_ids, product)


if __name__ == "__main__":
    seed_test_products()
