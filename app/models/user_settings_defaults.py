from app.models.user_settings_enums import AIResponseStyle, VisibilityLevel


class UserSettingsDefaults:
    ACTIVITY_TRACKING_ENABLED = True

    AI_ENABLED = True
    PERSONALIZATION_ENABLED = True
    PREFERRED_LANGUAGE = "en"
    RESPONSE_STYLE = AIResponseStyle.BALANCED

    PUSH_ENABLED = True
    EMAIL_ENABLED = True
    POST_ACTIVITY = True
    COMMENTS = True
    LIKES = True
    MENTIONS = True
    FOLLOWERS = True
    MESSAGES = True
    AI_UPDATES = True
    SYSTEM_UPDATES = True

    PROFILE_VISIBILITY = VisibilityLevel.PUBLIC
    LOCATION_VISIBILITY = VisibilityLevel.FOLLOWERS
    ACTIVITY_VISIBILITY = VisibilityLevel.PUBLIC
    ALLOW_MESSAGES = True
    ALLOW_MENTIONS = True

    HIDE_SENSITIVE_CONTENT = True
    PERSONALIZED_FEED = True
