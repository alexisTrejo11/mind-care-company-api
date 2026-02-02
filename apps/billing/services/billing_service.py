import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.exceptions.base_exceptions import (
    AuthorizationError,
    ValidationError,
    NotFoundError,
    BusinessRuleError,
    PaymentError,
)

from ..models import Bill, BillItem, Payment, Refund, InsuranceClaim
from apps.appointments.models import Appointment
from apps.specialists.models import Specialist, SpecialistService
from apps.users.models import User

logger = logging.getLogger(__name__)


class BillingService:
    """Main billing service with business logic"""

    MIN_PAYMENT_AMOUNT = Decimal("0.5")
    DEFAULT_DUE_DAYS = 14
    DEFAULT_TAX_RATE = Decimal("8.5")

    @staticmethod
    def can_view_bill(user, bill):
        """Check if user can view bill"""
        if user.user_type == "admin":
            return True

        if user.user_type == "patient" and bill.patient == user:
            return True

        if user.user_type == "specialist":
            if (
                hasattr(user, "specialist_profile")
                and bill.appointment.specialist == user.specialist_profile
            ):
                return True

        if user.user_type == "staff":
            return True

        return False

    @staticmethod
    def calculate_bill_amounts(appointment):
        """Calculate bill amounts for an appointment"""
        consultation_fee = appointment.specialist.consultation_fee

        # Calculate base amount
        subtotal = consultation_fee
        tax_amount = (subtotal * BillingService.DEFAULT_TAX_RATE) / Decimal("100")
        total_amount = subtotal + tax_amount

        return {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "discount_amount": Decimal("0"),
            "total_amount": total_amount,
        }

    @classmethod
    @transaction.atomic
    def create_bill_from_appointment(cls, appointment, created_by, **validated_data):
        """Create a new bill from appointment"""
        cls.validate_bill_creation(appointment, created_by)

        amounts = cls.calculate_bill_amounts(appointment)

        # Set due date (default 14 days from now)
        due_date = validated_data.get("due_date")
        if not due_date:
            due_date = timezone.now().date() + timedelta(days=cls.DEFAULT_DUE_DAYS)

        # Create bill
        bill = Bill.objects.create(
            appointment=appointment,
            patient=appointment.patient,
            subtotal=amounts["subtotal"],
            tax_amount=amounts["tax_amount"],
            discount_amount=amounts["discount_amount"],
            total_amount=amounts["total_amount"],
            amount_paid=Decimal("0"),
            balance_due=amounts["total_amount"],
            due_date=due_date,
            insurance_company=validated_data.get("insurance_company"),
            policy_number=validated_data.get("policy_number"),
            notes=validated_data.get("notes", ""),
            created_by=created_by,
        )

        # Create bill item for consultation
        BillItem.objects.create(
            bill=bill,
            description=f"Consultation - {appointment.get_appointment_type_display()}",
            quantity=1,
            unit_price=appointment.specialist.consultation_fee,
            tax_rate=cls.DEFAULT_TAX_RATE,
            discount_rate=0,
            service=None,  # Could link to a service if available
        )

        # Update appointment to indicate billing is done
        # appointment.is_billed = True
        # appointment.save()

        return bill

    @staticmethod
    def validate_bill_creation(appointment, user):
        """Validate if bill can be created"""
        # Check if appointment is completed
        if appointment.status != "completed":
            raise BusinessRuleError(
                detail="Bills can only be created for completed appointments"
            )

        # Check if bill already exists
        if hasattr(appointment, "bill"):
            raise BusinessRuleError(detail="Bill already exists for this appointment")

        # TODO: Move to views and check user permissions there
        if user.user_type == "specialist":
            if not hasattr(user, "specialist_profile"):
                raise AuthorizationError(detail="Specialist profile not found")

            if appointment.specialist != user.specialist_profile:
                raise AuthorizationError(
                    detail="You can only create bills for your own appointments"
                )

        elif user.user_type not in ["admin", "staff"]:
            raise AuthorizationError(
                detail="Only admins, staff, or specialists can create bills"
            )
