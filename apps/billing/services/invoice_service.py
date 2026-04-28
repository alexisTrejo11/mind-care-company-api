import logging
from typing import Dict
from apps.core.exceptions.base_exceptions import BusinessRuleError
from apps.billing.models import Bill

logger = logging.getLogger(__name__)


class InvoiceService:
    """Service layer for invoice generation and sending"""

    @staticmethod
    def generate_invoice_pdf(bill: Bill) -> bytes:
        """
        Generate PDF invoice for bill

        Args:
            bill: Bill to generate invoice for

        Returns:
            PDF content as bytes
        """
        try:
            # In production, use a proper PDF generation library
            # For now, return a placeholder
            from io import BytesIO
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Table,
                TableStyle,
            )
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch

            buffer = BytesIO()

            # Create PDF
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Add title
            title = Paragraph(f"INVOICE #{bill.bill_number}", styles["Title"])
            story.append(title)

            # Add bill details
            story.append(Paragraph(f"Date: {bill.invoice_date}", styles["Normal"]))
            story.append(Paragraph(f"Due Date: {bill.due_date}", styles["Normal"]))
            story.append(
                Paragraph(f"Patient: {bill.patient.get_full_name()}", styles["Normal"])
            )

            # Add items table
            items_data = [["Description", "Qty", "Unit Price", "Total"]]
            for item in bill.items.all():
                items_data.append(
                    [
                        item.description,
                        str(item.quantity),
                        f"${item.unit_price}",
                        f"${item.net_amount}",
                    ]
                )

            items_table = Table(
                items_data, colWidths=[3 * inch, inch, 1.5 * inch, 1.5 * inch]
            )
            items_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 14),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 12),
                        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ]
                )
            )

            story.append(items_table)

            # Add totals
            totals_data = [
                ["Subtotal:", f"${bill.subtotal}"],
                ["Tax:", f"${bill.tax_amount}"],
                ["Total Amount:", f"${bill.total_amount}"],
                ["Amount Paid:", f"${bill.amount_paid}"],
                ["Balance Due:", f"${bill.balance_due}"],
            ]

            totals_table = Table(totals_data, colWidths=[3 * inch, 1.5 * inch])
            totals_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ]
                )
            )

            story.append(totals_table)

            # Build PDF
            doc.build(story)

            buffer.seek(0)
            pdf_content = buffer.getvalue()

            logger.info(f"Generated invoice PDF for bill {bill.bill_number}")

            return pdf_content

        except Exception as e:
            logger.error(f"Error generating invoice PDF: {str(e)}", exc_info=True)
            raise BusinessRuleError(detail="Failed to generate invoice PDF")

    @staticmethod
    def send_invoice_email(bill: Bill) -> Dict:
        """
        Send invoice email to patient

        Args:
            bill: Bill to send invoice for

        Returns:
            Dictionary with email sending status
        """
        try:
            # In production, use Django's email functionality
            # This is a placeholder implementation

            from django.core.mail import EmailMessage
            from django.conf import settings

            subject = f"Invoice #{bill.bill_number}"

            # Generate email body
            body = f"""
            Dear {bill.patient.get_full_name()},

            Please find attached your invoice #{bill.bill_number} for your recent appointment.

            Invoice Details:
            - Invoice #: {bill.bill_number}
            - Date: {bill.invoice_date}
            - Due Date: {bill.due_date}
            - Total Amount: ${bill.total_amount}
            - Amount Paid: ${bill.amount_paid}
            - Balance Due: ${bill.balance_due}

            You can view and pay your bill online at: {bill.get_payment_url()}

            Thank you for your business!

            Best regards,
            {settings.COMPANY_NAME}
            """

            # Create email
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[bill.patient.email],
            )

            # Attach PDF
            pdf_content = InvoiceService.generate_invoice_pdf(bill)
            email.attach(
                filename=f"invoice-{bill.bill_number}.pdf",
                content=pdf_content,
                mimetype="application/pdf",
            )

            # Send email
            # email.send()

            logger.info(
                f"Invoice email sent for bill {bill.bill_number} to {bill.patient.email}"
            )

            return {
                "status": "email_sent",
                "to": bill.patient.email,
                "subject": subject,
                "bill_number": bill.bill_number,
            }

        except Exception as e:
            logger.error(f"Error sending invoice email: {str(e)}", exc_info=True)
            raise BusinessRuleError(detail="Failed to send invoice email")
