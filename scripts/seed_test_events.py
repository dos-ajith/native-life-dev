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
from app.models.event import Event
from app.models.event_image import EventImage
from app.models.user import User
from app.repositories.event_image_repository import EventImageRepository
from app.schemas.event import EventCreate
from app.services.event_service import EventService
from scripts.seed_locations import SeedLocations
from scripts.seed_test_posts import seed_users

EVENTS_ROOT_CATEGORY = "Events"
EVENTS_PER_USER = 3
FIRST_EVENT_DAY_OFFSET = 2
DAYS_BETWEEN_EVENTS = 2
MIN_IMAGES_PER_EVENT = 3
MAX_IMAGES_PER_EVENT = 5
SAMPLE_IMAGES_SUBDIR = "sample_images"
LOCATION_SEED_OFFSET = 5000


@dataclass(frozen=True)
class EventTemplate:
    category: str
    title: str
    venue: str
    start_hour: int
    duration_hours: int
    description: str


EVENT_TEMPLATES = (
    EventTemplate(
        "Festival",
        "Temple utsavam and cultural night in {district}",
        "Sree Mahadeva Temple Grounds, {district}",
        17,
        5,
        "The annual temple utsavam in {district} returns with a grand evening of chenda melam, "
        "kathakali and a decorated elephant procession around the temple grounds.\n\n"
        "Food stalls run by the local committee will serve payasam, snacks and evening tea. "
        "Families are welcome and there is a separate area for children near the pond side. "
        "Parking is available at the government school ground, and volunteers will guide "
        "traffic on the main road. Please carry water and avoid bringing plastic to the venue.",
    ),
    EventTemplate(
        "Festival",
        "Onam pookalam competition and sadya in {district}",
        "Town Hall Grounds, {district}",
        9,
        6,
        "Celebrate Onam with neighbours in {district}! The day opens with a pookalam competition "
        "for teams of up to five, followed by tug of war, uriyadi and other traditional games.\n\n"
        "A full Onam sadya will be served at noon on banana leaves. Registration for the "
        "pookalam competition closes two days before the event, and teams should bring their "
        "own flowers. Prizes for the top three teams will be given at the closing ceremony.",
    ),
    EventTemplate(
        "Celebration",
        "Kerala Piravi celebration evening in {district}",
        "Municipal Open Auditorium, {district}",
        16,
        4,
        "Join us to celebrate Kerala Piravi in {district} with an evening of music, dance and "
        "stories about our state's history and culture.\n\n"
        "Students from local schools will perform mohiniyattam, thiruvathira and folk songs. "
        "There will be a short quiz on Kerala history with prizes for all age groups. Light "
        "refreshments will be provided. Entry is free and everyone is welcome to attend.",
    ),
    EventTemplate(
        "Celebration",
        "Christmas carol night and cake fest in {district}",
        "St. Mary's Parish Hall, {district}",
        18,
        4,
        "Get into the festive mood with a carol night in {district}. Choirs from nearby "
        "parishes and schools will perform classic carols and Malayalam Christmas songs.\n\n"
        "Home bakers will set up stalls with plum cakes, wine-free fruit cakes and cookies. "
        "Santa will be visiting the kids around 8 PM with small gifts. Bring your family and "
        "friends for a warm evening of music, lights and good food.",
    ),
    EventTemplate(
        "Community",
        "Neighbourhood clean-up drive in {district}",
        "Panchayat Office Junction, {district}",
        7,
        3,
        "Let's keep {district} clean together! We are organising a neighbourhood clean-up drive "
        "covering the main road, the bus stand and the canal side.\n\n"
        "Gloves, bags and refreshments will be provided by the residents' association. "
        "Collected plastic will be handed over to the Haritha Karma Sena for recycling. "
        "Students can get volunteer certificates for participating. Please wear comfortable "
        "shoes and bring a water bottle.",
    ),
    EventTemplate(
        "Community",
        "Free medical camp and blood donation drive in {district}",
        "Government LP School, {district}",
        8,
        6,
        "A free medical camp is being held in {district} with general physicians, "
        "eye specialists and dental doctors available for consultation.\n\n"
        "Basic tests like blood sugar, blood pressure and BMI will be done on the spot, and "
        "medicines will be given free for common conditions. A blood donation drive will run "
        "alongside the camp; donors should be healthy, above 18 and should have eaten "
        "before donating. Please bring any previous medical records you have.",
    ),
    EventTemplate(
        "Activity",
        "Sunrise trek and nature walk near {district}",
        "Forest Check Post, {district}",
        5,
        5,
        "Join a guided sunrise trek near {district} for beautiful views of the valley and "
        "the chance to spot birds and butterflies along the trail.\n\n"
        "The trail is moderate and suitable for beginners with basic fitness. A forest guide "
        "will accompany the group and explain the local plants and wildlife. Wear good shoes, "
        "carry water and a light snack, and avoid plastic on the trail. Limited to 30 people, "
        "so register early.",
    ),
    EventTemplate(
        "Activity",
        "Weekend football tournament in {district}",
        "Municipal Stadium, {district}",
        15,
        5,
        "Calling all football lovers in {district}! A weekend sevens tournament is open for "
        "local clubs and friends' teams.\n\n"
        "Each team can register up to ten players, and matches will run in a knockout format "
        "through the afternoon. Trophies and cash prizes for the winners and runners-up, plus "
        "a best player award. Spectators are welcome, and there will be snacks and juice "
        "stalls near the gallery.",
    ),
)


