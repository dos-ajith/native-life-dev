import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select, update
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
from app.repositories.role_repository import RoleRepository
from scripts.seed import DEFAULT_USER_PASSWORD

ADMIN_EMAIL = "dev@nativelife.com"
PLUGIN_KEY = "ecommerce"
API_PREFIX = get_settings().api_v1_prefix
COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
HTTP_HEADERS = {
    "User-Agent": "NativeLifeDevSeed/1.0 (mailto:dev@nativelife.com; product test images)"
}
HTTP_TIMEOUT_SECONDS = 60
IMAGE_WIDTH = 800
REQUEST_PAUSE_SECONDS = 2
RATE_LIMIT_BACKOFF_SECONDS = 20
MAX_DOWNLOAD_ATTEMPTS = 4
ACCEPTED_IMAGE_TYPES = ("image/jpeg", "image/png")
SEARCH_RESULT_LIMIT = 8
TEST_EMAIL_DOMAIN = "test.nativelife.com"
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
    image_queries: tuple[str, ...]
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
                ("USB charger wall adapter", "USB-C charger"),
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
                ("power bank portable charger",),
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
                ("earphones headphones in-ear",),
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
                ("bluetooth speaker portable",),
                individual=True,
            ),
            SeedProduct(
                "ELEC-USB-CABLE",
                "USB-C Cable 1m",
                "Braided 1 metre USB-C charging and data cable.",
                "149.00",
                "249.00",
                150,
                "Electronics",
                ("USB-C cable",),
                bulk=True,
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
                "FASH-SAREE-KASAVU",
                "Kasavu Saree",
                "Traditional cream and gold kasavu cotton saree.",
                "1850.00",
                "2400.00",
                30,
                "Apparel",
                ("Kasavu saree Kerala",),
                individual=True,
            ),
            SeedProduct(
                "FASH-MUNDU-SET",
                "Cotton Mundu Set",
                "Handloom double mundu for festive and daily wear.",
                "950.00",
                "1200.00",
                45,
                "Apparel",
                ("mundu Kerala dress",),
                bulk=True,
            ),
            SeedProduct(
                "FASH-TSHIRT-COT",
                "Cotton T-Shirt",
                "Soft combed cotton round-neck t-shirt.",
                "349.00",
                "599.00",
                120,
                "Apparel",
                ("cotton t-shirt folded",),
                bulk=True,
                individual=True,
            ),
            SeedProduct(
                "FASH-SHAWL-WOOL",
                "Woollen Shawl",
                "Warm woollen shawl with woven border.",
                "799.00",
                "1099.00",
                20,
                "Apparel",
                ("woollen shawl",),
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
                ("coconut oil bottle",),
                bulk=True,
                individual=True,
            ),
            SeedProduct(
                "GROC-MATTA-RICE-5KG",
                "Kuttanad Matta Rice 5kg",
                "Red matta rice from Kuttanad, 5 kg pack.",
                "420.00",
                "520.00",
                60,
                "Groceries",
                ("red rice matta",),
                bulk=True,
            ),
            SeedProduct(
                "GROC-EGGS-TRAY",
                "Country Eggs Tray (30)",
                "Farm-fresh country eggs, tray of 30.",
                "199.00",
                "240.00",
                40,
                "Groceries",
                ("tray of eggs",),
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
                ("black pepper peppercorns",),
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
                ("banana chips Kerala",),
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
                "HOME-URULI-BRASS",
                "Brass Uruli",
                "Traditional Kerala brass uruli for decor and cooking.",
                "2200.00",
                "2800.00",
                15,
                "Home & Kitchen",
                ("uruli brass Kerala",),
                individual=True,
            ),
            SeedProduct(
                "HOME-CLAY-POT",
                "Clay Cooking Pot",
                "Handmade clay pot for fish curry and slow cooking.",
                "450.00",
                "600.00",
                50,
                "Home & Kitchen",
                ("clay cooking pot",),
                bulk=True,
            ),
            SeedProduct(
                "HOME-COIR-MAT",
                "Coir Door Mat",
                "Durable natural coir door mat.",
                "249.00",
                "349.00",
                100,
                "Home & Kitchen",
                ("coir door mat",),
                bulk=True,
                individual=True,
            ),
            SeedProduct(
                "BEAUTY-SOAP-SANDAL",
                "Sandalwood Soap Pack of 3",
                "Natural sandalwood bath soap, pack of three.",
                "240.00",
                "300.00",
                85,
                "Beauty & Personal Care",
                ("sandalwood soap",),
                individual=True,
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


def _get_with_retry(client: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
    for attempt in range(MAX_DOWNLOAD_ATTEMPTS):
        try:
            response = client.get(url, **kwargs)
        except httpx.TransportError:
            time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
            continue
        if response.status_code != httpx.codes.TOO_MANY_REQUESTS:
            response.raise_for_status()
            return response
        time.sleep(RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1))
    return client.get(url, **kwargs).raise_for_status()


def _download_image(client: httpx.Client, query: str, used: set[str]) -> tuple[bytes, str] | None:
    search = _get_with_retry(
        client,
        COMMONS_API_URL,
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrlimit": SEARCH_RESULT_LIMIT,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "iiurlwidth": IMAGE_WIDTH,
        },
    )
    time.sleep(REQUEST_PAUSE_SECONDS)
    pages = sorted(
        search.json().get("query", {}).get("pages", {}).values(), key=lambda page: page["index"]
    )
    for page in pages:
        info = page["imageinfo"][0]
        if info["mime"] not in ACCEPTED_IMAGE_TYPES or info["url"] in used:
            continue
        response = _get_with_retry(client, info.get("thumburl") or info["url"])
        time.sleep(REQUEST_PAUSE_SECONDS)
        used.add(info["url"])
        return response.content, response.headers["content-type"].split(";")[0]
    return None


def _image_files(
    http: httpx.Client, queries: tuple[str, ...], used: set[str]
) -> list[tuple[str, tuple[str, bytes, str]]]:
    files = []
    for query in queries:
        image = _download_image(http, query, used)
        if image is None:
            print(f"  no image found for '{query}'")
            continue
        contents, content_type = image
        files.append(("images", (f"{len(files)}.jpg", contents, content_type)))
    return files


def _create_product(
    client: TestClient,
    http: httpx.Client,
    owner_headers: dict[str, str],
    business_id: UUID,
    category_ids: dict[str, str],
    seed: SeedProduct,
    used: set[str],
) -> None:
    files = _image_files(http, seed.image_queries, used)
    form = {
        "name": seed.name,
        "sku": seed.sku,
        "description": seed.description,
        "selling_price": str(Decimal(seed.selling_price)),
        "original_price": str(Decimal(seed.original_price)),
        "category_id": category_ids[seed.category],
        "quantity": str(seed.quantity),
        "low_stock_threshold": str(LOW_STOCK_THRESHOLD),
        "is_bulk_promotable": str(seed.bulk).lower(),
        "is_individually_promotable": str(seed.individual).lower(),
    }
    _data(
        client.post(
            _plugin_url(business_id, "products"), headers=owner_headers, data=form, files=files
        )
    )
    print(f"  Created product {seed.sku} with {len(files)} image(s)")


def seed_test_products() -> None:
    used_images: set[str] = set()
    with (
        TestClient(app) as client,
        httpx.Client(
            headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True
        ) as http,
    ):
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
                    _create_product(
                        client, http, owner_headers, business_id, category_ids, product, used_images
                    )


if __name__ == "__main__":
    seed_test_products()
