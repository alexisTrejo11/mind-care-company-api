from rest_framework.response import Response
from rest_framework import status
from typing import Any, Dict, Optional, List
from enum import Enum
from django.utils import timezone


class ResponseStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    INFO = "info"
    WARNING = "warning"


class APIResponse:
    """
    Response class for standardized API responses
    """

    @staticmethod
    def success(
        message: str = "Operation successful",
        data: Any = None,
        status_code: int = status.HTTP_200_OK,
        metadata: Optional[Dict] = None,
        pagination: Optional[Dict] = None,
    ) -> Response:
        """
        Standardized success response
        """
        response_data = {
            "status": ResponseStatus.SUCCESS.value,
            "message": message,
            "timestamp": timezone.now().isoformat(),
        }

        if data is not None:
            response_data["data"] = data

        if metadata:
            response_data["metadata"] = metadata

        if pagination:
            response_data["pagination"] = pagination

        return Response(response_data, status=status_code)

    @staticmethod
    def error(
        message: str = "An error occurred",
        code: Optional[str] = None,
        errors: Optional[List[Dict]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        metadata: Optional[Dict] = None,
    ) -> Response:
        """
        Standardized error response
        """
        response_data = {
            "status": ResponseStatus.ERROR.value,
            "message": message,
            "timestamp": timezone.now().isoformat(),
        }

        if code:
            response_data["code"] = code

        if errors:
            response_data["errors"] = errors

        if metadata:
            response_data["metadata"] = metadata

        return Response(response_data, status=status_code)

    @staticmethod
    def created(
        message: str = "Resource created successfully",
        data: Any = None,
        location: Optional[str] = None,
    ) -> Response:
        """
        Response for successful creation
        """
        headers = {}
        if location:
            headers["Location"] = location

        response = APIResponse.success(
            message=message, data=data, status_code=status.HTTP_201_CREATED
        )

        if headers:
            response.headers.update(headers)

        return response

    @staticmethod
    def paginated(
        data: List[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = "Data retrieved successfully",
    ) -> Response:
        """
        Standardized paginated response
        """
        pagination = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": page * page_size < total,
            "has_previous": page > 1,
        }

        return APIResponse.success(message=message, data=data, pagination=pagination)
