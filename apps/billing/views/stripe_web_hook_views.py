# views/stripe_webhook_views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
import logging

from apps.core.decorators.error_handler import api_error_handler
from apps.core.responses.api_response import APIResponse
from apps.billing.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookViewSet(viewsets.ViewSet):
    """
    ViewSet for Stripe webhook handling
    """

    permission_classes = [AllowAny]

    @method_decorator(csrf_exempt)
    @api_error_handler
    def create(self, request):
        """Handle Stripe webhook"""
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        if not sig_header:
            return HttpResponse(
                "Missing Stripe signature",
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = StripeService().handle_webhook(payload, sig_header)

            return APIResponse.success(
                message="Webhook processed successfully",
                data=result,
            )

        except Exception as e:
            logger.error(f"Error processing Stripe webhook: {str(e)}", exc_info=True)

            # Return 200 to Stripe even on error (as per Stripe docs)
            return APIResponse.error(
                message="Webhook processing failed",
                code="webhook_error",
                data={"error": str(e)},
            )

    @action(
        detail=False, methods=["get"], url_path="test", permission_classes=[AllowAny]
    )
    def test_webhook(self, request):
        """Test endpoint for webhook configuration"""
        return APIResponse.success(
            message="Stripe webhook endpoint is active",
            data={
                "status": "active",
                "endpoint": request.build_absolute_uri(),
            },
        )
