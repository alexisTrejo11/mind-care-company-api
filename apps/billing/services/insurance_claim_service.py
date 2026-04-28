import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions.base_exceptions import BusinessRuleError
from apps.billing.models import Bill, InsuranceClaim
from apps.users.models import User

logger = logging.getLogger(__name__)


class InsuranceClaimService:
    """Service layer for insurance claim management"""

    @classmethod
    @transaction.atomic
    def create_claim(cls, bill: Bill, user: User, **claim_data) -> "InsuranceClaim":
        """
        Create an insurance claim

        Args:
            bill: Bill to create claim for
            user: User creating claim
            **claim_data: Claim details

        Returns:
            Created InsuranceClaim instance

        Raises:
            NotFoundError: If bill not found
            BusinessRuleError: If validation fails
        """
        from apps.billing.models import InsuranceClaim

        if not bill.insurance_company:
            raise BusinessRuleError(detail="Bill does not have insurance information")

        claim = InsuranceClaim.objects.create(
            bill=bill,
            patient=bill.patient,
            claim_amount=bill.insurance_coverage or bill.total_amount,
            status="draft",
            created_by=user,
            **{k: v for k, v in claim_data.items() if k not in ["created_by", "bill"]},
        )

        logger.info(
            f"Insurance claim created: {claim.claim_number} for bill {bill.bill_number}"
        )

        return claim

    @classmethod
    @transaction.atomic
    def submit_claim(cls, claim: "InsuranceClaim", user: User) -> "InsuranceClaim":
        """
        Submit insurance claim

        Args:
            claim: InsuranceClaim to submit
            user: User submitting claim

        Returns:
            Updated InsuranceClaim instance

        Raises:
            BusinessRuleError: If claim cannot be submitted
        """
        if claim.status != "draft":
            raise BusinessRuleError(
                detail=f"Cannot submit claim with status: {claim.status}"
            )

        claim.status = "submitted"
        claim.date_submitted = timezone.now().date()
        claim.save()

        logger.info(f"Insurance claim submitted: {claim.claim_number}")

        return claim

    @classmethod
    @transaction.atomic
    def approve_claim(
        cls, claim: "InsuranceClaim", approved_amount: Decimal, user: User = None
    ) -> "InsuranceClaim":
        """
        Approve an insurance claim

        Args:
            claim: InsuranceClaim to approve
            approved_amount: Amount approved
            user: User approving claim

        Returns:
            Updated InsuranceClaim instance

        Raises:
            BusinessRuleError: If claim cannot be approved
        """
        if claim.status != "submitted":
            raise BusinessRuleError(
                detail=f"Only submitted claims can be approved. Current status: {claim.status}"
            )

        claim.status = "approved"
        claim.approved_amount = approved_amount
        claim.date_approved = timezone.now().date()
        claim.save()

        logger.info(
            f"Insurance claim approved: {claim.claim_number} for ${approved_amount}"
        )

        return claim

    @classmethod
    @transaction.atomic
    def deny_claim(
        cls, claim: "InsuranceClaim", reason: str, user: User = None
    ) -> "InsuranceClaim":
        """
        Deny an insurance claim

        Args:
            claim: InsuranceClaim to deny
            reason: Denial reason
            user: User denying claim

        Returns:
            Updated InsuranceClaim instance

        Raises:
            BusinessRuleError: If claim cannot be denied
        """
        if claim.status not in ["draft", "submitted"]:
            raise BusinessRuleError(
                detail=f"Cannot deny claim with status: {claim.status}"
            )

        claim.status = "denied"
        claim.denial_reason = reason
        claim.date_denied = timezone.now().date()
        claim.save()

        logger.info(f"Insurance claim denied: {claim.claim_number}, reason: {reason}")

        return claim
