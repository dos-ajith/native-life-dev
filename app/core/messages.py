class AuthMessages:
    LOGIN_SUCCESSFUL = "Login successful"
    PROFILE_RETRIEVED = "User profile retrieved"
    LOGGED_OUT = "Logged out"
    INVALID_CREDENTIALS = "Invalid email or password"
    ACCOUNT_INACTIVE = "Account is not active"
    EMAIL_NOT_VERIFIED = "Please verify your email before logging in"
    MISSING_TOKEN = "Please login to proceed"
    INVALID_TOKEN = "Invalid or expired token"
    PERMISSION_DENIED = "You do not have permission to perform this action"
    EMAIL_VERIFIED = "Email verified successfully"
    EMAIL_ALREADY_VERIFIED = "Email is already verified"
    INVALID_OR_EXPIRED_OTP = "Invalid or expired verification code"
    OTP_MAX_ATTEMPTS_EXCEEDED = "Too many incorrect attempts. Request a new verification code."
    OTP_RESEND_COOLDOWN = "Please wait {seconds} seconds before requesting another code"
    VERIFICATION_CODE_SENT = "Verification code sent. Please check your email."
    TOKEN_REFRESHED = "Token refreshed"
    INVALID_REFRESH_TOKEN = "Invalid or expired refresh token"
    REGISTRATION_REQUIRED = "Verification successful. Please complete your registration."
    REGISTRATION_COMPLETED = "Registration completed"
    INVALID_REGISTRATION_TOKEN = "Registration session is invalid or has expired"
    PHONE_OTP_SENT = "Verification code sent. Please check your messages."
    PHONE_OTP_RATE_LIMITED = "Too many verification codes requested. Please try again later."
    SMS_UNAVAILABLE = "Phone sign-in is temporarily unavailable"
    SMS_SEND_FAILED = "We could not send the verification code. Please try again later."
    PHONE_ALREADY_REGISTERED = "This phone number is already registered"
    PHONE_ALREADY_VERIFIED = "This phone number is already verified on your account"
    PHONE_VERIFIED = "Phone number verified"
    GOOGLE_TOKEN_INVALID = "Google sign-in could not be verified"
    GOOGLE_UNAVAILABLE = "Google sign-in is temporarily unavailable"
    GOOGLE_EMAIL_NOT_VERIFIED = "Your Google account email is not verified"
    GOOGLE_ACCOUNT_EXISTS = (
        "An account already uses this email. Sign in with your existing method, "
        "then link Google from your account."
    )
    GOOGLE_IDENTITY_IN_USE = "This Google account is already linked to another account"
    GOOGLE_ALREADY_LINKED = "A different Google account is already linked to your account"
    GOOGLE_LINKED = "Google account linked"


class UserMessages:
    REGISTERED = "Registration successful. Please check your email for the verification code."
    CREATED = "User created"
    RETRIEVED = "User retrieved"
    LIST_RETRIEVED = "Users retrieved"
    UPDATED = "User updated"
    PROFILE_UPDATED = "Profile updated"
    PROFILE_RETRIEVED = "Profile retrieved"
    PROFILE_IMAGE_UPDATED = "Profile image updated"
    ROLES_UPDATED = "User roles updated"
    DELETED = "User deleted"
    NOT_FOUND = "User not found"
    EMAIL_TAKEN = "Email is already registered"
    EMAIL_DOMAIN_NOT_ALLOWED = "Registration is not allowed for this email provider"
    PHONE_TAKEN = "Phone number is already registered"
    CANNOT_DELETE_SELF = "Cannot delete your own account"
    UNKNOWN_ROLE_IDS = "Unknown role id(s): {ids}"
    DEFAULT_ROLE_MISSING = "Default role is not configured"
    ADMIN_ROLE_CHANGE_FORBIDDEN = "Only a Super Admin can grant or remove administrative roles"
    SUPER_ADMIN_PROTECTED = "Only a Super Admin can modify a Super Admin account"
    SINGLE_ROLE_ONLY = "A user can hold only one role"
    NATIVE_ADMIN_ROLE_MANAGED_BY_NATIVE_PLACE = (
        "The Native Admin role can only be granted or removed through a native place"
    )


class UserFollowMessages:
    FOLLOWED = "User followed"
    UNFOLLOWED = "User unfollowed"
    REQUESTED = "Follow request sent"
    REQUEST_CANCELLED = "Follow request cancelled"
    REQUEST_ACCEPTED = "Follow request accepted"
    REQUEST_DECLINED = "Follow request declined"
    INCOMING_REQUESTS_RETRIEVED = "Follow requests retrieved"
    STATUS_RETRIEVED = "Follow status retrieved"
    FOLLOWERS_RETRIEVED = "Followers retrieved"
    FOLLOWING_RETRIEVED = "Following retrieved"
    COUNTS_RETRIEVED = "Follow counts retrieved"
    CONNECTS_RETRIEVED = "Connects retrieved"
    ALREADY_FOLLOWING = "You are already following this user"
    ALREADY_REQUESTED = "You have already requested to follow this user"
    NOT_FOLLOWING_OR_REQUESTED = "You are not following or requesting to follow this user"
    REQUEST_NOT_FOUND = "Follow request not found"
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
    SYSTEM_ROLE_PROTECTED = "Built-in roles cannot be deleted"
    ADMIN_ROLE_PROTECTED = "Only a Super Admin can change an administrative role"
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
    RADIUS_REQUIRES_LOCATION = "radius_km requires latitude and longitude"
    MEDIA_RETRIEVED = "Post media retrieved"
    MEDIA_REMOVED = "Post media removed"
    MEDIA_NOT_FOUND = "Post media not found"
    VIDEO_THUMBNAIL_REQUIRED = "Each video must include a matching thumbnail image"
    DUPLICATE_CONTENT = "You already have a post with this exact content"
    PRIVATE_REQUIRES_COMMUNITY = "Only a community post can be private"
    ADMIN_CREATED = "Post created by admin"
    ADMIN_LIST_RETRIEVED = "Posts retrieved"
    BLOCKED = "Post blocked"
    UNBLOCKED = "Post unblocked"
    ALREADY_BLOCKED = "Post is already blocked"
    NOT_BLOCKED = "Post is not blocked"
    ONLY_PUBLISHED_CAN_BE_BLOCKED = "Only a published post can be blocked"
    BLOCKED_NOT_EDITABLE = "A blocked post cannot be edited"
    STATUS_BLOCKED_NOT_ALLOWED = "A post cannot be set to blocked directly"


class ExploreMessages:
    BUSINESSES_RETRIEVED = "Nearby businesses retrieved"


class BusinessMessages:
    CREATED = "Business created"
    RETRIEVED = "Business retrieved"
    LIST_RETRIEVED = "Businesses retrieved"
    CATEGORIES_RETRIEVED = "Business categories retrieved"
    UPDATED = "Business updated"
    DELETED = "Business deleted"
    NOT_FOUND = "Business not found"
    NOT_OWNER = "You do not have permission to access this business"
    ROLE_NOT_VERIFIED = "Select the Business / Service Provider role to create a business"
    PUBLISH_REQUIRES_VERIFIED_ROLE = (
        "Your Business / Service Provider role must be approved before you can publish a business"
    )
    INACTIVE = "This business is not active"
    APPROVED = "Business approved"
    REJECTED = "Business rejected"
    RESUBMITTED = "Business resubmitted for verification"
    COUNTS_RETRIEVED = "Business counts retrieved"
    ADMIN_CREATED = "Business created and assigned to the owner"
    OWNER_NOT_BUSINESS_USER = "The owner must be an active Business / Service Provider user"
    OUTSIDE_JURISDICTION = "The business location must be inside your native place"
    ESCALATED = "Business escalated to Super Admin"
    ALREADY_ESCALATED = "Business is already escalated"
    ESCALATED_REQUIRES_SUPER_ADMIN = "An escalated business can only be resolved by a Super Admin"
    DOCUMENT_REVIEWED = "Business document reviewed"
    NOT_PENDING = "Only businesses awaiting verification can be reviewed"
    NOT_REJECTED = "Only rejected businesses can be resubmitted"
    NOT_VERIFIED = "A business must be verified before it can be activated"
    JURISDICTION_NOT_SET = "Set your primary native place to review businesses in your area"
    PENDING_REVIEW_EXISTS = (
        "You already have a business awaiting admin verification. "
        "You can create another once it is approved"
    )
    NAME_ALREADY_USED = "You already have a business with this name"
    INVALID_CATEGORY = "Category does not exist or is not active"
    LOCATION_INCOMPLETE = "latitude and longitude must be provided together"
    RADIUS_REQUIRES_LOCATION = "radius_meters requires latitude and longitude"
    DOCUMENT_ADDED = "Business document added"
    DOCUMENTS_RETRIEVED = "Business documents retrieved"
    DOCUMENT_DELETED = "Business document deleted"
    DOCUMENT_NOT_FOUND = "Business document not found"
    DOCUMENT_TYPES_MISMATCH = "Send one document_types entry for each document"
    IMAGE_ADDED = "Business image added"
    IMAGES_RETRIEVED = "Business images retrieved"
    IMAGE_DELETED = "Business image deleted"
    IMAGE_NOT_FOUND = "Business image not found"


