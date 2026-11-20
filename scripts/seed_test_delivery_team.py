from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.permissions import RoleSlug
from app.core.security import hash_password
from app.core.timezone import app_now
from app.models.business import Business
from app.models.delivery_request import DeliveryRequest, DeliveryRequestStatus
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_vehicle import DeliveryVehicle, VehicleType
from app.models.gis_village import GisVillage
from app.models.order import DeliveryOption, Order, OrderStatus, OrderType
from app.models.user import User, UserStatus, UserType
from app.models.user_has_role import user_has_roles
from app.repositories.role_repository import RoleRepository
from app.repositories.spatial import point_from_coordinates
from app.repositories.user_repository import UserRepository
from app.services.order_numbers import new_order_number
from scripts.seed import DEFAULT_USER_PASSWORD

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
EMAIL_DOMAIN = "delivery.nativelife.com"
SUPER_ADMIN_EMAIL = "dev@nativelife.com"
NATIVE_ADMIN_EMAIL = "native.admin@nativelife.com"
TEAM_MEMBERS_PER_PROMOTER = 2
ROUTE_LATITUDE_OFFSET = 0.02
ROUTE_COVERAGE_RADIUS_M = 2000
REQUEST_OPTIONS = (DeliveryOption.INSTANT, DeliveryOption.ROUTE)
REQUEST_EXPIRY = timedelta(hours=1)
ORDER_CURRENCY = "INR"
ORDER_TOTAL = Decimal("250.00")
CUSTOMER_PHONE = "+919876543210"


@dataclass(frozen=True)
class SeedPromoter:
    key: str
    first_name: str


PROMOTERS = (SeedPromoter("promoter1", "Asha"), SeedPromoter("promoter2", "Bala"))


def _email(local_part: str) -> str:
    return f"{local_part}@{EMAIL_DOMAIN}"


def _require_local_database() -> None:
    host = engine.url.host
    if host not in LOCAL_HOSTS:
        raise RuntimeError("Refusing to seed: DATABASE_URL does not point at a local database")


def _get_or_create_user(
    db: Session,
    email: str,
    first_name: str,
    last_name: str,
    role_slug: str,
    promoter_id: UUID | None = None,
    verified: bool = False,
) -> User:
    users = UserRepository(db)
    user = users.get_by_email(email)
    if user is not None:
        if user.account_role_selected_at is None:
            user.account_role_selected_at = app_now()
            users.save(user)
        print(f"Already exists: {email}")
        return user
    role = RoleRepository(db).get_by_slug(role_slug)
    if role is None:
        raise RuntimeError(f"Role '{role_slug}' does not exist. Run scripts/seed.py first.")
    user = users.add(
        User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=hash_password(DEFAULT_USER_PASSWORD),
            status=UserStatus.ACTIVE,
            user_type=UserType.PUBLIC,
            email_verified_at=app_now(),
            account_role_selected_at=app_now(),
            roles=[role],
            promoter_id=promoter_id,
        )
    )
    if verified:
        db.execute(
            update(user_has_roles)
            .where(user_has_roles.c.user_id == user.id, user_has_roles.c.role_id == role.id)
            .values(verified_at=app_now())
        )
        db.commit()
    print(f"Seeded {role_slug}: {email} / {DEFAULT_USER_PASSWORD}")
    return user


def _seed_courier_vehicle(db: Session, courier: User, number: int) -> DeliveryVehicle:
    name = f"{courier.first_name} {courier.last_name} vehicle"
    vehicle = db.scalar(
        select(DeliveryVehicle).where(
            DeliveryVehicle.user_id == courier.id, DeliveryVehicle.name == name
        )
    )
    if vehicle is None:
        vehicle = DeliveryVehicle(
            user_id=courier.id,
            vehicle_type=VehicleType.BIKE if number == 1 else VehicleType.VAN,
            name=name,
        )
        db.add(vehicle)
        db.commit()
        print(f"Seeded vehicle: {name}")
    return vehicle


def _retire_promoter_vehicles(db: Session, promoter: User) -> None:
    names = [f"{promoter.first_name} vehicle {number}" for number in (1, 2)]
    retired = db.scalars(
        select(DeliveryVehicle).where(
            DeliveryVehicle.user_id == promoter.id, DeliveryVehicle.name.in_(names)
        )
    ).all()
    for vehicle in retired:
        db.delete(vehicle)
    db.commit()
    if retired:
        print(f"Removed {len(retired)} old Promoter-owned vehicle(s) of {promoter.email}")


def _use_courier_vehicle(
    db: Session, promoter: User, route: DeliveryRoute, courier: User, vehicle: DeliveryVehicle
) -> None:
    current = db.get(DeliveryVehicle, route.vehicle_id) if route.vehicle_id else None
    if route.courier_id == courier.id and (current is None or current.user_id == promoter.id):
        route.vehicle_id = vehicle.id
        db.commit()


