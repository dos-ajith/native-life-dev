from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import CommunityMessages
from app.models.community import Community
from app.models.user import User
from app.repositories.community_repository import CommunityRepository


def lock_published(communities: CommunityRepository, community_id: UUID) -> Community:
    community = communities.get_for_update(community_id)
    if community is None or not communities.is_published(community):
        raise NotFoundError(CommunityMessages.NOT_FOUND)
    return community


def lock_owned(communities: CommunityRepository, community_id: UUID, actor: User) -> Community:
    community = lock_published(communities, community_id)
    ensure_owner(community, actor)
    return community


def ensure_owner(community: Community, actor: User) -> None:
    if community.owner_id != actor.id:
        raise AuthorizationError(CommunityMessages.NOT_OWNER)