class CategoryMessages:
    CREATED = "Category created"
    UPDATED = "Category updated"
    DELETED = "Category deleted"
    LIST_RETRIEVED = "Categories retrieved"
    SUGGESTED = "Category suggestion submitted for review"
    PENDING_LIST_RETRIEVED = "Pending category suggestions retrieved"
    APPROVED = "Category approved"
    REJECTED = "Category rejected"
    NOT_PENDING = "Only pending categories can be approved or rejected"
    NOT_PUBLISHED = "Only published categories can be activated or deactivated"
    NOT_FOUND = "Category not found"
    PARENT_FILTER_CONFLICT = "Provide either parent_id or parent_slug, not both"
    OUTSIDE_ROOT = "Category must belong to the '{root}' category"
    PARENT_NOT_FOUND = "Parent category does not exist"
    PARENT_INACTIVE = "Parent category is not published and active"
    SELF_PARENT = "A category cannot be its own parent"
    CIRCULAR_HIERARCHY = "A category cannot be moved under one of its own descendants"
    DUPLICATE_NAME = "A category with this name already exists under the same parent"
    HAS_CHILDREN = "Category has child categories and cannot be deleted"
    IN_USE = "Category is used by businesses and cannot be deleted; deactivate it instead"
    INVALID_PARENT_ID = "parent_id must be a category id or 'null'"
    INACTIVE_LIST_FORBIDDEN = "You do not have permission to list inactive categories"
    BOUND_TO_PLUGIN = (
        "Category is used by a business plugin and cannot be deleted; deactivate it instead"
    )
    CORE_CATEGORY_MISPLACED = (
        "Core category '{slug}' exists but is not a published child of '{parent}'; resolve it first"
    )
    CORE_CATEGORY_CONFLICT = (
        "Category '{name}' already exists with slug '{slug}'; expected slug '{expected}'"
    )


class TagMessages:
    INVALID_NAME = "Tag names must contain at least one letter or number"


class PostCommentMessages:
    CREATED = "Comment added"
    LIST_RETRIEVED = "Comments retrieved"
    DELETED = "Comment deleted"
    NOT_FOUND = "Comment not found"
    NOT_OWNER = "You do not have permission to delete this comment"
    PARENT_NOT_FOUND = "Parent comment not found"


class PostReactionMessages:
    REACTED = "Reaction saved"
    REACTION_REMOVED = "Reaction removed"
    NOT_FOUND = "Reaction not found"


class PostShareMessages:
    SHARED = "Post shared"


class LostFoundMessages:
    CREATED = "Report created"
    RETRIEVED = "Report retrieved"
    LIST_RETRIEVED = "Reports retrieved"
    UPDATED = "Report updated"
    RESOLVED = "Report marked as resolved"
    DELETED = "Report deleted"
    NOT_FOUND = "Report not found"
    NOT_OWNER = "You do not have permission to change this report"
    ALREADY_RESOLVED = "This report is already resolved"
    RESOLVED_READ_ONLY = "A resolved report can no longer be changed"
    RESPONDED = "The author of the report has been notified"
    CANNOT_RESPOND_OWN = "You cannot respond to your own report"
    ALREADY_RESPONDED = "You have already responded to this report"
    IMAGE_ADDED = "Image added"
    IMAGE_DELETED = "Image deleted"
    IMAGE_NOT_FOUND = "Image not found"
    TOO_MANY_IMAGES = "A report can have at most {limit} images"
    DATE_IN_FUTURE = "The date cannot be in the future"
    LOCATION_INCOMPLETE = "latitude and longitude must be provided together"
    RADIUS_REQUIRES_LOCATION = "radius_km requires latitude and longitude"


class DealMessages:
    CREATED = "Deal created"
    RETRIEVED = "Deal retrieved"
    LIST_RETRIEVED = "Deals retrieved"
    UPDATED = "Deal updated"
    DELETED = "Deal deleted"
    CANCELLED = "Deal cancelled"
    CLOSED = "Deal closed"
    SUBMITTED = "Deal submitted for acceptance"
    INVITATIONS_REFRESHED = "Deal invitations refreshed"
    INVITATIONS_RETRIEVED = "Deal invitations retrieved"
    ACCEPTED = "Deal accepted and published"
    DECLINED = "Deal declined"
    ITEM_ADDED = "Deal item added"
    ITEM_UPDATED = "Deal item updated"
    ITEM_DELETED = "Deal item deleted"
    IMAGE_ADDED = "Deal image added"
    IMAGE_DELETED = "Deal image deleted"
    THUMBNAIL_SET = "Deal thumbnail updated"
    NOT_FOUND = "Deal not found"
    ITEM_NOT_FOUND = "Deal item not found"
    IMAGE_NOT_FOUND = "Deal image not found"
    NOT_OWNER = "You do not have permission to manage this deal"
    NOT_DRAFT = "Only draft deals can be changed"
    NOT_PENDING = "This deal is no longer awaiting acceptance"
    NOT_CANCELLABLE = "Only pending or published deals can be cancelled"
    NOT_CLOSABLE = "Only published deals can be closed"
    DEAL_CLOSED = "This deal has been closed"
    ITEMS_REQUIRED = "Add at least one item before submitting the deal"
    THUMBNAIL_REQUIRED = "Add a thumbnail image before submitting the deal"
    TOO_MANY_ITEMS = "A deal can have at most {limit} items"
    TOO_MANY_IMAGES = "A deal can have at most {limit} images"
    DEAL_PRICE_ABOVE_ORIGINAL = "deal_price cannot be higher than original_price"
    VALID_UNTIL_IN_PAST = "valid_until must be in the future"
    END_BEFORE_START = "valid_until must be after starts_at"
    PICKUP_OR_DELIVERY_REQUIRED = "Provide pickup_location or delivery_details"
    BUSINESS_NOT_OWNED = "You can only create deals for your own business"
    PRIMARY_NATIVE_REQUIRED = "Set your primary native place before creating or submitting a deal"
    SECONDARY_NATIVE_NOT_SET = "You have not set a secondary native place"
    ACCEPTANCE_NOT_CONFIGURED = "Deal acceptance is not configured. Please contact support."
    NOT_ACCEPTOR = "Your account role cannot accept deals"
    NOT_ELIGIBLE = "You are not eligible to accept this deal"
    INVITATION_NOT_FOUND = "You have not been invited to accept this deal"
    INVITATION_CLOSED = "This invitation is no longer open"
    ACCEPTING_ROLES_INVALID = "deal_accepting_roles must be a JSON array of role slugs"
    ACCEPTING_ROLES_COUNT = "deal_accepting_roles must contain exactly {limit} role"
    ACCEPTING_ROLE_UNKNOWN = "Role '{slug}' does not exist"
    ACCEPTING_ROLE_NOT_VERIFIABLE = (
        "Role '{slug}' has no verification workflow and cannot be used to accept deals"
    )
    ACCEPTANCE_TIMEOUT_INVALID = (
        "deal_acceptance_timeout_hours must be a whole number between {minimum} and {maximum}"
    )
    ORDER_PLACED = "Order placed"
    ITEM_NAME_REQUIRED = "Each item needs a name unless it references a product"
    PRODUCT_DEAL_PRICE_REQUIRED = "Product items need a deal_price"
    PRODUCT_QUANTITY_REQUIRED = "Product items need a quantity"
    PRODUCT_ITEM_FIELDS_LOCKED = (
        "Product items take their name, unit and original_price from the product"
    )
    ITEMS_MUST_BE_PRODUCTS = "Deals for a business can only contain that business's products"
    PRODUCT_ITEMS_NEED_BUSINESS = "Only deals for a business can contain products"
    BUSINESS_LOCKED_BY_ITEMS = "Remove the deal's items before changing its business"
    COMMERCE_UNAVAILABLE = "This business cannot sell products through deals"
    PRODUCT_NOT_FOUND = "Product not found for this business"
    PRODUCT_INACTIVE = "Product '{name}' is not active"
    PRODUCT_DUPLICATED = "A product can only appear once in a deal"
    PRODUCT_PRICE_CHANGED = "deal_price for '{name}' is higher than the product's selling price"
    NOT_PUBLISHED = "Only published deals can be ordered"
    NOT_STARTED = "This deal has not started yet"
    ENDED = "This deal has ended"
    ORDER_ITEMS_DUPLICATED = "Each deal item can only appear once in an order"
    ORDER_ITEM_NOT_ORDERABLE = "Deal item '{name}' cannot be ordered"
    ORDER_ITEM_LIMIT_EXCEEDED = "Only {remaining} of '{name}' left in this deal"
    JOINED = "You joined the deal"
    LEFT = "You left the deal"
    JOINED_LIST_RETRIEVED = "Joined deals retrieved"
    PARTICIPANTS_RETRIEVED = "Deal participants retrieved"
    CANNOT_JOIN_OWN = "You cannot join your own deal"
    CANNOT_JOIN_ACCEPTED = "You cannot join a deal you accepted for publishing"
    ALREADY_JOINED = "You have already joined this deal"
    NOT_JOINED = "You have not joined this deal"
    JOIN_REQUIRED = "Join this deal before adding items or placing an order"
    LEAVE_BLOCKED_BY_ORDERS = "You cannot leave a deal while you have an order on it"


