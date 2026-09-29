class RoleSlug:
    SUPER_ADMIN = "super-admin"
    NATIVE_ADMIN = "native-admin"
    PUBLIC_USER = "public-user"


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

    POST_VIEW = "post.view"
    POST_CREATE = "post.create"
    POST_UPDATE_ANY = "post.update_any"
    POST_DELETE_ANY = "post.delete_any"
    POST_LIKE = "post.like"
    POST_COMMENT = "post.comment"
    POST_SHARE = "post.share"
    POST_SAVE = "post.save"

    COMMENT_DELETE_ANY = "comment.delete_any"

    ROLE_UPGRADE_REQUEST_CREATE = "role_upgrade_request.create"
    ROLE_UPGRADE_REQUEST_VIEW_OWN = "role_upgrade_request.view_own"
    ROLE_UPGRADE_REQUEST_VIEW_ANY = "role_upgrade_request.view_any"
    ROLE_UPGRADE_REQUEST_APPROVE = "role_upgrade_request.approve"
    ROLE_UPGRADE_REQUEST_REJECT = "role_upgrade_request.reject"


GUEST_PERMISSIONS = frozenset({PermissionName.POST_VIEW, PermissionName.PAGE_READ})
