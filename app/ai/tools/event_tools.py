from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.base import AITool, SearchQuery, ToolContext
from app.core.exceptions import AuthorizationError
from app.core.messages import AIMessages
from app.core.permissions import PermissionName
from app.core.timezone import app_now
from app.models.event import EventStatus
from app.models.user import User
from app.schemas.event import EventListQuery, EventRead
from app.schemas.pagination import PaginationParams
from app.services.authorization_service import has_permission
from app.services.event_service import EventService

AI_EVENT_MAX_RESULTS = 5


def _ensure_can_view_events(actor: User) -> None:
    if not has_permission(actor, PermissionName.EVENTS_VIEW):
        raise AuthorizationError(AIMessages.EVENTS_FORBIDDEN)


class EventReferenceRead(BaseModel):
    id: UUID
    title: str
    status: EventStatus
    description: str
    category: str
    venue_name: str
    starts_at: datetime
    ends_at: datetime
    organizer_name: str
    distance_km: float | None

    @classmethod
    def from_event(cls, event: EventRead) -> "EventReferenceRead":
        return cls(
            id=event.id,
            title=event.title,
            status=event.status,
            description=event.description,
            category=event.category.name,
            venue_name=event.venue_name,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            organizer_name=event.organizer.name,
            distance_km=event.distance_km,
        )


class SearchEventsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: SearchQuery | None = Field(
        default=None,
        description="Free-text words matched against the event title, description and venue.",
    )
    from_date: date | None = Field(
        default=None, description="Earliest start day, YYYY-MM-DD. Only when the user gave one."
    )
    to_date: date | None = Field(
        default=None, description="Latest start day, YYYY-MM-DD. Only when the user gave one."
    )
    limit: int = Field(default=AI_EVENT_MAX_RESULTS, ge=1, le=AI_EVENT_MAX_RESULTS)


class SearchEventsResult(BaseModel):
    today: date
    events: list[EventReferenceRead]
    total: int


class SearchEventsTool(AITool[SearchEventsArgs]):
    name = "search_events"
    description = (
        "Search real upcoming Native Life events near the user, soonest first. Returns up "
        "to 5 events with id, title, description, category, venue, start and end time, "
        "organizer name and distance, plus the total match count and today's date. Past "
        "and cancelled events are never returned. Events have no tickets, prices or RSVPs, "
        "so never state any. Recommend only returned events; if the list is empty, say no "
        "matching upcoming events were found."
    )
    args_model = SearchEventsArgs

    def execute(self, context: ToolContext, arguments: SearchEventsArgs) -> SearchEventsResult:
        _ensure_can_view_events(context.actor)
        query = EventListQuery(
            q=arguments.query, from_date=arguments.from_date, to_date=arguments.to_date
        )
        items, total = EventService(context.db).list_for(
            PaginationParams(page=1, page_size=arguments.limit), context.actor, query
        )
        return SearchEventsResult(
            today=app_now().date(),
            events=[EventReferenceRead.from_event(item) for item in items],
            total=total,
        )


class GetEventArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(description="Event id returned by search_events.")


class GetEventTool(AITool[GetEventArgs]):
    name = "get_event"
    description = (
        "Get one Native Life event by the id returned from search_events: title, "
        "status (scheduled or cancelled), description, category, venue, start and end time "
        "and organizer name."
    )
    args_model = GetEventArgs

    def execute(self, context: ToolContext, arguments: GetEventArgs) -> EventReferenceRead:
        _ensure_can_view_events(context.actor)
        event = EventService(context.db).get_read(arguments.event_id, context.actor)
        return EventReferenceRead.from_event(event)
