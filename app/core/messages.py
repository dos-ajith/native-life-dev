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
    DEFAULT_ROLE_MISSING = "Default role is not configured"


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


class HealthMessages:
    SERVICE_HEALTHY = "Service is healthy"
    DATABASE_HEALTHY = "Database is healthy"
    DATABASE_UNAVAILABLE = "Database is unavailable"


class StorageMessages:
    INVALID_IMAGE_TYPE = "Image must be JPEG, PNG, or WebP"
    IMAGE_TOO_LARGE = "Image must be 5MB or smaller"


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
