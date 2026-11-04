class RoleName:
    SUPER_ADMIN = "Super Admin"
    NATIVE_ADMIN = "Native Admin"
    INDIVIDUAL_USER = "Individual User"
    PROMOTER = "Promoter"
    CLUB_COMMUNITY = "Club / Community"
    BUSINESS_SERVICE_PROVIDER = "Business / Service Provider"


class RoleSlug:
    SUPER_ADMIN = "super-admin"
    NATIVE_ADMIN = "native-admin"
    INDIVIDUAL_USER = "individual-user"
    PROMOTER = "promoter"
    CLUB_COMMUNITY = "club-community"
    BUSINESS_SERVICE_PROVIDER = "business-service-provider"


CANONICAL_ROLE_SLUGS = (
    RoleSlug.SUPER_ADMIN,
    RoleSlug.NATIVE_ADMIN,
    RoleSlug.INDIVIDUAL_USER,
    RoleSlug.PROMOTER,
    RoleSlug.CLUB_COMMUNITY,
    RoleSlug.BUSINESS_SERVICE_PROVIDER,
)
ADMIN_ROLE_SLUGS = frozenset({RoleSlug.SUPER_ADMIN, RoleSlug.NATIVE_ADMIN})
VERIFIED_ACCOUNT_ROLE_SLUGS = (
    RoleSlug.PROMOTER,
    RoleSlug.CLUB_COMMUNITY,
    RoleSlug.BUSINESS_SERVICE_PROVIDER,
)
SELECTABLE_ACCOUNT_ROLE_SLUGS = (RoleSlug.INDIVIDUAL_USER, *VERIFIED_ACCOUNT_ROLE_SLUGS)
PROMOTER_REVIEW_ROLE_SLUGS = frozenset({RoleSlug.PROMOTER})


class PermissionName:
    USER_VIEW = "user.view"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"

    ROLE_VIEW = "role.view"
    ROLE_CREATE = "role.create"
    ROLE_UPDATE = "role.update"
    ROLE_DELETE = "role.delete"

    PERMISSION_VIEW = "permission.view"
    PERMISSION_CREATE = "permission.create"
    PERMISSION_UPDATE = "permission.update"
    PERMISSION_DELETE = "permission.delete"

    PAGE_VIEW = "page.view"
    PAGE_READ = "page.read"
    PAGE_CREATE = "page.create"
    PAGE_UPDATE = "page.update"
    PAGE_DELETE = "page.delete"

    SETTING_VIEW = "setting.view"
    SETTING_CREATE = "setting.create"
    SETTING_UPDATE = "setting.update"
    SETTING_DELETE = "setting.delete"

    GEOGRAPHY_IMPORT = "geography.import"
    GEOGRAPHY_MANAGE = "geography.manage"

    POST_VIEW = "post.view"
    POST_CREATE = "post.create"
    POST_CREATE_ANY = "post.create_any"
    POST_VIEW_ANY = "post.view_any"
    POST_UPDATE_ANY = "post.update_any"
    POST_DELETE_ANY = "post.delete_any"
    POST_BLOCK = "post.block"
    POST_LIKE = "post.like"
    POST_COMMENT = "post.comment"
    POST_SHARE = "post.share"
    POST_SAVE = "post.save"

    COMMENT_DELETE_ANY = "comment.delete_any"

    CATEGORY_SUGGEST = "category.suggest"
    CATEGORY_VIEW_PENDING = "category.view_pending"
    CATEGORY_APPROVE = "category.approve"
    CATEGORY_REJECT = "category.reject"
    CATEGORY_CREATE = "category.create"
    CATEGORY_UPDATE = "category.update"
    CATEGORY_DELETE = "category.delete"

    NATIVE_PLACE_SUGGEST = "native_place.suggest"
    NATIVE_PLACE_VIEW_PENDING = "native_place.view_pending"
    NATIVE_PLACE_APPROVE = "native_place.approve"
    NATIVE_PLACE_REJECT = "native_place.reject"
    NATIVE_PLACE_MANAGE = "native_place.manage"

    POPULAR_PLACE_MANAGE = "popular_place.manage"

    COMMUNITY_CREATE = "community.create"
    COMMUNITY_VIEW_PENDING = "community.view_pending"
    COMMUNITY_APPROVE = "community.approve"
    COMMUNITY_REJECT = "community.reject"

    BUSINESS_CREATE = "business.create"
    BUSINESS_SEARCH = "business.search"
    BUSINESS_VIEW_ANY = "business.view_any"
    BUSINESS_UPDATE_ANY = "business.update_any"
    BUSINESS_DELETE_ANY = "business.delete_any"
    BUSINESS_REVIEW = "business.review"
    BUSINESS_ESCALATE = "business.escalate"
    BUSINESS_CREATE_ANY = "business.create_any"

    LOST_FOUND_VIEW = "lost_found.view"
    LOST_FOUND_CREATE = "lost_found.create"
    LOST_FOUND_UPDATE_ANY = "lost_found.update_any"
    LOST_FOUND_DELETE_ANY = "lost_found.delete_any"

    EVENTS_VIEW = "events.view"
    EVENTS_CREATE = "events.create"
    EVENTS_UPDATE_ANY = "events.update_any"
    EVENTS_DELETE_ANY = "events.delete_any"
    EVENTS_FEATURE = "events.feature"

    DEAL_CREATE = "deal.create"
    DEAL_VIEW_ANY = "deal.view_any"

    ROLE_UPGRADE_REQUEST_CREATE = "role_upgrade_request.create"
    ROLE_UPGRADE_REQUEST_VIEW_OWN = "role_upgrade_request.view_own"
    ROLE_UPGRADE_REQUEST_VIEW_ANY = "role_upgrade_request.view_any"
    ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER = "role_upgrade_request.review_promoter"
    ROLE_UPGRADE_REQUEST_APPROVE = "role_upgrade_request.approve"
    ROLE_UPGRADE_REQUEST_REJECT = "role_upgrade_request.reject"

    PLUGIN_VIEW = "plugin.view"
    PLUGIN_MANAGE = "plugin.manage"


GUEST_PERMISSIONS = frozenset({PermissionName.POST_VIEW, PermissionName.PAGE_READ})
