from __future__ import annotations

from pos import config
from pos.repositories import settings as settings_repo
from pos.services.errors import ValidationError

_MAX_LENGTHS = {
    "business_name": 80,
    "ruc": 20,
    "address": 140,
    "phone": 30,
    "receipt_footer": 240,
}


class SettingsService:
    def __init__(self, db) -> None:
        self.db = db

    def get_store_info(self) -> dict[str, str]:
        with self.db.read() as conn:
            stored = settings_repo.get_all(conn)
        info = dict(config.DEFAULT_SETTINGS)
        info.update({key: value for key, value in stored.items() if key in info})
        return info

    def save(self, values: dict[str, str]) -> None:
        clean: dict[str, str] = {}
        for key, value in values.items():
            if key not in config.DEFAULT_SETTINGS:
                continue
            text = str(value or "").strip()
            limit = _MAX_LENGTHS[key]
            if len(text) > limit:
                raise ValidationError(f"El campo {key} supera los {limit} caracteres.")
            clean[key] = text
        if not clean.get("business_name") and "business_name" in clean:
            raise ValidationError("El nombre del negocio es obligatorio.")
        with self.db.transaction() as conn:
            settings_repo.set_many(conn, clean)
