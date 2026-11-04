from dataclasses import dataclass

from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import BusinessRuleError
from app.core.permissions import RoleSlug
from app.core.security import hash_password
from app.core.timezone import app_now
from app.models.gis_district import GisDistrict
from app.models.post import PostStatus
from app.models.user import User, UserStatus, UserType
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.post import PostCreate
from app.services.post_service import PostService
from app.services.tag_service import TagService
from scripts.seed import DEFAULT_USER_PASSWORD

POSTS_PER_USER = 10
TEST_EMAIL_DOMAIN = "test.nativelife.com"


@dataclass(frozen=True)
class TestUser:
    first_name: str
    last_name: str
    phone: str


@dataclass(frozen=True)
class CategoryTemplate:
    tag: str
    title: str
    content: str


TEST_USERS = (
    TestUser("Arjun", "Nair", "+919400000001"),
    TestUser("Meera", "Menon", "+919400000002"),
    TestUser("Rahul", "Pillai", "+919400000003"),
    TestUser("Anjali", "Varghese", "+919400000004"),
    TestUser("Fahad", "Rahman", "+919400000005"),
    TestUser("Lakshmi", "Krishnan", "+919400000006"),
    TestUser("Joseph", "Kurian", "+919400000007"),
    TestUser("Nisha", "Thomas", "+919400000008"),
    TestUser("Vishnu", "Das", "+919400000009"),
    TestUser("Sneha", "Mathew", "+919400000010"),
)

