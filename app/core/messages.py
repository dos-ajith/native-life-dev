class AuthMessages:
    LOGIN_SUCCESSFUL = "Login successful"
    PROFILE_RETRIEVED = "User profile retrieved"
    LOGGED_OUT = "Logged out"
    INVALID_CREDENTIALS = "Invalid email or password"
    ACCOUNT_INACTIVE = "Account is not active"
    MISSING_TOKEN = "Missing authentication token"
    INVALID_TOKEN = "Invalid or expired token"
    PERMISSION_DENIED = "You do not have permission to perform this action"


class UserMessages:
    REGISTERED = "Registration successful"
    CREATED = "User created"
    RETRIEVED = "User retrieved"
    LIST_RETRIEVED = "Users retrieved"
    UPDATED = "User updated"
    PROFILE_UPDATED = "Profile updated"
    PROFILE_IMAGE_UPDATED = "Profile image updated"
    ROLES_UPDATED = "User roles updated"
    DELETED = "User deleted"
    NOT_FOUND = "User not found"
    EMAIL_TAKEN = "Email is already registered"
    PHONE_TAKEN = "Phone number is already registered"
    CANNOT_DELETE_SELF = "Cannot delete your own account"
    UNKNOWN_ROLE_IDS = "Unknown role id(s): {ids}"
    DEFAULT_ROLE_MISSING = "Default role is not configured"


class UserFollowMessages:
    FOLLOWED = "User followed"
    UNFOLLOWED = "User unfollowed"
    STATUS_RETRIEVED = "Follow status retrieved"
    FOLLOWERS_RETRIEVED = "Followers retrieved"
    FOLLOWING_RETRIEVED = "Following retrieved"
    COUNTS_RETRIEVED = "Follow counts retrieved"
    ALREADY_FOLLOWING = "You are already following this user"
    NOT_FOLLOWING = "You are not following this user"
    CANNOT_FOLLOW_SELF = "You cannot follow yourself"
    CANNOT_UNFOLLOW_SELF = "You cannot unfollow yourself"


class RoleMessages:
    CREATED = "Role created"
    RETRIEVED = "Role retrieved"
    LIST_RETRIEVED = "Roles retrieved"
    UPDATED = "Role updated"
    PERMISSIONS_UPDATED = "Role permissions updated"
    DELETED = "Role deleted"
    NOT_FOUND = "Role not found"
    NAME_TAKEN = "Role name is already in use"
    SLUG_TAKEN = "Role slug is already in use"
    UNKNOWN_PERMISSION_IDS = "Unknown permission id(s): {ids}"


class PermissionMessages:
    CREATED = "Permission created"
    RETRIEVED = "Permission retrieved"
    LIST_RETRIEVED = "Permissions retrieved"
    UPDATED = "Permission updated"
    DELETED = "Permission deleted"
    NOT_FOUND = "Permission not found"
    NAME_TAKEN = "Permission name is already in use"


class SettingMessages:
    CREATED = "Setting created"
    RETRIEVED = "Setting retrieved"
    LIST_RETRIEVED = "Settings retrieved"
    UPDATED = "Setting updated"
    DELETED = "Setting deleted"
    NOT_FOUND = "Setting not found"
    KEY_TAKEN = "Setting key is already in use"


class PageMessages:
    CREATED = "Page created"
    RETRIEVED = "Page retrieved"
    LIST_RETRIEVED = "Pages retrieved"
    UPDATED = "Page updated"
    IMAGE_UPDATED = "Page image updated"
    DELETED = "Page deleted"
    NOT_FOUND = "Page not found"
    SLUG_TAKEN = "Page slug is already in use"


class PostMessages:
    CREATED = "Post created"
    RETRIEVED = "Post retrieved"
    LIST_RETRIEVED = "Posts retrieved"
    UPDATED = "Post updated"
    DELETED = "Post deleted"
    NOT_FOUND = "Post not found"
    NOT_OWNER = "You do not have permission to modify this post"
    SCHEDULED_AT_REQUIRED = "scheduled_at is required when status is scheduled"
    LOCATION_INCOMPLETE = "latitude and longitude must be provided together"
    MEDIA_RETRIEVED = "Post media retrieved"
    MEDIA_REMOVED = "Post media removed"
    MEDIA_NOT_FOUND = "Post media not found"
    VIDEO_THUMBNAIL_REQUIRED = "Each video must include a matching thumbnail image"


class TagMessages:
    INVALID_NAME = "Tag names must contain at least one letter or number"


