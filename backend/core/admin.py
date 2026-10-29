from django.contrib import admin
from .models import Organization, Membership, Customer, Invoice, Payment, PaymentAllocation, AuditLog
admin.site.register([Organization, Membership, Customer, Invoice, Payment, PaymentAllocation, AuditLog])