class OrderMessages:
    RETRIEVED = "Order retrieved"
    LIST_RETRIEVED = "Orders retrieved"
    PLACED = "Order placed"
    PRODUCTS_DUPLICATED = "Each product can only appear once in an order"
    STATUS_UPDATED = "Order status updated"
    CANCELLED = "Order cancelled"
    NOT_FOUND = "Order not found"
    USE_CANCEL = "Use the cancel endpoint to cancel an order"
    TRANSITION_INVALID = "An order cannot move from '{current}' to '{target}'"
    NOT_CANCELLABLE = "An order with status '{current}' cannot be cancelled"
    CONFLICT = "The order could not be saved; try again"


class DeliveryMessages:
    SETTINGS_RETRIEVED = "Delivery settings retrieved"
    SETTINGS_SAVED = "Delivery settings saved"
    OPTIONS_RETRIEVED = "Delivery options retrieved"
    OPTION_UNAVAILABLE = "This delivery option is not available for this deal right now"
    ADDRESS_REQUIRED = "Choose a delivery address for this delivery option"
    WORKING_DAYS_INVALID = "working_days must list each weekday once, from 1 (Monday) to 7 (Sunday)"
    END_BEFORE_START = "route_end_time must be after route_start_time"
    NOT_ALLOWED = "Your account role cannot manage delivery settings"
    ROUTE_UNAVAILABLE = "Choose a route that is available for your delivery address"
    ROUTE_REQUIRED = "Choose a delivery route for this delivery option"
    ELIGIBLE_ROUTES_RETRIEVED = "Available delivery routes retrieved"
    ACCESS_NOT_CONFIGURED = "Delivery settings are not configured. Please contact support."
    TIMEOUT_INVALID = "{key} must be a whole number of minutes between {minimum} and {maximum}"
    ROLES_INVALID = "delivery_settings_roles must be a JSON array of one or more role slugs"
    ROLE_UNKNOWN = "Role '{slug}' does not exist"
    ROLE_NOT_VERIFIABLE = (
        "Role '{slug}' has no verification workflow and cannot manage delivery settings"
    )


class DeliveryVehicleMessages:
    CREATED = "Vehicle added"
    LIST_RETRIEVED = "Vehicles retrieved"
    RETRIEVED = "Vehicle retrieved"
    UPDATED = "Vehicle updated"
    DELETED = "Vehicle deleted"
    NOT_FOUND = "Vehicle not found"


class DeliveryRouteMessages:
    CREATED = "Route added"
    LIST_RETRIEVED = "Routes retrieved"
    RETRIEVED = "Route retrieved"
    UPDATED = "Route updated"
    DELETED = "Route deleted"
    NOT_FOUND = "Route not found"
    NO_NATIVE_PLACE = "Set your primary native place before creating a delivery route"
    NAME_TAKEN = "You already have a route with this name"
    PATH_TAKEN = "You already have a route with the same start and end points"


class DeliveryRequestMessages:
    LIST_RETRIEVED = "Delivery requests retrieved"
    RETRIEVED = "Delivery retrieved"
    ACCEPTED = "Delivery request accepted"
    REJECTED = "Delivery request rejected"
    RE_REQUESTED = "Delivery requested again"
    STOPS_RETRIEVED = "Route stops retrieved"
    LOCATION_UPDATED = "Route location updated"
    NOT_FOUND = "Delivery request not found"
    NOT_OPEN = "This delivery request is no longer open"
    NO_DELIVERY = "This order has no delivery request"
    ROUTE_REQUIRED = "Choose one of your routes to accept this instant delivery"
    ROUTE_CANNOT_SERVE = "This route cannot serve the delivery address right now"
    NOT_RETRYABLE = "Choose another route only after the promoter declined or the request expired"
    ORDER_CLOSED = "This order can no longer be delivered"


class CartMessages:
    RETRIEVED = "Cart retrieved"
    ITEM_ADDED = "Item added to cart"
    ITEM_UPDATED = "Cart item updated"
    ITEM_REMOVED = "Item removed from cart"
    DEAL_REMOVED = "Deal removed from cart"
    DEAL_NOT_IN_CART = "Your cart has no items for this deal"
    CHECKED_OUT = "Order placed from your cart"
    ITEM_NOT_FOUND = "Cart item not found"
    NOTHING_TO_CHECK_OUT = "Your cart has no items for this deal"
    QUANTITY_TOO_HIGH = "A cart line can hold at most {limit} units"
    CONFLICT = "The cart could not be saved; try again"


class UserAddressMessages:
    CREATED = "Address added"
    LIST_RETRIEVED = "Addresses retrieved"
    UPDATED = "Address updated"
    DELETED = "Address deleted"
    DEFAULT_SET = "Default address updated"
    NOT_FOUND = "Address not found"
    MAP_CENTER_RETRIEVED = "Map center retrieved"
    NO_NATIVE_PLACE = "Set your primary native place to get a map starting point"
    LOCATION_INCOMPLETE = "latitude and longitude must be provided together"
    OUTSIDE_COVERAGE = "This location is outside the areas we deliver to"
    HAS_ONGOING_ORDERS = (
        "This address is used by an ongoing order. "
        "You can delete it once the order is delivered or cancelled"
    )


class EventMessages:
    CREATED = "Event created"
    RETRIEVED = "Event retrieved"
    LIST_RETRIEVED = "Events retrieved"
    FEATURED_RETRIEVED = "Featured event retrieved"
    RELATED_RETRIEVED = "Related events retrieved"
    UPDATED = "Event updated"
    CANCELLED = "Event cancelled"
    DELETED = "Event deleted"
    FEATURED = "Event featured"
    UNFEATURED = "Event unfeatured"
    NOT_FOUND = "Event not found"
    NOT_OWNER = "You do not have permission to change this event"
    ALREADY_CANCELLED = "This event is already cancelled"
    CANCELLED_READ_ONLY = "A cancelled event can no longer be changed"
    IMAGE_ADDED = "Image added"
    IMAGE_DELETED = "Image deleted"
    IMAGE_NOT_FOUND = "Image not found"
    TOO_MANY_IMAGES = "An event can have at most {limit} images"
    TOO_MANY_CAPTIONS = "There cannot be more captions than images"
    START_IN_PAST = "The event cannot start in the past"
    END_BEFORE_START = "The event must end after it starts"
    DATE_RANGE_INVALID = "to_date cannot be before from_date"
    LOCATION_INCOMPLETE = "latitude and longitude must be provided together"
    RADIUS_REQUIRES_LOCATION = "radius_km requires latitude and longitude"


