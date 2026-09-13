from app.config import settings


def test_settings_import_works():
    assert settings.EMBEDDING_DIMENSION == 768
    assert settings.GEMINI_MODEL_NAME
