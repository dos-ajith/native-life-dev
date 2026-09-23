class RoleSlug:
    SUPER_ADMIN = "super-admin"
    PUBLIC_AUTHORITY = "public-authority"
    GUEST = "public-user"


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
    PAGE_CREATE = "page.create"
    PAGE_UPDATE = "page.update"
    PAGE_DELETE = "page.delete"

    SETTING_VIEW = "setting.view"
    SETTING_CREATE = "setting.create"
    SETTING_UPDATE = "setting.update"
    SETTING_DELETE = "setting.delete"

    GEOGRAPHY_IMPORT = "geography.import"

    POST_VIEW = "post.view"
    POST_CREATE = "post.create"
    POST_UPDATE_ANY = "post.update_any"
    POST_DELETE_ANY = "post.delete_any"
    POST_LIKE = "post.like"
    POST_COMMENT = "post.comment"
    POST_SHARE = "post.share"

    COMMENT_DELETE_ANY = "comment.delete_any"