class UpdateFeedMessages:
    LIST_RETRIEVED = "Updates retrieved"


class SavedPostMessages:
    SAVED = "Post saved"
    UNSAVED = "Post unsaved"
    ALREADY_SAVED = "You have already saved this post"
    NOT_FOUND = "Saved post not found"
    LIST_RETRIEVED = "Saved posts retrieved"


class CollectionMessages:
    CREATED = "Collection created"
    RETRIEVED = "Collection retrieved"
    LIST_RETRIEVED = "Collections retrieved"
    UPDATED = "Collection updated"
    DELETED = "Collection deleted"
    NOT_FOUND = "Collection not found"
    POSTS_RETRIEVED = "Collection posts retrieved"
    POST_ADDED = "Post added to collection"
    POST_REMOVED = "Post removed from collection"
    POST_NOT_SAVED = "Save this post before adding it to a collection"
    POST_ALREADY_IN_COLLECTION = "This post is already in the collection"
    POST_NOT_IN_COLLECTION = "This post is not in the collection"


class DeviceMessages:
    REGISTERED = "Device registered for push notifications"
    REMOVED = "Device removed from push notifications"
    WEB_CONFIG_RETRIEVED = "Web push configuration retrieved"


class NotificationMessages:
    PUSH_TITLE = "Native Life"
    DIRECT_MESSAGE_PUSH_TITLE = "{sender}"
    LIST_RETRIEVED = "Notifications retrieved"
    UNREAD_COUNT_RETRIEVED = "Unread notification count retrieved"
    MARKED_READ = "Notification marked as read"
    ALL_MARKED_READ = "All notifications marked as read"
    NOT_FOUND = "Notification not found"
    UNKNOWN_ACTOR = "Someone"
    USER_FOLLOWED = "{actor} started following you"
    FOLLOW_REQUESTED = "{actor} requested to follow you"
    FOLLOW_REQUEST_ACCEPTED = "{actor} accepted your follow request"
    POST_LIKED = "{actor} liked your post"
    POST_COMMENTED = "{actor} commented on your post"
    ROLE_UPGRADE_REQUESTED = "{actor} requested the {role_name} role"
    ROLE_UPGRADE_APPROVED = "Your request for the {role_name} role was approved"
    ROLE_UPGRADE_REJECTED = "Your request for the {role_name} role was rejected"
    CATEGORY_SUGGESTED = "{actor} suggested the category '{category_name}'"
    CATEGORY_APPROVED = "Your category '{category_name}' has been approved."
    CATEGORY_REJECTED = "Your category '{category_name}' has been rejected. Reason: {review_note}"
    BUSINESS_SUBMITTED = "{actor} submitted the business '{business_name}' for verification"
    BUSINESS_APPROVED = "Your business '{business_name}' has been verified and is now active."
    BUSINESS_REJECTED = "Your business '{business_name}' was not verified. Reason: {review_note}"
    COMMUNITY_SUBMITTED = "{actor} submitted the community '{community_name}' for approval"
    COMMUNITY_APPROVED = "Your community '{community_name}' has been approved."
    COMMUNITY_REJECTED = (
        "Your community '{community_name}' has been rejected. Reason: {review_note}"
    )
    COMMUNITY_JOIN_REQUESTED = "{actor} requested to join '{community_name}'"
    COMMUNITY_JOIN_APPROVED = "Your request to join '{community_name}' was approved"
    COMMUNITY_JOIN_REJECTED = "Your request to join '{community_name}' was rejected"
    COMMUNITY_POST_REMOVED = (
        "Your post in '{community_name}' was removed by the owner. Reason: {review_note}"
    )
    DEAL_ACCEPTANCE_REQUESTED = "{actor} submitted the deal '{deal_name}' for your acceptance"
    DEAL_NO_ELIGIBLE_ACCEPTORS = (
        "No eligible users were found to accept your deal '{deal_name}'. "
        "It stays pending until someone eligible accepts it."
    )
    DEAL_NO_ELIGIBLE_ACCEPTORS_ADMIN = (
        "{actor} submitted the deal '{deal_name}' but no eligible users can accept it"
    )
    DEAL_PUBLISHED = "{actor} accepted your deal '{deal_name}'. It is now published."
    DEAL_EXPIRED = "Your deal '{deal_name}' expired because it was not accepted in time"
    DELIVERY_REQUESTED = "New delivery request for order {order_number}"
    DELIVERY_ACCEPTED = "A promoter accepted the delivery of your order {order_number}"
    DELIVERY_REJECTED = (
        "The promoter declined the delivery of your order {order_number}. "
        "Please choose another route."
    )
    DELIVERY_EXPIRED = (
        "No promoter accepted the delivery of your order {order_number} in time. "
        "Please choose another route."
    )
    LOST_FOUND_NEARBY = "{actor} reported a {item_kind} item near you: '{item_title}'"
    LOST_FOUND_RESOLVED = "Your {item_kind} report '{item_title}' was marked as resolved by {actor}"
    LOST_FOUND_FOUND = "{actor} says they found your lost item '{item_title}'"
    LOST_FOUND_CLAIMED = "{actor} says the item you found, '{item_title}', belongs to them"
    LOST_FOUND_CLOSED = "{actor} marked the {item_kind} report '{item_title}' as resolved"
    RESPONSE_NOTE_SUFFIX = " Note: {response_note}"


class RealtimeMessages:
    AUTH_REQUIRED = "Authentication message required"
    AUTH_TIMEOUT = "Authentication timed out"
    TOKEN_EXPIRED = "Token expired"
    IDLE_TIMEOUT = "Connection idle for too long"
    TOO_MANY_CONNECTIONS = "Too many connections"
    INVALID_MESSAGE = "Invalid message"
    SERVER_SHUTDOWN = "Server shutting down"
    TOKEN_REVOKED = "Token revoked"


class AIWelcomeMessages:
    GREETING = "Hi {name}! 👋"
    INTRO = "I'm your Native Assistant."
    HINT_WITH_PLACE = (
        "Ask me anything about {place} — from local businesses and events to places, "
        "notices, daily services and more."
    )
    HINT_WITHOUT_PLACE = (
        "Ask me anything about your local life — from local businesses and events to "
        "places, notices, daily services and more."
    )
    SUGGESTIONS_TITLE = "Here are some things you can ask"
    DEFAULT_AREA = "my area"
    UPDATES_TITLE = "New Updates"
    UPDATES_SUBTITLE = "Get information"
    UPDATES_PROMPT = "What's new in {area}?"
    BUSINESS_TITLE = "Find business"
    BUSINESS_SUBTITLE = "Products, services"
    BUSINESS_PROMPT = "Which local businesses are there in {area}?"
    EVENTS_TITLE = "Upcoming Events"
    EVENTS_SUBTITLE = "Festivals, programs"
    EVENTS_PROMPT = "What events are coming up in {area}?"
    COMMUNITY_TITLE = "Community Posts"
    COMMUNITY_SUBTITLE = "Discussions, groups"
    COMMUNITY_PROMPT = "What are people posting in the communities near {area}?"


