import math
import random
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gis_district import GisDistrict
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.models.user_native_place import UserNativePlace
from app.repositories.gis_village_repository import GisVillageRepository
from scripts.seed_test_posts import random_point_in_district

NATIVE_SCATTER_KM = 20
KM_PER_DEGREE_LATITUDE = 111.32
FULL_CIRCLE_DEGREES = 360


@dataclass(frozen=True)
class SeedSpot:
    district_name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class NativeAnchor:
    district_name: str
    latitude: float
    longitude: float


class SeedLocations:
    def __init__(self, db: Session, seed_offset: int) -> None:
        self._db = db
        self._seed_offset = seed_offset
        self._districts = list(db.scalars(select(GisDistrict).order_by(GisDistrict.name)))
        if not self._districts:
            raise RuntimeError("No districts found. Import geography first.")
        self._anchors = self._native_anchors()

    def spot(self, sequence: int) -> SeedSpot:
        if self._anchors and sequence % 2 == 0:
            anchor = self._anchors[(sequence // 2) % len(self._anchors)]
            latitude, longitude = _scatter(anchor.latitude, anchor.longitude, NATIVE_SCATTER_KM)
            return SeedSpot(anchor.district_name, latitude, longitude)
        district = self._districts[sequence % len(self._districts)]
        latitude, longitude = random_point_in_district(
            self._db, district, sequence + self._seed_offset
        )
        return SeedSpot(district.name, latitude, longitude)

    def _native_anchors(self) -> list[NativeAnchor]:
        rows = self._db.execute(
            select(GisVillage.id, GisDistrict.name)
            .join(UserNativePlace, UserNativePlace.village_id == GisVillage.id)
            .join(GisTaluk, GisTaluk.id == GisVillage.taluk_id)
            .join(GisDistrict, GisDistrict.id == GisTaluk.district_id)
            .distinct()
        ).all()
        villages = GisVillageRepository(self._db)
        anchors: list[NativeAnchor] = []
        for village_id, district_name in rows:
            point = villages.get_representative_point(village_id)
            if point is not None:
                anchors.append(NativeAnchor(district_name, point[0], point[1]))
        return anchors


def _scatter(latitude: float, longitude: float, max_km: float) -> tuple[float, float]:
    distance_km = max_km * math.sqrt(random.random())
    bearing = math.radians(random.uniform(0, FULL_CIRCLE_DEGREES))
    delta_latitude = distance_km * math.cos(bearing) / KM_PER_DEGREE_LATITUDE
    delta_longitude = (
        distance_km
        * math.sin(bearing)
        / (KM_PER_DEGREE_LATITUDE * math.cos(math.radians(latitude)))
    )
    return latitude + delta_latitude, longitude + delta_longitude
