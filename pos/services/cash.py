from __future__ import annotations

import sqlite3

from pos import config
from pos.repositories import cash as cash_repo
from pos.services.errors import ConflictError, NotFoundError, ValidationError


class CashService:
    def __init__(self, db) -> None:
        self.db = db

    def current(self) -> dict | None:
        with self.db.read() as conn:
            session = cash_repo.get_open_session(conn)
            if session is None:
                return None
            return cash_repo.summarize_session(conn, int(session["id"]))

    def has_open_session(self) -> bool:
        with self.db.read() as conn:
            return cash_repo.get_open_session(conn) is not None

    def open(self, opening_cash_cents: int, notes: str = "") -> dict:
        if isinstance(opening_cash_cents, bool):
            raise ValidationError("El fondo inicial no es válido.")
        try:
            opening_cash_cents = int(opening_cash_cents)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El fondo inicial no es válido.") from exc
        if opening_cash_cents < 0:
            raise ValidationError("El fondo inicial no puede ser negativo.")
        notes = " ".join(str(notes or "").strip().split())
        if len(notes) > 200:
            raise ValidationError("La nota no puede superar los 200 caracteres.")

        with self.db.transaction() as conn:
            if cash_repo.get_open_session(conn) is not None:
                raise ConflictError("Ya hay una caja abierta. Ciérrala antes de abrir otra.")
            try:
                session_id = cash_repo.open_session(
                    conn, opening_cash_cents, notes, config.utc_now_iso()
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError("Ya hay una caja abierta.") from exc
            return cash_repo.summarize_session(conn, session_id)

    def add_movement(self, kind: str, amount_cents: int, concept: str) -> dict:
        if kind not in {"ingreso", "egreso"}:
            raise ValidationError("El tipo de movimiento no es válido.")
        if isinstance(amount_cents, bool):
            raise ValidationError("El monto no es válido.")
        try:
            amount_cents = int(amount_cents)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El monto no es válido.") from exc
        if amount_cents <= 0:
            raise ValidationError("El monto debe ser mayor que cero.")
        concept = " ".join(str(concept or "").strip().split())
        if not 3 <= len(concept) <= 120:
            raise ValidationError("El concepto debe tener entre 3 y 120 caracteres.")

        with self.db.transaction() as conn:
            session = cash_repo.get_open_session(conn)
            if session is None:
                raise ConflictError("La caja está cerrada.")
            cash_repo.add_movement(
                conn,
                session_id=int(session["id"]),
                kind=kind,
                amount_cents=amount_cents,
                concept=concept,
                sale_id=None,
                when=config.utc_now_iso(),
            )
            return cash_repo.summarize_session(conn, int(session["id"]))

    def close(self, counted_cash_cents: int, notes: str = "") -> dict:
        if isinstance(counted_cash_cents, bool):
            raise ValidationError("El efectivo contado no es válido.")
        try:
            counted_cash_cents = int(counted_cash_cents)
        except (TypeError, ValueError) as exc:
            raise ValidationError("El efectivo contado no es válido.") from exc
        if counted_cash_cents < 0:
            raise ValidationError("El efectivo contado no puede ser negativo.")
        notes = " ".join(str(notes or "").strip().split())
        if len(notes) > 200:
            raise ValidationError("La nota no puede superar los 200 caracteres.")

        with self.db.transaction() as conn:
            session = cash_repo.get_open_session(conn)
            if session is None:
                raise ConflictError("No hay una caja abierta para cerrar.")
            summary = cash_repo.summarize_session(conn, int(session["id"]))
            if summary is None:  # pragma: no cover - defensivo
                raise NotFoundError("No se encontró la caja abierta.")
            expected = int(summary["expected_cash_cents"])
            difference = counted_cash_cents - expected
            cash_repo.close_session(
                conn,
                int(session["id"]),
                counted_cash_cents=counted_cash_cents,
                expected_cash_cents=expected,
                difference_cents=difference,
                notes=notes,
                when=config.utc_now_iso(),
            )
            closed = cash_repo.summarize_session(conn, int(session["id"]))
            if closed is None:  # pragma: no cover - defensivo
                raise NotFoundError("No se pudo recuperar la caja cerrada.")
            return closed

    def movements(self, session_id: int) -> list[dict]:
        with self.db.read() as conn:
            return cash_repo.list_movements(conn, session_id)

    def history(self, limit: int = 30) -> list[dict]:
        with self.db.read() as conn:
            return cash_repo.list_sessions(conn, limit=limit)