class AIMessages:
    RESPONSE_GENERATED = "AI response generated"
    WELCOME_RETRIEVED = "Assistant welcome retrieved"
    PROMPT_REQUIRED = "A prompt is required"
    UNKNOWN_TOOL = "Unknown AI tool: {name}"
    INVALID_TOOL_ARGUMENTS = "Invalid arguments for AI tool: {name}"
    TOOL_EXECUTION_FAILED = "AI tool execution failed"
    USER_POSTS_FORBIDDEN = "You do not have permission to view this user's posts"
    EVENTS_FORBIDDEN = "You do not have permission to view events"
    PROVIDER_UNAVAILABLE = "AI provider is currently unavailable"
    PROVIDER_TIMEOUT = "AI provider request timed out"
    PROVIDER_RATE_LIMITED = "AI is busy right now, please try again in a moment"
    MALFORMED_RESPONSE = "AI provider returned a malformed response"
    TOOL_ITERATION_LIMIT_EXCEEDED = (
        "AI could not produce a final answer within the allotted tool-call attempts"
    )
    AI_DISABLED_BY_USER = "AI features are disabled in your settings"
    AVATARS_RETRIEVED = "Assistant avatars retrieved"
    AVATAR_NOT_FOUND = "Assistant avatar not found"
    TRANSCRIPTION_GENERATED = "Speech transcribed"
    AUDIO_EMPTY = "The audio file is empty"
    AUDIO_TOO_LARGE = "The audio file is too large"
    SPEECH_TEXT_TOO_LONG = "The text is too long to be spoken"
    TRANSCRIPT_EMPTY = "No speech was detected in the audio"


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


class DocsMessages:
    WEBSOCKET_DOCS_NOT_FOUND = "WebSocket API documentation not found"


class RelativeTimeMessages:
    JUST_NOW = "Just now"
    MINUTE_AGO = "{count} minute ago"
    MINUTES_AGO = "{count} minutes ago"
    HOUR_AGO = "{count} hour ago"
    HOURS_AGO = "{count} hours ago"
    YESTERDAY = "Yesterday"
    DAYS_AGO = "{count} days ago"
    WEEK_AGO = "{count} week ago"
    WEEKS_AGO = "{count} weeks ago"
    MONTH_AGO = "{count} month ago"
    MONTHS_AGO = "{count} months ago"
    YEAR_AGO = "{count} year ago"
    YEARS_AGO = "{count} years ago"


class ValidationMessages:
    INVALID_JSON_BODY = "Request body must be valid JSON"
    FIELD_REQUIRED = "This field is required"
    NAME_BLANK = "must not be blank"
    NAME_CONTAINS_NUMBERS = "must not contain numbers"
    NAME_MISSING_LETTER = "must contain at least one letter"
    NAME_NUMERIC_ONLY = "must not be numbers only"
    INVALID_PHONE = "must be a valid mobile number including the country code, e.g. +919876543210"
    TERMS_NOT_ACCEPTED = "must be accepted to continue"
    DATE_OF_BIRTH_IN_FUTURE = "must not be in the future"


class DirectChatMessages:
    SENT = "Message sent"
    CONVERSATIONS_RETRIEVED = "Conversations retrieved"
    HISTORY_RETRIEVED = "Messages retrieved"
    MARKED_READ = "Messages marked as read"
    CANNOT_MESSAGE_SELF = "You cannot message yourself"
    HISTORY_CURSOR_NOT_FOUND = "The before cursor is not valid"
    MESSAGES_DISABLED = "This user is not accepting messages"
    CONNECTIONS_ONLY = "This user only accepts messages from people they follow or who follow them"
    BLOCKED = "You cannot exchange messages with this user"


class PresenceMessages:
    RETRIEVED = "Presence retrieved"


class UserBlockMessages:
    BLOCKED = "User blocked"
    UNBLOCKED = "User unblocked"
    LIST_RETRIEVED = "Blocked users retrieved"
    CANNOT_BLOCK_SELF = "You cannot block yourself"
    ALREADY_BLOCKED = "You have already blocked this user"
    NOT_BLOCKED = "You have not blocked this user"


class CommunityChatMessages:
    SENT = "Message sent"
    HISTORY_RETRIEVED = "Messages retrieved"
    DELETED = "Message deleted"
    NOT_FOUND = "Message not found"
    MEMBERS_ONLY = "Only active members can use this community chat"
    CANNOT_DELETE = "You can only delete your own messages unless you own the community"
    REPLY_NOT_FOUND = "The message you are replying to was not found in this community"


class CommunityTimelineMessages:
    RETRIEVED = "Community timeline retrieved"
    INVALID_CURSOR = "The before cursor is not valid"


class PollMessages:
    CREATED = "Poll created"
    LIST_RETRIEVED = "Polls retrieved"
    VOTED = "Your vote was recorded"
    VOTE_REMOVED = "Your vote was removed"
    RETRIEVED = "Poll retrieved"
    NOT_A_POLL = "This post is not a poll"
    NOT_FOUND = "Poll not found"
    DUPLICATE_OPTIONS = "Poll options must be different from each other"
    DUPLICATE_OPTION_IDS = "Each option can only be chosen once"
    OPTIONS_REQUIRED = "Polls need at least two options"
    POLL_REQUIRES_COMMUNITY = "Polls can only be created inside a community"
    POLL_OWNER_ONLY = "Only the community owner can create polls"
    POLL_DETAILS_FORBIDDEN = "Poll fields are only allowed for poll posts"
    ENDS_AT_IN_PAST = "The poll end time must be in the future"
    CLOSED = "This poll has ended"
    MEMBERS_ONLY = "Only active community members can vote"
    UNKNOWN_OPTION = "One or more options do not belong to this poll"
    SINGLE_CHOICE_ONLY = "This poll allows only one choice"
    NOT_VOTED = "You have not voted in this poll"


class HttpMessages:
    ENDPOINT_NOT_FOUND = "The requested endpoint was not found. Check the URL and its ids."
    METHOD_NOT_ALLOWED = "This HTTP method is not allowed for this endpoint"
    REQUEST_FAILED = "Request failed"


class HealthMessages:
    SERVICE_HEALTHY = "Service is healthy"
    DATABASE_HEALTHY = "Database is healthy"
    DATABASE_UNAVAILABLE = "Database is unavailable"


class AadhaarDocumentMessages:
    UPLOADED = "Aadhaar document uploaded"
    RETRIEVED = "Aadhaar document retrieved"
    NOT_FOUND = "You have not uploaded your Aadhaar document"
    FILE_NOT_FOUND = "Aadhaar file not found"
    FILES_REQUIRED = "Upload at least one Aadhaar image"
    TOO_MANY_FILES = "You can upload at most {limit} Aadhaar images"
    UPLOAD_CONFLICT = "Another upload of your Aadhaar document is in progress. Please try again."


class StorageMessages:
    INVALID_IMAGE_TYPE = "Image must be JPEG, PNG, or WebP"
    IMAGE_TOO_LARGE = "Image must be 5MB or smaller"
    PLUGIN_IMAGE_TOO_LARGE = "Image must be {limit_mb}MB or smaller"
    INVALID_VIDEO_TYPE = "Video must be MP4, MOV, or WebM"
    VIDEO_TOO_LARGE = "Video must be 100MB or smaller"
    INVALID_DOCUMENT_TYPE = "Document must be a JPEG, PNG, WebP, or PDF file"
    DOCUMENT_TOO_LARGE = "Document must be 10MB or smaller"


class RoleUpgradeRequestMessages:
    SUBMITTED = "Role upgrade request submitted"
    RETRIEVED = "Role upgrade request retrieved"
    LIST_RETRIEVED = "Role upgrade requests retrieved"
    REQUESTABLE_ROLES_RETRIEVED = "Requestable roles retrieved"
    DOCUMENT_ADDED = "Document added to role upgrade request"
    APPROVED = "Role upgrade request approved"
    REJECTED = "Role upgrade request rejected"
    NOT_FOUND = "Role upgrade request not found"
    DOCUMENT_NOT_FOUND = "Document not found"
    UNKNOWN_ROLE = "Requested role does not exist"
    RESTRICTED_ROLE = "This role cannot be requested through self-service upgrade"
    DUPLICATE_PENDING_REQUEST = "You already have a pending request for this role"
    REQUEST_NOT_PENDING = "This request has already been reviewed"
    STALE_REQUEST = "The user no longer holds the role in this request"
    CANNOT_REVIEW_OWN_REQUEST = "You cannot review your own request"


class PopularPlaceMessages:
    LIST_RETRIEVED = "Popular places retrieved"
    RETRIEVED = "Popular place retrieved"
    CREATED = "Popular place created"
    UPDATED = "Popular place updated"
    DELETED = "Popular place deleted"
    NOT_FOUND = "Popular place not found"
    ALREADY_EXISTS = "This native place is already a popular place"
    LOCATION_INCOMPLETE = "latitude and longitude must be provided together"


