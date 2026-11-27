import copy
import enum
from dataclasses import dataclass, field
from typing import Any

from app.core.openapi_tags import ApiTag

SCHEMA_REF_PREFIX = "#/components/schemas/"


class DocsAudience(enum.StrEnum):
    COMMON = "common"
    MOBILE = "mobile"
    ADMIN = "admin"
    INDIVIDUAL = "individual"
    PROMOTER = "promoter"
    DELIVERY_TEAM = "delivery-team"
    BUSINESS = "business"
    CLUB = "club"


@dataclass(frozen=True)
class AudienceDefinition:
    title: str
    tag_prefix: str | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    note: str | None = None

    def includes(self, tag: str) -> bool:
        return tag in self.tags or (self.tag_prefix is not None and tag.startswith(self.tag_prefix))


ALSO_INDIVIDUAL_NOTE = (
    "Only the extra endpoints for this role. They also use everything on the "
    "[Individual User](/docs/individual) page."
)

INDIVIDUAL_USER_TAGS = frozenset(
    {
        ApiTag.PROFILE,
        ApiTag.AADHAAR_DOCUMENT,
        ApiTag.LOCATION,
        ApiTag.NATIVE_PLACES,
        ApiTag.ACCOUNT_ROLE,
        ApiTag.ROLE_UPGRADE_REQUESTS,
        ApiTag.USER_SETTINGS,
        ApiTag.USER_ADDRESSES,
        ApiTag.EXPLORE,
        ApiTag.UPDATES,
        ApiTag.POSTS,
        ApiTag.COMMUNITY_POSTS,
        ApiTag.LOST_FOUND,
        ApiTag.EVENTS,
        ApiTag.SAVED_POSTS,
        ApiTag.COLLECTIONS,
        ApiTag.USER_FOLLOWS,
        ApiTag.COMMUNITY,
        ApiTag.COMMUNITY_MEMBERSHIP,
        ApiTag.COMMUNITY_TIMELINE,
        ApiTag.COMMUNITY_POLLS,
        ApiTag.COMMUNITY_CHAT,
        ApiTag.DEALS,
        ApiTag.DEAL_ITEMS,
        ApiTag.DEAL_IMAGES,
        ApiTag.DEAL_PARTICIPATION,
        ApiTag.DEAL_EXPLORE,
        ApiTag.DEAL_ORDERS,
        ApiTag.CART,
        ApiTag.ORDERS,
        ApiTag.SELLER_ORDERS,
        ApiTag.BOOKINGS,
        ApiTag.PAYMENTS,
        ApiTag.DELIVERY_TRACKING,
        ApiTag.DELIVERY_CUSTOMER,
        ApiTag.CATEGORIES,
        ApiTag.CHAT_MESSAGES,
        ApiTag.CHAT_BLOCKED_USERS,
        ApiTag.EARNINGS,
        ApiTag.PAYOUTS,
        ApiTag.COD_DUES,
    }
)

