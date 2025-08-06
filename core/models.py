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




class InvoiceItem(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=4, decimal_places=2)

    def __str__(self):
        return self.description

    @property
    def amount(self):
        return self.quantity * self.rate

class Invoice(models.Model):
    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateField()
    seller_name = models.CharField(max_length=255, default="KAVIN TEX")
    seller_address = models.TextField(default="7-1/53, 22ND WARD, AMBETHKAR STREET, Tharamangalam")
    seller_gstin = models.CharField(max_length=15, default="33BUUPR3263F2Z9")
    seller_state = models.CharField(max_length=100, default="Tamil Nadu")
    seller_state_code = models.CharField(max_length=2, default="33")
    buyer_name = models.CharField(max_length=255)
    buyer_address = models.TextField(blank=True, null=True)
    buyer_gstin = models.CharField(max_length=15, blank=True, null=True)
    place_of_supply = models.CharField(max_length=2)
    payment_mode = models.CharField(max_length=100, blank=True, null=True)
    transport_name = models.CharField(max_length=255, blank=True, null=True)
    transport_address = models.TextField(blank=True, null=True)
    transport_gstin = models.CharField(max_length=15, blank=True, null=True)
    total_bundles = models.PositiveIntegerField(default=0, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    cgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    igst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    round_off = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    total_in_words = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='invoices_created')
    updated_on = models.DateTimeField(auto_now=True)

    
    def __str__(self):
        return f"{self.invoice_number} - {self.buyer_name}"