class NativePlaceMessages:
    SEARCH_RETRIEVED = "Native places retrieved"
    LIST_RETRIEVED = "Your native places retrieved"
    BOUNDARY_RETRIEVED = "Native place boundary retrieved"
    BOUNDARIES_RETRIEVED = "Your native place boundaries retrieved"
    CURRENT_LOCATION_RESOLVED = "Native place for your location retrieved"
    PRIMARY_SET = "Primary native place updated"
    SECONDARY_SET = "Secondary native place updated"
    SECONDARY_REMOVED = "Secondary native place removed"
    VILLAGE_NOT_FOUND = "Native place not found"
    LOCATION_NOT_FOUND = "No native place found for these coordinates"
    DISTRICT_NOT_FOUND = "District not found"
    PRIMARY_REQUIRED = "Choose a primary native place first"
    SAME_AS_PRIMARY = "Your secondary native place must differ from your primary"
    SAME_AS_SECONDARY = "Your primary native place must differ from your secondary"
    NO_SECONDARY = "You have not chosen a secondary native place"
    SECONDARY_NOT_ELIGIBLE = (
        "A secondary native place is only available when there are no businesses or posts "
        "near your primary native place"
    )
    SECONDARY_ELIGIBLE_NOTE = (
        "No businesses or posts were found near your primary native place, "
        "so you can add a secondary native place"
    )
    SECONDARY_INELIGIBLE_NOTE = (
        "Businesses or posts were found near your primary native place, "
        "so a secondary native place is not available"
    )
    SUGGESTED = "Native place suggestion submitted for review"
    PENDING_LIST_RETRIEVED = "Pending native place suggestions retrieved"
    APPROVED = "Native place suggestion approved"
    REJECTED = "Native place suggestion rejected"
    SUGGESTION_NOT_FOUND = "Native place suggestion not found"
    NOT_PENDING = "Only pending suggestions can be approved or rejected"
    UPDATED = "Native place updated"
    NOTHING_TO_UPDATE = "Provide a tag name or an image to update"
    ADMIN_CREATED = "Native admin created"
    ADMIN_REMOVED = "Native admin removed"
    ADMIN_ALREADY_ASSIGNED = "This native place already has a native admin"
    NO_ADMIN = "This native place has no native admin"
    ADMIN_ROLE_MISSING = "Native Admin role is not configured"


class AccountRoleMessages:
    LIST_RETRIEVED = "Account roles retrieved"
    RETRIEVED = "Account role retrieved"
    SELECTED = "Account role selected"
    VERIFICATION_SUBMITTED = "Account role verification submitted"
    NOT_SELECTABLE = "This role cannot be selected as an account role"
    SELECTION_UNAVAILABLE = "Account role selection is not available for this account"
    NO_ACCOUNT_ROLE = "This account has no account role"
    ROLE_ALREADY_SELECTED = (
        "This role is already selected. Attach documents to its verification request instead"
    )
    VERIFICATION_NOT_REQUIRED = "Your account role does not require verification"
    ALREADY_VERIFIED = "Your account role is already verified"
    DOCUMENT_NOT_APPLICABLE = "A document can only be attached to a role that requires verification"


class GeographyMessages:
    IMPORTED = "Geography imported successfully"
    INVALID_FILE_TYPE = "Uploaded file must be a ZIP archive"
    FILE_TOO_LARGE = "Uploaded file exceeds the maximum allowed size"
    INVALID_ZIP = "Uploaded file is not a valid ZIP archive"
    UNSAFE_ZIP_ENTRY = "ZIP archive contains an unsafe file path"
    ZIP_TOO_LARGE_UNCOMPRESSED = "ZIP archive is too large when uncompressed"
    NO_SHAPEFILES = "No shapefile layers were found in the archive"
    LAYERS_NOT_IDENTIFIED = (
        "Could not identify the {levels} layer(s) with sufficient confidence, and no "
        "village layer can derive them. Detected layers: {report}"
    )
    AMBIGUOUS_LAYER = "Multiple layers qualify as the {level} layer ({layers}); refusing to guess"
    LAYER_SUMMARY = (
        "{name} ({geometry}, {count} records, CRS {crs}, fields: {fields}; "
        "sample: {sample}) -> {reason}"
    )
    LAYER_SUMMARY_UNREADABLE = "{name} -> {reason}"
    LAYER_REASON_UNREADABLE = "could not be read as a shapefile"
    LAYER_REASON_NOT_POLYGON = "geometry type {geometry} is not polygonal"
    LAYER_REASON_EMPTY = "contains no records"
    LAYER_REASON_VILLAGE_SOURCE = (
        "village-level layer ({fields}) that can derive state, district and taluk boundaries"
    )
    LAYER_REASON_VILLAGE_INCOMPLETE = (
        "village-level layer ({fields}) that lacks {missing}, so boundaries cannot be derived"
    )
    LAYER_REASON_NO_ADMIN_FIELDS = "has no recognised administrative fields"
    LAYER_REASON_INCOMPLETE_FIELDS = "looks like a {level} layer but lacks {fields}"
    LAYER_REASON_CODES_NOT_UNIQUE = (
        "{field} values are blank or repeated, so it is not one record per {level}"
    )
    LAYER_REASON_NAME_CONFLICT = "named as a {named_level} layer but its fields indicate {level}"
    LAYER_REASON_CANDIDATE = "identified as {level} layer"
    MISSING_PRJ = "Layer '{layer}' is missing its .prj projection file"
    INVALID_PRJ = "Layer '{layer}' has a .prj projection file that could not be parsed"
    NULL_REQUIRED_VALUE = "Layer '{layer}' has a blank value for required field '{field}'"
    INVALID_STATE_LGD = "State LGD code '{actual}' in layer '{layer}' is not in the state layer"
    UNEXPECTED_STATE_RECORD_COUNT = "Expected exactly one state record, found {count}"
    DUPLICATE_DISTRICT_LGD = "Duplicate district LGD code found: {code}"
    DUPLICATE_TALUK_LGD = "Duplicate taluk LGD code found: {code}"
    STATES_RETRIEVED = "States retrieved"
    DISTRICTS_RETRIEVED = "Districts retrieved"
    TALUKS_RETRIEVED = "Taluks retrieved"
    VILLAGES_RETRIEVED = "Villages retrieved"
    TALUK_NOT_FOUND = "Taluk not found"
    STATE_NOT_FOUND = "State not found"
    DISTRICT_NOT_FOUND = "District not found"
    ORPHAN_TALUK_DISTRICT = "Taluk '{name}' references unknown district LGD code: {code}"
    INVALID_GEOMETRY = "Layer '{layer}' contains an invalid geometry for record {identifier}"
    AMBIGUOUS_PARENT_CODE = (
        "{level} LGD code {code} is assigned to more than one {parent_level}: {parents}"
    )
    INVALID_DERIVED_GEOMETRY = "Derived {level} boundary for LGD code {code} is not a valid polygon"
    GEOMETRY_OUT_OF_RANGE = (
        "Layer '{layer}' record {identifier} falls outside EPSG:4326 bounds after "
        "reprojection; check the layer's .prj file"
    )
    LOCATION_RESOLVED = "Location resolved"
    LOCATION_NOT_FOUND = "No matching state, district, or taluk found for the given coordinates"
    ADDRESS_SUGGESTIONS_RETRIEVED = "Address suggestions retrieved"
    LOCATION_ADDRESS_RESOLVED = "Address resolved"
    DISTRICT_CREATED = "District created"
    TALUK_CREATED = "Taluk created"
    VILLAGE_CREATED = "Village created"
    POINT_OUTSIDE_PARENT = "The given coordinates fall outside the selected {parent}"
    AREA_ALREADY_COVERED = "The given coordinates already belong to the existing {level} '{name}'"
    LGD_CODE_TAKEN = "LGD code '{code}' is already in use"


