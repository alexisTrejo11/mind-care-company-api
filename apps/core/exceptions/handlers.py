from django.conf import settings
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

from .base_exceptions import MindCareBaseException
from apps.core.responses.api_response import APIResponse

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Handler global de excepciones para DRF
    Se configura en settings.py: REST_FRAMEWORK['EXCEPTION_HANDLER']
    """

    # Primero, dejar que DRF maneje las excepciones estándar
    response = exception_handler(exc, context)

    if response is not None:
        # Ya manejado por DRF, pero queremos formatear la respuesta
        return APIResponse.error(
            message=str(exc.detail) if hasattr(exc, "detail") else str(exc),
            errors=exc.detail if hasattr(exc, "detail") else None,
            status_code=response.status_code,
        )

    # Manejar nuestras excepciones personalizadas
    if isinstance(exc, MindCareBaseException):
        return APIResponse.error(
            message=str(exc.detail),
            code=getattr(exc, "default_code", "error"),
            status_code=exc.status_code,
            metadata=getattr(exc, "metadata", {}),
        )

    # Error 500 - Error inesperado
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    # En producción, no mostrar detalles del error
    if settings.DEBUG:
        message = str(exc)
    else:
        message = "An unexpected error occurred"

    return APIResponse.error(
        message=message,
        code="internal_server_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