def _category_ids(db: Session) -> dict[str, UUID]:
    root = aliased(Category)
    rows = db.execute(
        select(Category.name, Category.id)
        .join(root, root.id == Category.parent_id)
        .where(root.name == EVENTS_ROOT_CATEGORY)
    ).all()
    ids = {name: category_id for name, category_id in rows}
    missing = {template.category for template in EVENT_TEMPLATES} - ids.keys()
    if missing:
        raise RuntimeError(f"Missing event categories: {sorted(missing)}")
    return ids


def _sample_image_urls(upload_dir: str) -> list[str]:
    directory = Path(upload_dir) / SAMPLE_IMAGES_SUBDIR
    names = sorted(path.name for path in directory.glob("*.jpg"))
    if not names:
        raise RuntimeError(f"No sample images found in {directory}")
    return [f"{MEDIA_URL_PREFIX}/{SAMPLE_IMAGES_SUBDIR}/{name}" for name in names]


def _already_seeded(db: Session, users: list[User]) -> bool:
    user_ids = [user.id for user in users]
    return db.scalar(select(Event.id).where(Event.user_id.in_(user_ids)).limit(1)) is not None


def _attach_images(images: EventImageRepository, event_id: UUID, urls: list[str]) -> None:
    count = random.randint(MIN_IMAGES_PER_EVENT, min(MAX_IMAGES_PER_EVENT, len(urls)))
    for sort_order, url in enumerate(random.sample(urls, count)):
        images.add(EventImage(event_id=event_id, image_url=url, sort_order=sort_order))


def _seed_events(db: Session, users: list[User], upload_dir: str) -> None:
    locations = SeedLocations(db, LOCATION_SEED_OFFSET)
    category_ids = _category_ids(db)
    image_urls = _sample_image_urls(upload_dir)
    events = EventService(db)
    images = EventImageRepository(db)
    today = app_now().replace(minute=0, second=0, microsecond=0)
    for user_index, user in enumerate(users):
        for event_index in range(EVENTS_PER_USER):
            sequence = user_index * EVENTS_PER_USER + event_index
            template = EVENT_TEMPLATES[sequence % len(EVENT_TEMPLATES)]
            spot = locations.spot(sequence)
            day_offset = FIRST_EVENT_DAY_OFFSET + sequence * DAYS_BETWEEN_EVENTS
            starts_at = (today + timedelta(days=day_offset)).replace(hour=template.start_hour)
            payload = EventCreate(
                category_id=category_ids[template.category],
                title=template.title.format(district=spot.district_name),
                description=template.description.format(district=spot.district_name),
                venue_name=template.venue.format(district=spot.district_name),
                latitude=spot.latitude,
                longitude=spot.longitude,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=template.duration_hours),
            )
            event = events.create(payload, [], [], upload_dir, user)
            _attach_images(images, event.id, image_urls)
    print(f"Seeded {len(users) * EVENTS_PER_USER} test events")


def seed_test_events() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        if _already_seeded(db, users):
            print("Test events already exist; skipping")
            return
        _seed_events(db, users, get_settings().upload_dir)
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_events()
