from __future__ import annotations


class POSError(Exception):
    """Error de negocio con un mensaje apto para mostrar al usuario."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(POSError):
    """Datos inválidos enviados por la interfaz."""


class NotFoundError(POSError):
    """El recurso solicitado no existe."""


class ConflictError(POSError):
    """La operación choca con una regla del negocio o el estado actual."""
