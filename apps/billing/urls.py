from .views import (
    PaymentViewSet,
    PaymentMethodViewSet,
    BillViewSet,
    InsuranceClaimViewSet,
    RefundViewSet,
)
from rest_framework.routers import DefaultRouter
from django.urls import path, include

router = DefaultRouter()
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"payment-methods", PaymentMethodViewSet, basename="paymentmethod")
router.register(r"bills", BillViewSet, basename="bill")
router.register(r"insurance-claims", InsuranceClaimViewSet, basename="insuranceclaim")
router.register(r"refunds", RefundViewSet, basename="refund")

urlpatterns = [
    path("api/v2/billing/", include(router.urls)),
]
