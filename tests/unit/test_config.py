from app.core.config import get_settings


def test_settings_load_required_values() -> None:
    settings = get_settings()

    assert settings.database_url
    assert settings.jwt_secret_key
