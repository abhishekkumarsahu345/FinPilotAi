"""
Enhanced email rendering for payment reminders.
Includes invoice line items, payment history, and rich financial context.
"""
from datetime import date
from typing import Dict, Any, List, Tuple
from decimal import Decimal

from core.formatting import fmt_qty


def money_display(paise: int) -> str:
    """Convert paise to rupees display format."""
    return f"₹{paise / 100:,.2f}"


def build_invoice_context(invoice, customer, organization) -> Dict[str, Any]:
    """
    Build comprehensive context for email rendering including:
    - Customer details
    - Invoice header information  
    - Line items with products, quantities, amounts
    - Payment history with individual transactions
    - Financial summary (total, paid, outstanding)
    - Overdue calculation
    """
    from core.models import PaymentAllocation
    
    # Calculate outstanding balance
    active_allocations = invoice.allocations.filter(reversed_at__isnull=True).select_related('payment')
    total_paid_minor = sum(a.amount_minor for a in active_allocations)
    outstanding_minor = max(0, invoice.total_minor - total_paid_minor)
    
    # Calculate days overdue
    today = date.today()
    days_overdue = max(0, (today - invoice.due_date).days) if invoice.due_date < today else 0
    days_until_due = (invoice.due_date - today).days if invoice.due_date >= today else 0
    
    # Build line items list
    line_items = []
    for item in invoice.items.all().order_by('sort_order'):
        line_items.append({
            'description': item.description,
            'quantity': fmt_qty(item.quantity),
            'unit_price': money_display(item.unit_price_minor),
            'line_total': money_display(item.line_total_minor),
            'gst_rate_bps': item.gst_rate_bps,
            'gst_tax': money_display(item.gst_tax_minor) if item.gst_tax_minor > 0 else None,
        })
    
    # Build payment history
    payment_transactions = []
    for alloc in active_allocations.order_by('payment__payment_date'):
        payment = alloc.payment
        payment_transactions.append({
            'date': str(payment.payment_date),
            'amount': money_display(alloc.amount_minor),
            'method': payment.get_method_display(),
            'reference': payment.reference or '—',
        })
    
    # Build context dictionary
    context = {
        # Customer
        'customer_name': customer.name,
        'customer_email': customer.email,
        'customer_contact': customer.contact_name or customer.name,
        
        # Invoice header
        'invoice_number': invoice.invoice_number,
        'invoice_date': str(invoice.invoice_date),
        'due_date': str(invoice.due_date),
        'days_overdue': days_overdue,
        'days_until_due': days_until_due,
        'overdue_status': 'overdue' if days_overdue > 0 else 'due_soon' if days_until_due <= 7 else 'not_due',
        
        # Financial summary
        'subtotal': money_display(invoice.subtotal_minor),
        'discount': money_display(invoice.discount_minor) if invoice.discount_minor > 0 else None,
        'tax': money_display(invoice.tax_minor),
        'total_amount': money_display(invoice.total_minor),
        'total_paid': money_display(total_paid_minor),
        'outstanding_amount': money_display(outstanding_minor),
        'payment_percentage': int((total_paid_minor / invoice.total_minor * 100)) if invoice.total_minor > 0 else 0,
        
        # Amounts as minor units (for calculations)
        'total_minor': invoice.total_minor,
        'paid_minor': total_paid_minor,
        'outstanding_minor': outstanding_minor,
        
        # Line items and payments
        'line_items': line_items,
        'line_items_count': len(line_items),
        'payment_transactions': payment_transactions,
        'payment_transactions_count': len(payment_transactions),
        
        # Organization
        'business_name': organization.name,
        'business_email': organization.business_email or 'noreply@finpilot.ai',
        'business_contact': organization.contact_phone or '',
        'business_address': organization.billing_address or '',
        
        # Payment instructions
        'payment_reference_instructions': f"Please reference invoice {invoice.invoice_number} when making payment",
    }
    
    return context