CATEGORY_TEMPLATES = (
    CategoryTemplate(
        "Travel",
        "Weekend getaway spots around {district}",
        "Spent the last weekend exploring the quieter corners around {district} and it was "
        "worth every minute. We started early, reached the backwaters just after sunrise "
        "and had the whole stretch almost to ourselves.\n\n"
        "From there we drove up to a small hill viewpoint where the mist was still hanging "
        "over the valley. A local tea shop at the top served the best chai and pazhampori "
        "we had all trip. Later we stopped at a village temple pond and a small waterfall "
        "that only flows properly after the rains.\n\n"
        "Tip for anyone planning a visit: leave before 7 AM, carry water and cash, and "
        "avoid long weekends when the roads get packed. Happy to share the exact route if "
        "anyone needs it.",
    ),
    CategoryTemplate(
        "Food",
        "Must-try local eats in {district}",
        "Found a small family-run hotel in {district} that deserves a lot more attention. "
        "No fancy board, just a few plastic chairs and a kitchen that smells amazing from "
        "the road.\n\n"
        "Their appam and chicken stew are soft, mildly spiced and very homely. For lunch "
        "the meals come on a banana leaf with sambar, avial, thoran, pickle and a crispy "
        "pappadam, and they keep refilling without asking. The evening special is kappa "
        "with fish curry, which sells out by 8 PM most days.\n\n"
        "Prices are surprisingly affordable and everything is cooked fresh in small "
        "batches. Parking is limited, so go by two-wheeler if you can. If you are around "
        "{district}, skip the big chains once and try places like this.",
    ),
    CategoryTemplate(
        "Automobile",
        "Reliable bike and car service centres in {district}",
        "Got my car and my brother's bike serviced in {district} this week and both "
        "experiences were better than expected, so sharing for anyone looking for a "
        "trustworthy garage.\n\n"
        "They gave a clear estimate upfront, called before replacing any part and showed us "
        "the old parts after the work. Genuine spares were used and the bill matched the "
        "estimate almost exactly. The bike was ready the same evening and the car took a "
        "day because of a wheel alignment issue they spotted.\n\n"
        "Book an appointment a day earlier to avoid waiting, especially before festival "
        "season. They also offer pickup and drop within the town for a small charge, which "
        "is handy if you are busy on weekdays.",
    ),
    CategoryTemplate(
        "Electronics",
        "Best electronics deals this month in {district}",
        "Festival offers on phones, laptops and home appliances are now live across most "
        "shops in {district}. I went around comparing prices this weekend and the "
        "differences between stores were bigger than I expected.\n\n"
        "Some shops are giving extra exchange value for old phones, while others offer free "
        "extended warranty or no-cost EMI on selected cards. A few appliance stores are "
        "bundling free installation for ACs and washing machines, which adds up to real "
        "savings.\n\n"
        "Before buying, check the online price, ask for the final on-road bill including "
        "GST and confirm warranty terms in writing. Also ask whether the model is the "
        "latest version, since some older stock is being cleared at the same tag price.",
    ),
    CategoryTemplate(
        "Health",
        "Morning walking trails and wellness spots in {district}",
        "Looking for a peaceful place to walk or jog in {district}? There is a lovely route "
        "along the canal side that stays shaded until around 8 AM and is mostly free from "
        "traffic.\n\n"
        "Plenty of regulars use it, so it feels safe even early in the morning. Halfway "
        "along there is a small open ground where a group does free yoga sessions on "
        "weekends, and anyone can join. There are also benches and a drinking water point "
        "near the temple junction.\n\n"
        "A couple of Ayurveda centres nearby offer weekend wellness packages with massage "
        "and steam bath at reasonable rates. If you are starting fresh, begin with 20 "
        "minutes a day and build up slowly. Consistency matters more than speed.",
    ),
    CategoryTemplate(
        "Education",
        "Coaching and skill classes worth joining in {district}",
        "New batches for entrance coaching, spoken English and computer courses are "
        "starting next month in {district}. I checked out a few centres for my cousin and "
        "wanted to share what we learned.\n\n"
        "The better institutes offer a free demo class, keep batch sizes small and share "
        "past results openly. Weekend and evening batches are available for working "
        "professionals, and some places also run online sessions with recorded classes for "
        "revision.\n\n"
        "Before paying, ask about the refund policy, the trainer's experience and whether "
        "study material is included in the fee. Talking to current students outside the "
        "centre gave us the most honest feedback. Admissions fill quickly, so enquire early "
        "if you are interested.",
    ),
    CategoryTemplate(
        "Real Estate",
        "Plots and rental homes trending in {district}",
        "Demand for rental homes in {district} has clearly picked up over the last few "
        "months, especially for two-bedroom houses close to schools and bus routes.\n\n"
        "Residential plots near the main road are getting enquiries fast, and prices in "
        "some areas have gone up noticeably since last year. Interior plots with a decent "
        "access road are still reasonably priced and worth considering for long-term "
        "buyers.\n\n"
        "If you are planning to buy, verify the title deed, possession certificate and "
        "encumbrance details with a lawyer before paying any advance. For renters, agree on "
        "the deposit, maintenance and notice period in writing. Visiting the area in the "
        "evening also tells you a lot about water, lighting and traffic.",
    ),
    CategoryTemplate(
        "Events",
        "Upcoming festivals and events in {district}",
        "Temple festival season has started and there are a lot of cultural programs lined "
        "up in {district} this month. Expect chenda melam, kathakali, thiruvathira and a "
        "big procession on the main day.\n\n"
        "The local committee has announced a food and craft fair near the grounds as well, "
        "with stalls from nearby panchayats selling snacks, handloom and handicrafts. There "
        "is also a small music program by school students on the opening evening.\n\n"
        "Traffic will be diverted near the venue during the evenings, so plan your travel "
        "early and use public transport if possible. Parking will be available at the "
        "school ground. Keep an eye on the notice board for the final schedule.",
    ),
    CategoryTemplate(
        "Fashion",
        "Handloom and festive shopping picks in {district}",
        "Traditional kasavu sarees, set mundu and handloom shirts are on sale across "
        "several shops in {district} ahead of the festival and wedding season.\n\n"
        "The weaving cooperative outlet has the best range of pure handloom with genuine "
        "zari, and prices are fair compared to big showrooms. Smaller boutiques are "
        "offering custom stitching for blouses and kurtas with quick delivery if you order "
        "in advance.\n\n"
        "Check the handloom mark and fabric quality before buying, and ask for the washing "
        "instructions, since pure cotton needs a little care. Buying directly from weavers "
        "also supports local families who keep this craft alive. Shops get very crowded on "
        "weekends, so weekday mornings are best.",
    ),
    CategoryTemplate(
        "Agriculture",
        "Fresh farm produce and nursery plants in {district}",
        "The weekly farmers' market in {district} is back and better than ever. Local "
        "farmers are selling organic vegetables, bananas, tapioca and fresh greens "
        "directly, without any middlemen.\n\n"
        "There is a good nursery section too, with coconut, arecanut and banana seedlings, "
        "along with fruit plants like rambutan, mangosteen and dwarf mango. The agriculture "
        "office has a small counter offering free advice on pest control, composting and "
        "grow-bag farming for home gardens.\n\n"
        "Come early since the best produce sells out by mid-morning, and bring your own "
        "bags. Prices are fair and you know exactly where your food comes from. A great way "
        "to support small farmers in the area while eating healthier.",
    ),
)