AUDIENCES: dict[DocsAudience, AudienceDefinition] = {
    DocsAudience.COMMON: AudienceDefinition("Common (auth, notifications)", tag_prefix="0."),
    DocsAudience.MOBILE: AudienceDefinition("Platform App (Mobile)", tag_prefix="1."),
    DocsAudience.ADMIN: AudienceDefinition(
        "Admin Panel (Back Office)", tag_prefix="2.", tags=frozenset({ApiTag.DELIVERY_TEAM})
    ),
    DocsAudience.INDIVIDUAL: AudienceDefinition(
        "Individual User",
        tags=INDIVIDUAL_USER_TAGS,
        note="Everything a regular app user can do. Other roles build on this page.",
    ),
    DocsAudience.PROMOTER: AudienceDefinition(
        "Promoter",
        tags=frozenset(
            {
                ApiTag.DEAL_ACCEPTANCE,
                ApiTag.DEAL_DELIVERY,
                ApiTag.DELIVERY_TEAM,
                ApiTag.DELIVERY_ROUTES,
                ApiTag.DELIVERY_REQUESTS,
            }
        ),
        note=ALSO_INDIVIDUAL_NOTE,
    ),
    DocsAudience.DELIVERY_TEAM: AudienceDefinition(
        "Delivery Team",
        tags=frozenset({ApiTag.DELIVERY_COURIER, ApiTag.DELIVERY_VEHICLES}),
        note="Endpoints for delivery team members (couriers).",
    ),
    DocsAudience.BUSINESS: AudienceDefinition(
        "Business / Service Provider",
        tags=frozenset(
            {
                ApiTag.BUSINESSES,
                ApiTag.BUSINESS_DOCUMENTS,
                ApiTag.BUSINESS_IMAGES,
                ApiTag.BUSINESS_PLUGINS,
                ApiTag.DEAL_OWNER_REVIEW,
                ApiTag.BUSINESS_ORDERS,
                ApiTag.BUSINESS_BOOKINGS,
                ApiTag.BUSINESS_EARNINGS,
            }
        ),
        note=ALSO_INDIVIDUAL_NOTE,
    ),
    DocsAudience.CLUB: AudienceDefinition(
        "Club / Community",
        tags=frozenset({ApiTag.COMMUNITY_MODERATION}),
        note=ALSO_INDIVIDUAL_NOTE,
    ),
}


def _audience_links(audiences: list[DocsAudience]) -> str:
    return " · ".join(
        f"[{AUDIENCES[audience].title}](/docs/{audience.value})" for audience in audiences
    )


def docs_index_description() -> str:
    by_section = _audience_links([DocsAudience.COMMON, DocsAudience.MOBILE, DocsAudience.ADMIN])
    by_role = _audience_links(
        [
            DocsAudience.INDIVIDUAL,
            DocsAudience.PROMOTER,
            DocsAudience.DELIVERY_TEAM,
            DocsAudience.BUSINESS,
            DocsAudience.CLUB,
        ]
    )
    return f"Full API reference.\n\nBy app: {by_section}\n\nBy user role: {by_role}"


def _belongs(operation: dict[str, Any], definition: AudienceDefinition) -> bool:
    return any(definition.includes(tag) for tag in operation.get("tags", []))


def _schema_refs(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = set()
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(SCHEMA_REF_PREFIX):
            found.add(ref.removeprefix(SCHEMA_REF_PREFIX))
        for value in node.values():
            found |= _schema_refs(value)
        return found
    if isinstance(node, list):
        found = set()
        for item in node:
            found |= _schema_refs(item)
        return found
    return set()


def _reachable_schemas(paths: dict[str, Any], schemas: dict[str, Any]) -> set[str]:
    reachable: set[str] = set()
    pending = _schema_refs(paths)
    while pending:
        name = pending.pop()
        if name in reachable or name not in schemas:
            continue
        reachable.add(name)
        pending |= _schema_refs(schemas[name]) - reachable
    return reachable


def audience_openapi(full: dict[str, Any], audience: DocsAudience) -> dict[str, Any]:
    definition = AUDIENCES[audience]
    filtered = copy.deepcopy(full)
    paths: dict[str, Any] = {}
    for path, operations in full.get("paths", {}).items():
        kept = {
            method: operation
            for method, operation in operations.items()
            if _belongs(operation, definition)
        }
        if kept:
            paths[path] = copy.deepcopy(kept)
    filtered["paths"] = paths
    filtered["tags"] = [tag for tag in full.get("tags", []) if definition.includes(tag["name"])]
    filtered["info"] = {
        **full.get("info", {}),
        "title": f"{full['info']['title']} · {definition.title}",
    }
    filtered["info"].pop("description", None)
    if definition.note is not None:
        filtered["info"]["description"] = definition.note
    schemas = full.get("components", {}).get("schemas", {})
    if schemas:
        keep = _reachable_schemas(paths, schemas)
        filtered["components"]["schemas"] = {
            name: schema for name, schema in schemas.items() if name in keep
        }
    return filtered