def render_html_email_body(context: Dict[str, Any], tone: str = 'friendly') -> str:
    """
    Render a complete HTML email body with invoice details, line items, and payment history.
    
    Args:
        context: Dictionary with invoice, customer, and payment data
        tone: 'issue', 'friendly', 'gentle', 'serious'
    """
    
    # Determine greeting and opening based on tone
    if tone == 'issue':
        greeting = f"Dear {context['customer_contact']},"
        opening = f"""
        <p>Thank you for your business! Please find your invoice details below.</p>
        <p>Invoice <strong>{context['invoice_number']}</strong> dated <strong>{context['invoice_date']}</strong> 
        is due on <strong>{context['due_date']}</strong>.</p>
        """
    elif tone == 'friendly':
        greeting = f"Hello {context['customer_contact']},"
        if context['days_until_due'] > 0:
            opening = f"""
            <p>This is a friendly reminder that invoice <strong>{context['invoice_number']}</strong> 
            is due in <strong>{context['days_until_due']} days</strong> on <strong>{context['due_date']}</strong>.</p>
            """
        else:
            opening = f"""
            <p>This is a friendly reminder that invoice <strong>{context['invoice_number']}</strong> 
            is due today (<strong>{context['due_date']}</strong>).</p>
            """
    elif tone == 'gentle':
        greeting = f"Dear {context['customer_contact']},"
        opening = f"""
        <p>We notice that invoice <strong>{context['invoice_number']}</strong> is now 
        <strong>{context['days_overdue']} days overdue</strong> (due date: {context['due_date']}).</p>
        <p>We understand that payment delays can happen. If you have already made the payment, 
        please disregard this reminder.</p>
        """
    else:  # serious / final
        greeting = f"Dear {context['customer_contact']},"
        opening = f"""
        <p><strong>IMPORTANT:</strong> Invoice <strong>{context['invoice_number']}</strong> 
        is now <strong>{context['days_overdue']} days overdue</strong>.</p>
        <p>We have sent multiple payment reminders. Please settle this invoice immediately 
        to avoid any disruption to your account.</p>
        """
    
    # Build line items table
    line_items_html = ""
    if context['line_items']:
        rows = ""
        for item in context['line_items']:
            # GST label shown as a subdued note below the amount, not crammed inline.
            gst_note = (
                f'<br><small style="color:#6b7280;">incl. GST {item["gst_rate_bps"] / 100:.4g}%</small>'
                if item.get('gst_tax') else ""
            )
            rows += f"""
            <tr>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e5e7eb; word-break: break-word; max-width: 260px;">{item['description']}</td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; white-space: nowrap;">{item['quantity']}</td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; white-space: nowrap;">{item['unit_price']}</td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; white-space: nowrap;"><strong>{item['line_total']}</strong>{gst_note}</td>
            </tr>
            """

        line_items_html = f"""
        <div style="margin: 24px 0;">
            <h3 style="color: #374151; margin-bottom: 12px;">Invoice Items</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e5e7eb; table-layout: fixed;">
                <colgroup>
                    <col style="width: 44%;">
                    <col style="width: 10%;">
                    <col style="width: 20%;">
                    <col style="width: 26%;">
                </colgroup>
                <thead>
                    <tr style="background: #f9fafb;">
                        <th style="padding: 10px 10px; border-bottom: 2px solid #d1d5db; text-align: left;">Description</th>
                        <th style="padding: 10px 10px; border-bottom: 2px solid #d1d5db; text-align: right;">Qty</th>
                        <th style="padding: 10px 10px; border-bottom: 2px solid #d1d5db; text-align: right;">Unit Price</th>
                        <th style="padding: 10px 10px; border-bottom: 2px solid #d1d5db; text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
    
    # Build payment history table
    payment_history_html = ""
    if context['payment_transactions']:
        rows = ""
        for pmt in context['payment_transactions']:
            rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{pmt['date']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; text-align: right;"><strong>{pmt['amount']}</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{pmt['method']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; color: #6b7280;"><small>{pmt['reference']}</small></td>
            </tr>
            """
        
        payment_history_html = f"""
        <div style="margin: 24px 0;">
            <h3 style="color: #374151; margin-bottom: 12px;">Payment History</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; border: 1px solid #e5e7eb;">
                <thead>
                    <tr style="background: #f9fafb;">
                        <th style="padding: 10px 8px; border-bottom: 2px solid #d1d5db; text-align: left;">Date</th>
                        <th style="padding: 10px 8px; border-bottom: 2px solid #d1d5db; text-align: right;">Amount Paid</th>
                        <th style="padding: 10px 8px; border-bottom: 2px solid #d1d5db; text-align: left;">Method</th>
                        <th style="padding: 10px 8px; border-bottom: 2px solid #d1d5db; text-align: left;">Reference</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
    
    # Financial summary box
    discount_row = ""
    if context['discount']:
        discount_row = f"""
        <tr>
            <td style="padding: 6px 0; color: #059669;">Discount:</td>
            <td style="padding: 6px 0; text-align: right; color: #059669;">-{context['discount']}</td>
        </tr>
        """
    
    outstanding_style = "color: #dc2626; font-weight: bold;" if context['days_overdue'] > 0 else "color: #059669; font-weight: bold;"
    
    summary_html = f"""
    <div style="margin: 24px 0; padding: 20px; background: #f9fafb; border-left: 4px solid #3b82f6; border-radius: 4px;">
        <h3 style="color: #374151; margin-top: 0;">Payment Summary</h3>
        <table style="width: 100%; font-size: 15px;">
            <tr>
                <td style="padding: 6px 0;">Subtotal:</td>
                <td style="padding: 6px 0; text-align: right;">{context['subtotal']}</td>
            </tr>
            {discount_row}
            <tr>
                <td style="padding: 6px 0;">Tax (GST):</td>
                <td style="padding: 6px 0; text-align: right;">{context['tax']}</td>
            </tr>
            <tr style="border-top: 2px solid #d1d5db;">
                <td style="padding: 10px 0; font-size: 16px;"><strong>Total Invoice Amount:</strong></td>
                <td style="padding: 10px 0; text-align: right; font-size: 16px;"><strong>{context['total_amount']}</strong></td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #059669;">Amount Paid:</td>
                <td style="padding: 6px 0; text-align: right; color: #059669;">{context['total_paid']}</td>
            </tr>
            <tr style="border-top: 2px solid #d1d5db;">
                <td style="padding: 10px 0; font-size: 18px;"><strong>Outstanding Balance:</strong></td>
                <td style="padding: 10px 0; text-align: right; font-size: 18px; {outstanding_style}">{context['outstanding_amount']}</td>
            </tr>
        </table>
    </div>
    """
    
    # Closing based on tone
    if tone == 'serious':
        closing = f"""
        <p><strong>Action Required:</strong> Please arrange payment of <strong>{context['outstanding_amount']}</strong> immediately.</p>
        <p>If you have any questions or concerns, please contact us at {context['business_email']} or {context['business_contact']}.</p>
        """
    else:
        closing = f"""
        <p>Please arrange payment of <strong>{context['outstanding_amount']}</strong> at your earliest convenience.</p>
        <p>{context['payment_reference_instructions']}</p>
        <p>If you have any questions, feel free to contact us at {context['business_email']}{' or ' + context['business_contact'] if context['business_contact'] else ''}.</p>
        """
    
    # Assemble complete HTML email
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border: 1px solid #e5e7eb;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); padding: 30px 24px; color: white;">
                <h1 style="margin: 0; font-size: 24px;">{context['business_name']}</h1>
                <p style="margin: 8px 0 0 0; opacity: 0.95;">Payment Reminder</p>
            </div>
            
            <!-- Body -->
            <div style="padding: 32px 24px; color: #374151; line-height: 1.6;">
                {greeting}
                {opening}
                
                {line_items_html}
                {summary_html}
                {payment_history_html}
                
                {closing}
                
                <p style="margin-top: 32px;">Best regards,<br><strong>{context['business_name']}</strong></p>
            </div>
            
            <!-- Footer -->
            <div style="padding: 20px 24px; background: #f9fafb; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                <p style="margin: 0;">{context['business_name']}</p>
                {f"<p style='margin: 4px 0 0 0;'>{context['business_address']}</p>" if context['business_address'] else ""}
                <p style="margin: 4px 0 0 0;">Email: {context['business_email']}{' | Phone: ' + context['business_contact'] if context['business_contact'] else ''}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def generate_email_subject(context: Dict[str, Any], tone: str = 'friendly') -> str:
    """Generate appropriate email subject based on tone and invoice status."""
    invoice_num = context['invoice_number']
    
    if tone == 'issue':
        return f"Invoice {invoice_num} from {context['business_name']}"
    elif tone == 'friendly':
        if context['days_overdue'] > 0:
            return f"Payment Reminder: Invoice {invoice_num} (Due {context['due_date']})"
        else:
            return f"Upcoming Payment Due: Invoice {invoice_num}"
    elif tone == 'gentle':
        return f"Payment Overdue: Invoice {invoice_num} ({context['days_overdue']} days)"
    else:  # serious / final
        return f"URGENT: Payment Required - Invoice {invoice_num}"
