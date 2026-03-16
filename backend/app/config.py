import json
from typing import List, Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    CLOUDBEDS_API_KEY: str = "placeholder_key"
    CLOUDBEDS_PROPERTY_IDS: str = "[]"
    EXCHANGE_RATE_API_KEY: str = "placeholder_key"
    ANTHROPIC_API_KEY: str = ""
    META_ACCESS_TOKEN_SAIGON: str = ""
    META_AD_ACCOUNT_SAIGON: str = ""
    META_ACCESS_TOKEN_1948: str = ""
    META_AD_ACCOUNT_1948: str = ""
    META_ACCESS_TOKEN_TAIPEI: str = ""
    META_AD_ACCOUNT_TAIPEI: str = ""
    META_ACCESS_TOKEN_OSAKA: str = ""
    META_AD_ACCOUNT_OSAKA: str = ""
    META_ACCESS_TOKEN_OANI: str = ""
    META_AD_ACCOUNT_OANI: str = ""
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = ""
    EMAIL_RECIPIENTS: str = ""
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    APP_ENV: str = "development"
    SECRET_KEY: str = "changeme"

    # Per-property Cloudbeds keys (loaded from .env CB_API_KEY_* and CB_PROPERTY_ID_*)
    CB_API_KEY_TAIPEI: str = ""
    CB_PROPERTY_ID_TAIPEI: str = ""
    CB_API_KEY_SAIGON: str = ""
    CB_PROPERTY_ID_SAIGON: str = ""
    CB_API_KEY_1948: str = ""
    CB_PROPERTY_ID_1948: str = ""
    CB_API_KEY_OANI: str = ""
    CB_PROPERTY_ID_OANI: str = ""
    CB_API_KEY_OSAKA: str = ""
    CB_PROPERTY_ID_OSAKA: str = ""

    @property
    def cloudbeds_properties(self) -> List[dict]:
        try:
            return json.loads(self.CLOUDBEDS_PROPERTY_IDS)
        except (json.JSONDecodeError, ValueError):
            return []

    @property
    def property_api_key_map(self) -> Dict[str, str]:
        """Map property_id (str) → api_key for per-property auth."""
        result: Dict[str, str] = {}
        pairs = [
            (self.CB_PROPERTY_ID_TAIPEI, self.CB_API_KEY_TAIPEI),
            (self.CB_PROPERTY_ID_SAIGON, self.CB_API_KEY_SAIGON),
            (self.CB_PROPERTY_ID_1948, self.CB_API_KEY_1948),
            (self.CB_PROPERTY_ID_OANI, self.CB_API_KEY_OANI),
            (self.CB_PROPERTY_ID_OSAKA, self.CB_API_KEY_OSAKA),
        ]
        for pid, key in pairs:
            if pid and key:
                result[str(pid)] = key
        return result

    def get_api_key_for_property(self, property_id: str) -> Optional[str]:
        return self.property_api_key_map.get(str(property_id)) or (
            self.CLOUDBEDS_API_KEY if self.CLOUDBEDS_API_KEY != "placeholder_key" else None
        )

    @property
    def email_recipients_list(self) -> List[str]:
        return [e.strip() for e in self.EMAIL_RECIPIENTS.split(",") if e.strip()]


settings = Settings()
