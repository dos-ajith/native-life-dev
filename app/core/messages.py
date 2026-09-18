class AuthMessages:
    LOGIN_SUCCESSFUL = "Login successful"
    PROFILE_RETRIEVED = "User profile retrieved"
    LOGGED_OUT = "Logged out"
    INVALID_CREDENTIALS = "Invalid email or password"
    ACCOUNT_INACTIVE = "Account is not active"
    MISSING_TOKEN = "Missing authentication token"
    INVALID_TOKEN = "Invalid or expired token"
    ADMIN_REQUIRED = "Admin privileges required"


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


class RoleMessages:
    CREATED = "Role created"
    RETRIEVED = "Role retrieved"
    LIST_RETRIEVED = "Roles retrieved"
    UPDATED = "Role updated"
    PERMISSIONS_UPDATED = "Role permissions updated"
    DELETED = "Role deleted"
    NOT_FOUND = "Role not found"
    NAME_TAKEN = "Role name is already in use"
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


class HealthMessages:
    SERVICE_HEALTHY = "Service is healthy"
    DATABASE_HEALTHY = "Database is healthy"
    DATABASE_UNAVAILABLE = "Database is unavailable"


class StorageMessages:
    INVALID_IMAGE_TYPE = "Image must be JPEG, PNG, or WebP"
    IMAGE_TOO_LARGE = "Image must be 5MB or smaller"