def seed_users(db: Session) -> list[User]:
    users = UserRepository(db)
    role = RoleRepository(db).get_by_slug(RoleSlug.INDIVIDUAL_USER)
    if role is None:
        raise RuntimeError(
            f"Role '{RoleSlug.INDIVIDUAL_USER}' does not exist. Run scripts/seed.py first."
        )

    seeded: list[User] = []
    for test_user in TEST_USERS:
        email = f"{test_user.first_name.lower()}.{test_user.last_name.lower()}@{TEST_EMAIL_DOMAIN}"
        user = users.get_by_email(email)
        if user is None:
            user = users.add(
                User(
                    first_name=test_user.first_name,
                    last_name=test_user.last_name,
                    email=email,
                    phone=test_user.phone,
                    password_hash=hash_password(DEFAULT_USER_PASSWORD),
                    status=UserStatus.ACTIVE,
                    user_type=UserType.PUBLIC,
                    email_verified_at=app_now(),
                    roles=[role],
                )
            )
            print(f"Seeded test user: {email} / {DEFAULT_USER_PASSWORD}")
        else:
            print(f"Test user already exists: {email}")
        seeded.append(user)
    return seeded


def random_point_in_district(db: Session, district: GisDistrict, seed: int) -> tuple[float, float]:
    point = db.scalar(
        select(func.ST_GeometryN(func.ST_GeneratePoints(GisDistrict.geom, 1, seed), 1)).where(
            GisDistrict.id == district.id
        )
    )
    shape = to_shape(point)
    return shape.y, shape.x


def _seed_posts(db: Session, users: list[User]) -> None:
    districts = list(db.scalars(select(GisDistrict).order_by(GisDistrict.name)))
    if not districts:
        raise RuntimeError("No districts found. Import geography first.")

    posts = PostService(db)
    tags = TagService(db)
    created = 0
    for user_index, user in enumerate(users):
        for post_index in range(POSTS_PER_USER):
            sequence = user_index * POSTS_PER_USER + post_index
            district = districts[sequence % len(districts)]
            template = CATEGORY_TEMPLATES[post_index % len(CATEGORY_TEMPLATES)]
            latitude, longitude = random_point_in_district(db, district, sequence + 1)
            payload = PostCreate(
                title=template.title.format(district=district.name),
                content=template.content.format(district=district.name),
                status=PostStatus.PUBLISHED,
                latitude=latitude,
                longitude=longitude,
                tags=[template.tag, district.name, "Kerala"],
            )
            try:
                post = posts.create(payload, user)
            except BusinessRuleError:
                continue
            tags.set_post_tags(post.id, payload.tags or [], user)
            created += 1
    print(f"Seeded {created} published test posts")


def seed_test_posts() -> None:
    db = SessionLocal()
    try:
        users = seed_users(db)
        _seed_posts(db, users)
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_posts()
