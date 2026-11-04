from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.business import Business, BusinessStatus
from app.models.business_plugin import BusinessPlugin, BusinessPluginStatus
from app.models.gis_village import GisVillage
from app.models.plugin import Plugin, PluginStatus
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import as_geography, point_from_coordinates


class BusinessPluginRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, business_id: UUID, plugin_id: UUID) -> BusinessPlugin | None:
        return self._db.scalar(
            select(BusinessPlugin).where(
                BusinessPlugin.business_id == business_id, BusinessPlugin.plugin_id == plugin_id
            )
        )

    def get_for_update(self, business_id: UUID, plugin_id: UUID) -> BusinessPlugin | None:
        return self._db.scalar(
            select(BusinessPlugin)
            .where(BusinessPlugin.business_id == business_id, BusinessPlugin.plugin_id == plugin_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def list_for_business(self, business_id: UUID) -> list[tuple[BusinessPlugin, Plugin]]:
        rows = self._db.execute(
            select(BusinessPlugin, Plugin)
            .join(Plugin, Plugin.id == BusinessPlugin.plugin_id)
            .where(BusinessPlugin.business_id == business_id)
            .order_by(Plugin.key.asc())
        ).all()
        return [(business_plugin, plugin) for business_plugin, plugin in rows]

    def list_nearby_serving(
        self, plugin_key: str, areas: Sequence[AreaPoint], radius_meters: float, limit: int
    ) -> list[tuple[Business, float]]:
        location = as_geography(Business.location)
        points = [as_geography(point_from_coordinates(a.latitude, a.longitude)) for a in areas]
        distance = func.least(*(func.ST_Distance(location, point) for point in points))
        rows = self._db.execute(
            select(Business, distance)
            .join(BusinessPlugin, BusinessPlugin.business_id == Business.id)
            .join(Plugin, Plugin.id == BusinessPlugin.plugin_id)
            .where(
                Plugin.key == plugin_key,
                Plugin.status == PluginStatus.ENABLED,
                BusinessPlugin.status == BusinessPluginStatus.ACTIVE,
                Business.status == BusinessStatus.ACTIVE,
                Business.deleted_at.is_(None),
                Business.location.is_not(None),
                or_(*(func.ST_DWithin(location, point, radius_meters) for point in points)),
            )
            .order_by(distance, Business.id)
            .limit(limit)
        ).all()
        return [(business, meters) for business, meters in rows]

    def list_serving_in_village(
        self, plugin_key: str, village_id: UUID, origin: AreaPoint, limit: int
    ) -> list[tuple[Business, float]]:
        location = as_geography(Business.location)
        distance = func.ST_Distance(
            location, as_geography(point_from_coordinates(origin.latitude, origin.longitude))
        )
        village_geometry = (
            select(GisVillage.geom).where(GisVillage.id == village_id).scalar_subquery()
        )
        rows = self._db.execute(
            select(Business, distance)
            .join(BusinessPlugin, BusinessPlugin.business_id == Business.id)
            .join(Plugin, Plugin.id == BusinessPlugin.plugin_id)
            .where(
                Plugin.key == plugin_key,
                Plugin.status == PluginStatus.ENABLED,
                BusinessPlugin.status == BusinessPluginStatus.ACTIVE,
                Business.status == BusinessStatus.ACTIVE,
                Business.deleted_at.is_(None),
                Business.location.is_not(None),
                func.ST_Contains(village_geometry, Business.location),
            )
            .order_by(distance, Business.id)
            .limit(limit)
        ).all()
        return [(business, meters) for business, meters in rows]

    def add_if_absent(self, business_plugin: BusinessPlugin) -> BusinessPlugin | None:
        inserted_id = self._db.scalar(
            pg_insert(BusinessPlugin)
            .values(
                business_id=business_plugin.business_id,
                plugin_id=business_plugin.plugin_id,
                status=business_plugin.status,
                enabled_by=business_plugin.enabled_by,
            )
            .on_conflict_do_nothing(index_elements=["business_id", "plugin_id"])
            .returning(BusinessPlugin.id)
        )
        self._db.commit()
        if inserted_id is None:
            return None
        return self._db.get_one(BusinessPlugin, inserted_id, populate_existing=True)

    def rollback(self) -> None:
        self._db.rollback()

    def save(self, business_plugin: BusinessPlugin) -> BusinessPlugin:
        self._db.commit()
        self._db.refresh(business_plugin)
        return business_plugin