class CommunityMessages:
    EDIT_BLOCKED = (
        "This community was blocked after repeated rejections and can no longer be edited"
    )
    RECOMMENDED_RETRIEVED = "Recommended communities retrieved"
    NATIVE_PLACE_REQUIRED = "Set your primary native place before creating a community"
    MARKED_READ = "Community marked as read"
    CREATED = "Community submitted for approval"
    RETRIEVED = "Community retrieved"
    LIST_RETRIEVED = "Communities retrieved"
    MINE_RETRIEVED = "Your communities retrieved"
    UPDATED = "Community updated"
    RESUBMITTED = "Community resubmitted for approval"
    PENDING_LIST_RETRIEVED = "Pending communities retrieved"
    APPROVED = "Community approved"
    REJECTED = "Community rejected"
    NOT_FOUND = "Community not found"
    NOT_PENDING = "This community has already been reviewed"
    NOT_PUBLISHED = "This community is not published"
    NOT_OWNER = "Only the community owner can do this"
    ROLE_NOT_VERIFIED = "Only a Club / Community account can create a community"
    OWNER_ROLE_NOT_APPROVED = (
        "The owner's Club / Community role request is not approved yet. "
        "Approve the role upgrade request first, then review this community"
    )
    PENDING_EXISTS = "You already have a community waiting for approval"
    DUPLICATE_NAME = "A community with this name already exists"
    MAX_MEMBERS_BELOW_COUNT = "Maximum members cannot be lower than the current member count"
    JOINED = "You joined the community"
    JOIN_REQUESTED = "Join request sent to the community owner"
    LEFT = "You left the community"
    JOIN_REQUEST_CANCELLED = "Join request cancelled"
    ALREADY_MEMBER = "You are already a member of this community"
    ALREADY_REQUESTED = "You already have a pending request for this community"
    BLOCKED = "You cannot join this community"
    FULL = "This community has reached its member limit"
    OWNER_CANNOT_LEAVE = "The community owner cannot leave the community"
    NOT_A_MEMBER = "You are not a member of this community"
    MEMBERS_RETRIEVED = "Community members retrieved"
    REQUESTS_RETRIEVED = "Join requests retrieved"
    REQUEST_NOT_FOUND = "Join request not found"
    REQUEST_APPROVED = "Join request approved"
    REQUEST_REJECTED = "Join request rejected"
    MEMBER_NOT_FOUND = "Member not found"
    MEMBER_REMOVED = "Member removed"
    MEMBER_BLOCKED = "Member blocked"
    MEMBER_UNBLOCKED = "Member unblocked"
    CANNOT_MODERATE_OWNER = "The community owner cannot be removed or blocked"
    NOT_BLOCKED = "This user is not blocked"
    POSTS_RETRIEVED = "Community posts retrieved"
    POST_REMOVED = "Post removed from the community"
    POST_NOT_FOUND = "Post not found in this community"
    POSTING_NOT_ALLOWED = "Only active members of a published community can post here"


