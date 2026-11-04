from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.business_categories import BusinessCategorySlug
from app.models.business import BusinessStatus
from app.models.business_plugin import BusinessPlugin, BusinessPluginStatus
from app.models.category import Category
from app.models.plugin import Plugin, PluginBusinessType
from app.models.user import User
from app.plugins.manifest import CAPABILITY_PATH_PLACEHOLDER, CapabilityType
from app.schemas.base import BaseReadSchema
from app.services.business_plugin_service import (
    BusinessPluginOverview,
    PluginOffer,
    visible_capabilities,
)


class ApplicableCategoryRead(BaseModel):
    id: UUID
    slug: str
    name: str

    @classmethod
    def from_category(cls, category: Category) -> "ApplicableCategoryRead":
        return cls(id=category.id, slug=category.slug, name=category.name)


class PluginCapabilityRead(BaseModel):
    key: str
    title: str
    type: CapabilityType
    path: str


class AvailablePluginRead(BaseModel):
    key: str
    name: str
    version: str
    business_type: PluginBusinessType
    description: str | None
    enabled_for_business: bool

    @classmethod
    def from_offer(cls, offer: PluginOffer) -> "AvailablePluginRead":
        return cls(
            key=offer.plugin.key,
            name=offer.plugin.name,
            version=offer.plugin.version,
            business_type=offer.plugin.business_type,
            description=offer.manifest.plugin.description,
            enabled_for_business=offer.enabled_for_business,
        )


class EnabledPluginRead(BaseReadSchema):
    key: str
    name: str
    version: str
    enabled_by: UUID | None
    enabled_at: datetime
    capabilities: list[PluginCapabilityRead]

    @classmethod
    def from_offer(
        cls,
        offer: PluginOffer,
        business_plugin: BusinessPlugin,
        viewer: User,
        api_prefix: str,
    ) -> "EnabledPluginRead":
        base_path = f"{api_prefix}{offer.manifest.api.prefix}"
        business_id = str(business_plugin.business_id)
        return cls(
            key=offer.plugin.key,
            name=offer.plugin.name,
            version=offer.plugin.version,
            enabled_by=business_plugin.enabled_by,
            enabled_at=business_plugin.updated_at,
            capabilities=[
                PluginCapabilityRead(
                    key=capability.key,
                    title=capability.title,
                    type=capability.type,
                    path=base_path
                    + capability.path.replace(CAPABILITY_PATH_PLACEHOLDER, business_id),
                )
                for capability in visible_capabilities(offer.manifest, viewer)
            ],
        )


class BusinessCapabilitiesRead(BaseModel):
    business_id: UUID
    business_status: BusinessStatus
    business_type: PluginBusinessType | None
    categories: list[ApplicableCategoryRead]
    enabled_plugins: list[EnabledPluginRead]
    available_plugins: list[AvailablePluginRead]

    @classmethod
    def from_overview(
        cls, overview: BusinessPluginOverview, viewer: User, api_prefix: str
    ) -> "BusinessCapabilitiesRead":
        business_id = overview.business.id
        return cls(
            business_id=business_id,
            business_status=overview.business.status,
            business_type=overview.business_type,
            categories=[
                ApplicableCategoryRead.from_category(c)
                for c in overview.categories
                if c.slug != BusinessCategorySlug.ROOT
            ],
            enabled_plugins=[
                EnabledPluginRead.from_offer(offer, offer.business_plugin, viewer, api_prefix)
                for offer in overview.offers
                if offer.business_plugin is not None and offer.enabled_for_business
            ],
            available_plugins=[
                AvailablePluginRead.from_offer(offer)
                for offer in overview.offers
                if not offer.enabled_for_business
            ],
        )


class BusinessPluginRead(BaseReadSchema):
    business_id: UUID
    plugin_key: str
    status: BusinessPluginStatus
    enabled_by: UUID | None
    updated_at: datetime | None

    @classmethod
    def from_state(
        cls, business_id: UUID, plugin: Plugin, business_plugin: BusinessPlugin | None
    ) -> "BusinessPluginRead":
        return cls(
            business_id=business_id,
            plugin_key=plugin.key,
            status=business_plugin.status
            if business_plugin is not None
            else BusinessPluginStatus.DISABLED,
            enabled_by=business_plugin.enabled_by if business_plugin is not None else None,
            updated_at=business_plugin.updated_at if business_plugin is not None else None,
        )
