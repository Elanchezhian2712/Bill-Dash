from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    created_on = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users'
    )

    updated_on = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_users'
    )

    user_status = models.IntegerField(default=1)

    def __str__(self):
        return self.username



# Model for the main invoice details
class Invoice(models.Model):
    # Instead of an auto-incrementing ID as the main invoice number,
    # let's store the user-provided one. The primary key will still be an auto 'id'.
    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateField()

    # Seller Details
    seller_name = models.CharField(max_length=255, default="KAVIN TEX")
    seller_address = models.TextField(default="7-1/53, 22ND WARD, AMBETHKAR STREET, Tharamangalam")
    seller_gstin = models.CharField(max_length=15, default="33BUUPR3263F2Z9")
    seller_state = models.CharField(max_length=100, default="Tamil Nadu")
    seller_state_code = models.CharField(max_length=2, default="33")

    # Buyer Details
    buyer_name = models.CharField(max_length=255)
    buyer_address = models.TextField(blank=True, null=True)
    buyer_gstin = models.CharField(max_length=15, blank=True, null=True)
    place_of_supply = models.CharField(max_length=2) # State Code

    # Other Details
    payment_mode = models.CharField(max_length=100, blank=True, null=True)

    # Financials (Use DecimalField for money)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    cgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    igst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    round_off = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    total_in_words = models.CharField(max_length=255)

    # Timestamps & User Tracking
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='invoices_created')
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.buyer_name}"

# Model for each item within an invoice
class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    bundles = models.PositiveIntegerField(null=True, blank=True)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=4, decimal_places=2) # e.g., 5.00 for 5%

    def __str__(self):
        return self.description

    @property
    def amount(self):
        return self.quantity * self.rate