class PluginMessages:
    LIST_RETRIEVED = "Plugins retrieved"
    RETRIEVED = "Plugin retrieved"
    LOAD_REPORT_RETRIEVED = "Plugin load report retrieved"
    ENABLED = "Plugin enabled"
    DISABLED = "Plugin disabled"
    NOT_FOUND = "Plugin not found"
    NOT_AVAILABLE = "This feature is not available"
    RESTART_REQUIRED = (
        "This plugin was updated; the application must be restarted before it can serve requests"
    )
    NOT_LOADED = (
        "Plugin code is not loaded by this application process; apply it and restart the "
        "application"
    )
    DEPENDENCY_NOT_ENABLED = "Enable the required plugin '{dependency}' first"
    HAS_ENABLED_DEPENDENTS = "Disable the plugins that depend on it first: {dependents}"

    MANIFEST_UNREADABLE = "Could not read the plugin manifest: {error}"
    MANIFEST_INVALID = "Invalid plugin manifest: {errors}"
    INVALID_KEY = (
        "Plugin key must be 3-30 characters of lowercase letters, digits or single underscores, "
        "starting with a letter"
    )
    INVALID_VERSION = "'{value}' is not a semantic version (MAJOR.MINOR.PATCH)"
    INVALID_VERSION_RANGE = "'{value}' is not a valid version range such as '>=1.0,<2.0'"
    INVALID_ROLE_SCOPE = "Plugins may only target the '{role_scope}' role"
    INVALID_API_PREFIX = "api.prefix must be '{expected}'"
    INVALID_API_TAG = "api.tag must start with '{prefix}'"
    INVALID_TABLE_PREFIX = "database.table_prefix must be '{expected}'"
    INVALID_PERMISSION_NAME = (
        "Permission '{name}' must look like 'plugin.{key}.<resource>.<action>' "
        "(at most {max_length} characters)"
    )
    INVALID_IDENTIFIER = "'{value}' is not a valid lowercase Python identifier or module path"
    ENTRYPOINT_IN_EXCLUDED_PACKAGE = "entrypoint.module must not be inside '{package}'"
    INVALID_SLUG = "'{value}' is not a valid slug (lowercase letters, digits and single hyphens)"
    INVALID_CATEGORY_SLUG = "Category slug '{slug}' must start with '{prefix}'"
    UNKNOWN_CATEGORY_PARENT = (
        "Category '{slug}' has parent '{parent}', which is neither '{root}' nor declared earlier"
    )
    DUPLICATE_CATEGORY_SLUG = "Category slug '{slug}' is declared more than once"
    DUPLICATE_DEPENDENCY = "Dependency '{key}' is declared more than once"
    SELF_DEPENDENCY = "A plugin cannot depend on itself"
    MIGRATIONS_DIRECTORY_MISSING = (
        "The manifest enables migrations but the plugin has no 'migrations' directory"
    )
    SEEDERS_DIRECTORY_MISSING = (
        "The manifest enables seeders but the plugin has no 'seeders' directory"
    )
    INVALID_SCRIPT_FILENAME = (
        "'{path}' must be named NNNN_description.py (four digits, lowercase letters, digits and "
        "underscores)"
    )
    SCRIPT_ENTRYPOINT_MISSING = "'{path}' must define a callable named '{name}'"
    UNKNOWN_APPLIED_MIGRATION = (
        "Migration '{revision}' is recorded as applied but is missing from the plugin; "
        "downgrades are not supported"
    )
    MIGRATION_FAILED = "Migration '{name}' failed: {error}"
    SEEDER_FAILED = "Seeder '{name}' failed: {error}"
    PACKAGE_UNKNOWN_KEY = "No plugin found with key '{key}'"
    PACKAGE_CREATED = "Packaged {key} {version} into {path}"
    PACKAGE_UNSAFE_MEMBER = "The archive contains an unsafe entry '{name}'"
    PACKAGE_TOO_LARGE = "The archive exceeds the allowed size or number of files"
    PACKAGE_UNREADABLE = "The archive is not a readable ZIP file: {error}"
    PACKAGE_CHECKSUM_MISSING = "The archive has no {name} entry"
    PACKAGE_CHECKSUM_MISMATCH = "The archive contents do not match its {name} entry"
    PACKAGE_ALREADY_INSTALLED = (
        "A plugin with key '{key}' already exists at {path}; use --replace to overwrite it"
    )
    PACKAGE_KEY_ELSEWHERE = "Plugin key '{key}' is already provided by {path}"
    PACKAGE_EXTRACTED = "Extracted {key} {version} to {path}"
    PACKAGE_MANIFEST_MISSING = "The package has no plugin.toml at its root"
    PACKAGE_REQUIRED_FILE_MISSING = "The package is missing the required file '{path}'"
    PACKAGE_ALREADY_REGISTERED = (
        "A plugin with key '{key}' is already registered; imports never overwrite an existing "
        "plugin"
    )
    INSTALLED = "Plugin installed; it has not been enabled"
    IMPORTED_INSTALLED = "Plugin package imported and installed; it has not been enabled"
    UNINSTALLED = "Plugin uninstalled"
    UPGRADED = "Plugin package applied; restart the application to run the new version"
    UNINSTALL_ENABLED = "Disable the plugin before uninstalling it"
    UNINSTALL_HAS_DEPENDENTS = "Plugins that depend on this plugin are installed: {dependents}"
    UNINSTALL_BACKUP_FAILED = (
        "The plugin files were not removed because backing them up failed: {error}"
    )
    INVALID_ROOT_DECLARATION = (
        "Category '{slug}' is the {business_type} root and must be declared with parent '{parent}'"
    )
    UPGRADE_NOT_INSTALLED = (
        "Plugin '{key}' is not installed; import the package instead of upgrading"
    )
    UPGRADE_NOT_NEWER = (
        "Package version {package} is not newer than the installed version {installed}"
    )
    UPGRADE_NEXT_STEP = (
        "Restart the application; requests return 503 until the new version is loaded"
    )
    IMPORT_NOT_ZIP = "Upload a plugin package with a .zip file name"
    IMPORT_TOO_LARGE = "The uploaded package exceeds the {limit_mb} MB limit"
    IMPORT_EMPTY = "The uploaded package is empty"
    NOT_IMPORTED = "No imported plugin with key '{key}' was found in the plugins directory"
    DEPENDENCY_NOT_LOADED = "Required dependency '{dependency}' is not loaded in this process"
    INSTALLED_LOADED = "Plugin installed and loaded; enable it to start serving requests"
    INSTALLED_RESTART = (
        "Plugin installed but could not be loaded into the running application ({reason}); "
        "restart the application before enabling it"
    )

    DUPLICATE_KEY = "Plugin key '{key}' is declared by more than one plugin directory"
    INCOMPATIBLE_CORE_API = (
        "Plugin requires core API {required}; this application provides {provided}"
    )
    MISSING_DEPENDENCY = "Required plugin '{dependency}' is not available"
    INCOMPATIBLE_DEPENDENCY = "Plugin '{dependency}' {version} does not satisfy '{required}'"
    DEPENDENCY_CYCLE = "Dependency cycle detected between: {keys}"
    DEPENDENCY_FAILED = "Required plugin '{dependency}' failed to load"
    DEPENDENCY_NOT_APPLIED = "Required plugin '{dependency}' is not applied at a compatible version"

    FORBIDDEN_IMPORT = (
        "{file}:{line} imports '{module}'; plugins may only import the standard library, "
        "installed packages, their own modules and app.plugins.sdk"
    )
    FORBIDDEN_TESTS_IMPORT = (
        "{file}:{line} imports from the plugin's tests package, which is not loaded in production"
    )
    FORBIDDEN_UNVERIFIED_IMPORT = (
        "{file}:{line} imports from '{directory}', which is excluded from the plugin's verified "
        "contents"
    )
    NESTED_PLUGIN_ROOT = "Plugin directory is inside another plugin directory: {parent}"
    INVALID_UI_PATH = (
        "'{value}' must be a relative path inside the plugin without hidden, cache, test or "
        "build-tool directories"
    )
    UI_ENTRY_MISSING = "{section} entry '{entry}' was not found inside the plugin directory"
    FORBIDDEN_BACKREF = (
        "{file}:{line} uses backref; plugin models must not add attributes to core models"
    )
    SOURCE_SYNTAX_ERROR = "{file}:{line}: {error}"
    PACKAGE_INIT_MISSING = "Plugin directory has no __init__.py"
    IMPORT_FAILED = "Importing the plugin failed: {error}"
    ENTRYPOINT_INVALID = "Entrypoint '{module}.{function}' was not found or is not callable"
    REGISTER_FAILED = "register() failed: {error}"
    CONTEXT_CLOSED = "The plugin context no longer accepts registrations"
    AI_TOOL_NAME_INVALID = "AI tool '{name}' must be named '{prefix}' followed by a name"
    AI_TOOL_DUPLICATE = "AI tool '{name}' is registered twice"
    DEAL_COMMERCE_DUPLICATE = "A plugin can register only one deal commerce provider"
    ROUTE_TAGS_FORBIDDEN = "Plugin routes must not declare their own OpenAPI tags"
    ROUTER_LIFECYCLE_FORBIDDEN = (
        "Plugin routers must not declare on_startup, on_shutdown or lifespan handlers"
    )
    FOREIGN_BUSINESS_PLUGIN_KEY = (
        "Route '{path}' checks business access for plugin '{key}'; a plugin may only check its "
        "own key"
    )
    BUSINESS_DEPENDENCY_OUTSIDE_SCOPE = (
        "Route '{path}' uses require_business_plugin but has no business_id path parameter"
    )
    BUSINESS_ID_NOT_IN_PATH = (
        "Route '{path}' takes business_id as a {location} parameter; business_id is only "
        "allowed as a path parameter"
    )
    UNSUPPORTED_ROUTE_TYPE = (
        "Route '{path}' is a {kind}; plugins may only declare standard FastAPI HTTP routes and "
        "must register each APIRouter with ctx.include_router (no websockets, mounts, plain "
        "Starlette routes, custom route classes or nested include_router)"
    )
    FORBIDDEN_DEPENDENCY_OVERRIDES = (
        "{file}:{line} uses dependency_overrides; plugins must not replace FastAPI dependencies"
    )
    SYMLINK_FORBIDDEN = "'{path}' is a symlink; plugin directories must not contain symlinks"
    STRAY_BYTECODE = (
        "'{path}' is compiled Python outside __pycache__; plugins must ship source files only"
    )
    OPENAPI_GENERATION_FAILED = "Generating the plugin's OpenAPI schema failed: {error}"
    MODELS_NOT_REGISTERED = "Model base '{name}' is defined but not passed to ctx.register_models()"
    MODEL_BASE_NOT_ISOLATED = (
        "Plugin models must use their own DeclarativeBase with a separate MetaData"
    )
    TABLE_PREFIX_VIOLATION = "Table '{table}' must start with '{prefix}'"
    MAPPER_CONFIGURATION_FAILED = "Model configuration failed: {error}"

    NOT_APPLIED = "Present on disk but not applied; run: python -m app.plugins.cli apply"
    VERSION_NOT_APPLIED = (
        "Version {version} on disk differs from applied version {applied}; apply it and restart"
    )
    CHANGED_SINCE_APPLY = (
        "Files changed since version {version} was applied; bump the version and apply again"
    )
    REGISTRY_UNAVAILABLE = "The plugin registry could not be read; no plugins were loaded"

    DOWNGRADE_REJECTED = "Version {version} is lower than the installed version {installed}"
    CONTENT_CHANGED_WITHOUT_VERSION = (
        "Version {version} is already installed with different contents; bump the version"
    )
    SMOKE_LOAD_FAILED = "Smoke load in a separate process failed: {error}"
    SMOKE_LOAD_TIMED_OUT = (
        "Smoke load in a separate process did not finish within {seconds} seconds"
    )
    DATABASE_ERROR = "A database error occurred while applying the plugin"
    UNKNOWN_PLUGIN_KEYS = "No plugin found with key(s): {keys}"

    INVALID_CAPABILITY_PATH = (
        "Capability path '{path}' must start with '/' and may only use the {{business_id}} "
        "placeholder"
    )
    UNKNOWN_CAPABILITY_PERMISSION = (
        "Capability '{key}' uses permission '{permission}', which the plugin does not declare"
    )
    DUPLICATE_CAPABILITY_KEY = "Capability key '{key}' is declared more than once"
    CATEGORY_PARENT_UNUSABLE = (
        "Category '{slug}' cannot be placed under '{parent}' because it is not published and active"
    )
    CATEGORY_NOT_PUBLISHED = "Category '{slug}' already exists but is {status}; resolve it first"
    CATEGORY_OUTSIDE_SUBTREE = (
        "Category '{slug}' already exists outside the '{root}' category tree; resolve it first"
    )
    CATEGORY_NAME_CONFLICT = (
        "A category named '{name}' already exists under '{parent}' with slug '{existing}'; "
        "resolve it first"
    )


class BusinessPluginMessages:
    CAPABILITIES_RETRIEVED = "Business capabilities retrieved"
    AVAILABLE_RETRIEVED = "Available plugins retrieved"
    ENABLED = "Plugin enabled for this business"
    DISABLED = "Plugin disabled for this business"
    ROLE_NOT_VERIFIED = (
        "Your Business / Service Provider role must be approved before you can manage plugins"
    )
    INCOMPATIBLE = "This plugin is not available for this business's category"
    NOT_ENABLED_FOR_BUSINESS = "This plugin is not enabled for this business"
    ENABLE_CONFLICT = "The plugin's state for this business changed during the request; try again"
    ENABLE_TARGET_REMOVED = (
        "The business or plugin was removed while the plugin was being enabled; reload and try "
        "again"
    )