def _seed_route(
    db: Session, promoter: User, courier: User, vehicle: DeliveryVehicle
) -> DeliveryRoute | None:
    name = f"{promoter.first_name} morning route"
    existing = db.scalar(
        select(DeliveryRoute).where(
            DeliveryRoute.user_id == promoter.id, DeliveryRoute.name == name
        )
    )
    if existing is not None:
        if existing.start_label is None and existing.end_label is None:
            existing.start_label = f"{promoter.first_name} route start"
            existing.end_label = f"{promoter.first_name} route end"
            db.commit()
        print(f"Already exists: route {name}")
        return existing
    village = db.execute(
        select(
            GisVillage.id,
            func.ST_Y(func.ST_PointOnSurface(GisVillage.geom)),
            func.ST_X(func.ST_PointOnSurface(GisVillage.geom)),
        ).limit(1)
    ).first()
    if village is None:
        print("No GIS villages found; skipping route seeding. Run scripts/seed_locations.py.")
        return None
    village_id, latitude, longitude = village
    route = DeliveryRoute(
        user_id=promoter.id,
        village_id=village_id,
        vehicle_id=vehicle.id,
        courier_id=courier.id,
        name=name,
        start_label=f"{promoter.first_name} route start",
        end_label=f"{promoter.first_name} route end",
        start_point=point_from_coordinates(latitude, longitude),
        end_point=point_from_coordinates(latitude + ROUTE_LATITUDE_OFFSET, longitude),
        coverage_radius_m=ROUTE_COVERAGE_RADIUS_M,
    )
    db.add(route)
    db.commit()
    print(f"Seeded route: {name} (courier {courier.email}, vehicle {vehicle.name})")
    return route


def _confirm_seeded_orders(db: Session, route: DeliveryRoute) -> None:
    seeded_orders = select(DeliveryRequest.order_id).where(DeliveryRequest.route_id == route.id)
    db.execute(
        update(Order)
        .where(Order.id.in_(seeded_orders), Order.status == OrderStatus.PENDING)
        .values(status=OrderStatus.CONFIRMED)
    )
    db.commit()


def _seed_requests(db: Session, promoter: User, route: DeliveryRoute, customer: User) -> None:
    existing = db.scalar(
        select(func.count())
        .select_from(DeliveryRequest)
        .where(DeliveryRequest.route_id == route.id)
    )
    business_id = db.scalar(select(Business.id).limit(1))
    if existing or business_id is None:
        print(f"Skipping delivery requests for route {route.name} (already seeded or no business)")
        return
    now = app_now()
    for offset, option in enumerate(REQUEST_OPTIONS):
        order = Order(
            order_number=new_order_number(db),
            order_type=OrderType.DIRECT,
            business_id=business_id,
            customer_id=customer.id,
            promoter_id=promoter.id,
            delivery_option=option,
            expected_delivery_date=(now + timedelta(days=offset)).date(),
            status=OrderStatus.CONFIRMED,
            customer_name=f"{customer.first_name} {customer.last_name}",
            customer_phone=CUSTOMER_PHONE,
            shipping_address=f"{route.name} stop {offset + 1}",
            shipping_location=point_from_coordinates(
                route.start_latitude + ROUTE_LATITUDE_OFFSET / 2, route.start_longitude
            ),
            currency=ORDER_CURRENCY,
            total_amount=ORDER_TOTAL,
        )
        db.add(order)
        db.flush()
        db.add(
            DeliveryRequest(
                order_id=order.id,
                option=option,
                delivery_date=(now + timedelta(days=offset)).date(),
                route_id=route.id,
                promoter_id=promoter.id,
                status=DeliveryRequestStatus.ACCEPTED,
                expires_at=now + REQUEST_EXPIRY,
                decided_at=now,
            )
        )
    db.commit()
    print(f"Seeded {len(REQUEST_OPTIONS)} delivery requests on route {route.name}")


def seed_test_delivery_team() -> None:
    _require_local_database()
    db = SessionLocal()
    try:
        _get_or_create_user(db, SUPER_ADMIN_EMAIL, "Dev", "Super Admin", RoleSlug.SUPER_ADMIN)
        _get_or_create_user(db, NATIVE_ADMIN_EMAIL, "Dev", "Native Admin", RoleSlug.NATIVE_ADMIN)
        customer = _get_or_create_user(
            db, _email("customer"), "Dev", "Customer", RoleSlug.INDIVIDUAL_USER
        )
        for seed in PROMOTERS:
            promoter = _get_or_create_user(
                db,
                _email(seed.key),
                seed.first_name,
                "Promoter",
                RoleSlug.PROMOTER,
                verified=True,
            )
            couriers = [
                _get_or_create_user(
                    db,
                    _email(f"{seed.key}.courier{number}"),
                    f"{seed.first_name} courier",
                    str(number),
                    RoleSlug.DELIVERY_TEAM,
                    promoter_id=promoter.id,
                )
                for number in range(1, TEAM_MEMBERS_PER_PROMOTER + 1)
            ]
            vehicles = [
                _seed_courier_vehicle(db, courier, number)
                for number, courier in enumerate(couriers, start=1)
            ]
            route = _seed_route(db, promoter, couriers[0], vehicles[0])
            if route is not None:
                _use_courier_vehicle(db, promoter, route, couriers[0], vehicles[0])
                _seed_requests(db, promoter, route, customer)
                _confirm_seeded_orders(db, route)
            _retire_promoter_vehicles(db, promoter)
        _get_or_create_user(
            db, _email("unverified.promoter"), "Chitra", "Promoter", RoleSlug.PROMOTER
        )
        _get_or_create_user(db, _email("individual"), "Dev", "Individual", RoleSlug.INDIVIDUAL_USER)
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_delivery_team()