class PostCommentMessages:
    CREATED = "Comment added"
    LIST_RETRIEVED = "Comments retrieved"
    DELETED = "Comment deleted"
    NOT_FOUND = "Comment not found"
    NOT_OWNER = "You do not have permission to delete this comment"
    PARENT_NOT_FOUND = "Parent comment not found"


class PostLikeMessages:
    LIKED = "Post liked"
    UNLIKED = "Post unliked"
    ALREADY_LIKED = "You have already liked this post"
    NOT_FOUND = "Like not found"


class PostShareMessages:
    SHARED = "Post shared"


class AIMessages:
    RESPONSE_GENERATED = "AI response generated"
    PROMPT_REQUIRED = "A prompt is required"
    UNKNOWN_TOOL = "Unknown AI tool: {name}"
    INVALID_TOOL_ARGUMENTS = "Invalid arguments for AI tool: {name}"
    TOOL_EXECUTION_FAILED = "AI tool execution failed"
    USER_POSTS_FORBIDDEN = "You do not have permission to view this user's posts"
    PROVIDER_UNAVAILABLE = "AI provider is currently unavailable"
    PROVIDER_TIMEOUT = "AI provider request timed out"
    MALFORMED_RESPONSE = "AI provider returned a malformed response"
    TOOL_ITERATION_LIMIT_EXCEEDED = (
        "AI could not produce a final answer within the allotted tool-call attempts"
    )
    AI_DISABLED_BY_USER = "AI features are disabled in your settings"


class UserSettingsMessages:
    RETRIEVED = "Settings retrieved"
    UPDATED = "Settings updated"
    AI_RETRIEVED = "AI settings retrieved"
    AI_UPDATED = "AI settings updated"
    NOTIFICATIONS_RETRIEVED = "Notification settings retrieved"
    NOTIFICATIONS_UPDATED = "Notification settings updated"
    PRIVACY_RETRIEVED = "Privacy settings retrieved"
    PRIVACY_UPDATED = "Privacy settings updated"
    CONTENT_RETRIEVED = "Content settings retrieved"
    CONTENT_UPDATED = "Content settings updated"
    UNKNOWN_TAG_IDS = "Unknown category id(s): {ids}"
    UNKNOWN_DISTRICT_IDS = "Unknown location id(s): {ids}"


class HealthMessages:
    SERVICE_HEALTHY = "Service is healthy"
    DATABASE_HEALTHY = "Database is healthy"
    DATABASE_UNAVAILABLE = "Database is unavailable"


class StorageMessages:
    INVALID_IMAGE_TYPE = "Image must be JPEG, PNG, or WebP"
    IMAGE_TOO_LARGE = "Image must be 5MB or smaller"
    INVALID_VIDEO_TYPE = "Video must be MP4, MOV, or WebM"
    VIDEO_TOO_LARGE = "Video must be 100MB or smaller"


class GeographyMessages:
    IMPORTED = "Geography imported successfully"
    INVALID_FILE_TYPE = "Uploaded file must be a ZIP archive"
    FILE_TOO_LARGE = "Uploaded file exceeds the maximum allowed size"
    INVALID_ZIP = "Uploaded file is not a valid ZIP archive"
    UNSAFE_ZIP_ENTRY = "ZIP archive contains an unsafe file path"
    ZIP_TOO_LARGE_UNCOMPRESSED = "ZIP archive is too large when uncompressed"
    MISSING_LAYER = "Required shapefile layer '{layer}' was not found in the archive"
    MISSING_PRJ = "Layer '{layer}' is missing its .prj projection file"
    MISSING_FIELD = "Layer '{layer}' is missing required field '{field}'"
    NULL_REQUIRED_VALUE = "Layer '{layer}' has a blank value for required field '{field}'"
    INVALID_STATE_LGD = "State LGD code must be '{expected}', found '{actual}'"
    UNEXPECTED_STATE_RECORD_COUNT = "Expected exactly one state record, found {count}"
    DUPLICATE_DISTRICT_LGD = "Duplicate district LGD code found: {code}"
    DUPLICATE_TALUK_LGD = "Duplicate taluk LGD code found: {code}"
    STATES_RETRIEVED = "States retrieved"
    DISTRICTS_RETRIEVED = "Districts retrieved"
    TALUKS_RETRIEVED = "Taluks retrieved"
    STATE_NOT_FOUND = "State not found"
    DISTRICT_NOT_FOUND = "District not found"
    ORPHAN_TALUK_DISTRICT = "Taluk '{name}' references unknown district LGD code: {code}"
    INVALID_GEOMETRY = "Layer '{layer}' contains an invalid geometry for record {identifier}"
    LOCATION_RESOLVED = "Location resolved"
    LOCATION_NOT_FOUND = "No matching state, district, or taluk found for the given coordinates"
