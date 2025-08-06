import json
import traceback
from django.forms import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status
from django.db import transaction
from .models import Invoice, InvoiceItem
from datetime import datetime
from django.utils.dateparse import parse_date
from datetime import date
from django.db.models import Sum
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# --- ReportLab Imports ---
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from num2words import num2words
from decimal import Decimal
from io import BytesIO
from django.http import JsonResponse, HttpResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from django.utils.timezone import now


User = get_user_model()

# ------------------------- Public View: Login Page -------------------------
def login_view(request):
    return render(request, 'index.html')


# ------------------------- API: Login Auth Endpoint -------------------------
@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)

    if user is None:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    token, _ = Token.objects.get_or_create(user=user)
    login(request, user)

    return Response({
        'token': token.key,
        'user_id': user.pk,
        'username': user.username,
    })


# ------------------------- Protected Views -------------------------
from datetime import date, timedelta
@login_required
def dashboard_view(request):
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)


    if today.month >= 4:
        start_of_financial_year = date(today.year, 4, 1)
        end_of_financial_year = date(today.year + 1, 3, 31)
    else:
        start_of_financial_year = date(today.year - 1, 4, 1)
        end_of_financial_year = date(today.year, 3, 31)

    # --- Base QuerySets for each period ---
    daily_invoices = Invoice.objects.filter(invoice_date=today)
    weekly_invoices = Invoice.objects.filter(invoice_date__gte=start_of_week)
    monthly_invoices = Invoice.objects.filter(invoice_date__gte=start_of_month)
    yearly_invoices = Invoice.objects.filter(
        invoice_date__range=[start_of_financial_year, end_of_financial_year]
    )

    # --- Calculations for Counts ---
    daily_invoice_count = daily_invoices.count()
    weekly_invoice_count = weekly_invoices.count()
    monthly_invoice_count = monthly_invoices.count()
    yearly_invoice_count = yearly_invoices.count()

    # --- Calculations for Amounts ---
    # The 'or 0' handles cases where there are no invoices, preventing None
    daily_amount_total = daily_invoices.aggregate(total=Sum('grand_total'))['total'] or 0
    weekly_amount_total = weekly_invoices.aggregate(total=Sum('grand_total'))['total'] or 0
    monthly_amount_total = monthly_invoices.aggregate(total=Sum('grand_total'))['total'] or 0
    yearly_amount_total = yearly_invoices.aggregate(total=Sum('grand_total'))['total'] or 0

    # --- Original calculations for summary cards (can be kept or simplified) ---
    total_invoice_count = Invoice.objects.count()
    total_invoiced_amount_agg = Invoice.objects.aggregate(total=Sum('grand_total'))
    total_invoiced_amount = total_invoiced_amount_agg['total'] or 0
    total_clients_count = Invoice.objects.values('buyer_name').distinct().count()

    # New clients this month
    buyers_this_month = set(monthly_invoices.values_list('buyer_name', flat=True).distinct())
    buyers_before_this_month = set(Invoice.objects.filter(invoice_date__lt=start_of_month).values_list('buyer_name', flat=True).distinct())
    new_clients_count = len(buyers_this_month - buyers_before_this_month)


    context = {
        # Original Stats for top cards
        'total_invoice_count': total_invoice_count,
        'total_invoiced_amount': total_invoiced_amount,
        'invoices_this_month_count': monthly_invoice_count,
        'amount_this_month': monthly_amount_total,
        'total_clients_count': total_clients_count,
        'new_clients_count': new_clients_count,

        # New Detailed Stats for the table
        'daily_invoice_count': daily_invoice_count,
        'weekly_invoice_count': weekly_invoice_count,
        'yearly_invoice_count': yearly_invoice_count,

        'daily_amount_total': daily_amount_total,
        'weekly_amount_total': weekly_amount_total,
        'yearly_amount_total': yearly_amount_total,

        'start_of_financial_year': start_of_financial_year,
        'end_of_financial_year': end_of_financial_year,
    }

    return render(request, 'pages/dashboard/dashboard.html', context)
# -------------------------------




# ==============================================================================
#  STEP 1: Refactored PDF Generation Function
# ==============================================================================
import os
from django.conf import settings


def generate_invoice_pdf(invoice):

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm
    )

    # --- Configuration and Data Preparation ---
    ITEMS_PER_PAGE = 8  
    D = Decimal

    invoice_items = []
    for item in invoice.items.all():
        amount = item.quantity * item.rate
        invoice_items.append({
            "desc": item.description, "hsn": item.hsn_code,
            "qty": item.quantity, "rate": D(item.rate),
            "amount": D(amount), "gst_rate": D(item.gst_rate)
        })

    hsn_summary = {}
    for item in invoice_items:
        hsn = item['hsn']
        if hsn not in hsn_summary:
            hsn_summary[hsn] = {'taxable_value': D(0), 'gst_rate': item['gst_rate']}
        hsn_summary[hsn]['taxable_value'] += item['amount']

    # --- Reusable Styles ---
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_right = ParagraphStyle(name='right', parent=style_normal, alignment=TA_RIGHT)
    style_bold_right = ParagraphStyle(name='bold_right', parent=style_normal, alignment=TA_RIGHT, fontName='Helvetica-Bold')
    style_left_bold = ParagraphStyle(name='left_bold', parent=style_normal, fontName='Helvetica-Bold')

    # --- Page Frame Drawer (Header/Footer) ---
    def draw_page_frame(canvas, doc):
        canvas.saveState()
        page_num_str = f" (Page {canvas.getPageNumber()})" if doc.page > 1 else ""

        # Outer Frame
        canvas.setLineWidth(1)
        canvas.rect(1 * cm, 1.5 * cm, A4[0] - 2 * cm, A4[1] - 3.5 * cm)

        # Page Title
        canvas.setFont('Helvetica-Bold', 16)
        canvas.drawCentredString(10.5 * cm, 28 * cm, f"Tax Invoice{page_num_str}")

        # Seller Details
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(1.2 * cm, 27 * cm, invoice.seller_name)
        canvas.setFont('Helvetica', 9)
        y = 26.6 * cm
        for line in invoice.seller_address.split(','):
             canvas.drawString(1.2 * cm, y, line.strip())
             y -= 0.4 * cm
        canvas.drawString(1.2 * cm, y, f"GSTIN/UIN: {invoice.seller_gstin}")
        y -= 0.4 * cm
        canvas.drawString(1.2 * cm, y, f"State Name: {invoice.seller_state}, Code: {invoice.seller_state_code}")

        # Invoice Details Box
        box_left, box_top, box_width, box_height = 10*cm, 27.7*cm, 10*cm, 4.8*cm
        canvas.rect(box_left, box_top - box_height, box_width, box_height)
        col_split = box_left + (box_width / 2)
        row_height = 0.8 * cm
        for i in range(1, 7):
            canvas.line(box_left, box_top - i * row_height, box_left + box_width, box_top - i * row_height)
        canvas.line(col_split, box_top, col_split, box_top - box_height)
        labels = [
            ("Invoice No.", invoice.invoice_number, "Dated", invoice.invoice_date.strftime('%d-%b-%Y')),
            ("Delivery Note", "", "Mode/Terms of Payment", invoice.payment_mode or ""),
            ("Reference No. & Date.", "", "Other References", ""),
            ("Buyer's Order No.", "", "Dated", ""),
            ("Dispatch Doc No.", "", "Delivery Note Date", ""),
            ("Dispatched through", "", "Destination", "")
        ]
        canvas.setFont('Helvetica', 8)
        text_padding_x = 4
        text_padding_y = 10
        for i, (l1, v1, l2, v2) in enumerate(labels):
            y_text = box_top - i * row_height - text_padding_y
            canvas.drawString(box_left + text_padding_x, y_text, l1)
            canvas.setFont('Helvetica-Bold', 9)
            canvas.drawString(box_left + text_padding_x, y_text - 9, str(v1))
            canvas.setFont('Helvetica', 8)
            canvas.drawString(col_split + text_padding_x, y_text, l2)
            canvas.setFont('Helvetica-Bold', 9)
            canvas.drawString(col_split + text_padding_x, y_text - 9, str(v2))
            canvas.setFont('Helvetica', 8)
        canvas.drawString(box_left + text_padding_x, (box_top - box_height - 0.4 * cm), "Terms of Delivery")

        # --- CORRECTED Consignee, Buyer & Transport Details ---
        # Main container box for the three sections
       
        # Main container box for the three sections
        box_left, box_bottom, box_width, box_height = 1 * cm, 19.8 * cm, 9 * cm, 4.5 * cm
        canvas.rect(box_left, box_bottom, box_width, box_height, stroke=1, fill=0)

        # Define section boundaries for three equal sections
        section_height = box_height / 3
        top_divider_y = box_bottom + 2 * section_height
        bottom_divider_y = box_bottom + 1 * section_height

        # Draw two horizontal divider lines to create three distinct sections
        canvas.line(box_left, top_divider_y, box_left + box_width, top_divider_y)
        canvas.line(box_left, bottom_divider_y, box_left + box_width, bottom_divider_y)

        # --- Drawing parameters for better layout control ---
        text_x = 1.2 * cm
        line_spacing = 0.32 * cm  # Reduced spacing to fit 4 lines per section
        top_padding = 0.33 * cm    # Padding from the top of each section

        # --- Section 1: Consignee (Ship to) ---
        y = top_divider_y + section_height - top_padding # Start from top of section
        canvas.setFont('Helvetica', 9)
        canvas.drawString(text_x, y, "Consignee (Ship to)")
        y -= line_spacing
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(text_x, y, getattr(invoice, 'buyer_name', ''))
        y -= line_spacing
        canvas.setFont('Helvetica', 9)
        canvas.drawString(text_x, y, getattr(invoice, 'buyer_address', ''))
        y -= line_spacing
        canvas.drawString(text_x, y, f"GSTIN/UIN: {getattr(invoice, 'buyer_gstin', '')}")

        # --- Section 2: Buyer (Bill to) ---
        y = bottom_divider_y + section_height - top_padding # Start from top of middle section
        canvas.setFont('Helvetica', 9)
        canvas.drawString(text_x, y, "Buyer (Bill to)")
        y -= line_spacing
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(text_x, y, getattr(invoice, 'buyer_name', ''))
        y -= line_spacing
        canvas.setFont('Helvetica', 9)
        canvas.drawString(text_x, y, getattr(invoice, 'buyer_address', ''))
        y -= line_spacing
        canvas.drawString(text_x, y, f"Place of Supply: {getattr(invoice, 'place_of_supply', '')}")

        # --- Section 3: Transport Details ---
        y = box_bottom + section_height - top_padding # Start from top of bottom section
        canvas.setFont('Helvetica', 9)
        canvas.drawString(text_x, y, "Transport Details")
        y -= line_spacing
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(text_x, y, getattr(invoice, 'transport_name', ''))
        y -= line_spacing
        canvas.setFont('Helvetica', 9)
        canvas.drawString(text_x, y, f"GSTIN/UIN: {getattr(invoice, 'transport_gstin', '')}")
        y -= line_spacing
        canvas.drawString(text_x, y, f"Address: {getattr(invoice, 'transport_address', '')}") # Restored this line
# --- END OF CORRECTION ---
        # --- END OF CORRECTION ---

        # Declaration and Signature Box
        page_width = A4[0]
        footer_y = 1.5 * cm
        left_x = 1.2 * cm
        canvas.setFont('Helvetica-Bold', 10)
        declaration_title = "Declaration"
        canvas.drawString(left_x, footer_y + 1.6 * cm, declaration_title)
        text_width = canvas.stringWidth(declaration_title, 'Helvetica-Bold', 10)
        canvas.line(left_x, footer_y + 1.55 * cm, left_x + text_width, footer_y + 1.55 * cm)
        declaration_text = ["We declare that this invoice shows the actual price of the", "goods described and that all particulars are true and", "correct."]
        text_obj = canvas.beginText(left_x, footer_y + 1.2 * cm)
        text_obj.setFont("Helvetica", 9)
        text_obj.setLeading(12)
        for line in declaration_text: text_obj.textLine(line)
        canvas.drawText(text_obj)
        right_box_width = 9.3 * cm
        right_box_height = 2.2 * cm
        right_x = page_width - right_box_width - 1 * cm
        canvas.rect(right_x, footer_y, right_box_width, right_box_height)
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawRightString(right_x + right_box_width - 0.3 * cm, footer_y + 1.7 * cm, f"for {invoice.seller_name}")
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(right_x + right_box_width - 0.3 * cm, footer_y + 0.4 * cm, "Authorised Signatory")

        canvas.setFont('Helvetica', 9)
        canvas.drawCentredString(10.5 * cm, 1 * cm, "This is a Computer Generated Invoice")
        
        canvas.restoreState()

    # --- Build Story ---
    story = []
    story.append(Spacer(1, 8.7 * cm))

    # Main Items Table
    item_chunks = [invoice_items[i:i + ITEMS_PER_PAGE] for i in range(0, len(invoice_items), ITEMS_PER_PAGE)]
    main_header = [Paragraph(f"<b>{h}</b>", style_normal) for h in ["SI No.", "Description", "HSN", "Quantity", "Rate", "per", "Amount"]]
    
    for i, chunk in enumerate(item_chunks):
        is_last_page = (i == len(item_chunks) - 1)
        table_data = [main_header]
        for idx, item in enumerate(chunk):
            row = [
                str(i * ITEMS_PER_PAGE + idx + 1),
                item['desc'], item['hsn'],
                Paragraph(f"{item['qty']}", style_right),
                Paragraph(f"{item['rate']:.2f}", style_right),
                "Nos", Paragraph(f"{item['amount']:.2f}", style_right)
            ]
            table_data.append(row)

        if is_last_page:
            gst_rate = invoice_items[0]['gst_rate'] if invoice_items else D(0)
            table_data.append(['', Paragraph("<b>Sub Total</b>", style_right), '', '', '', '', Paragraph(f"<b>{invoice.subtotal:.2f}</b>", style_bold_right)])
            
            if invoice.igst_total > 0:
                table_data.append([
                    '', Paragraph(f"Output Tax IGST @ {gst_rate:.2f}%", style_right),
                    '', '', 
                    Paragraph(f"{gst_rate:.2f}%", style_right), '%',
                    Paragraph(f"{invoice.igst_total:.2f}", style_right)
                ])
            else:
                cgst_rate = gst_rate / 2
                table_data.append([
                    '', Paragraph(f"Output Tax CGST @ {cgst_rate:.2f}%", style_right),
                    '', '',
                    Paragraph(f"{cgst_rate:.2f}%", style_right), '%',
                    Paragraph(f"{invoice.cgst_total:.2f}", style_right)
                ])
                table_data.append([
                    '', Paragraph(f"Output Tax SGST @ {cgst_rate:.2f}%", style_right),
                    '', '',
                    Paragraph(f"{cgst_rate:.2f}%", style_right), '%',
                    Paragraph(f"{invoice.sgst_total:.2f}", style_right)
                ])

            if invoice.round_off != 0:
                table_data.append(['', Paragraph("Round Off", style_right), '', '', '', '', Paragraph(f"{invoice.round_off:.2f}", style_right)])
            
            total_qty = sum(item['qty'] for item in invoice_items)
            
  
            # pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
            # Use the actual location based on your structure
            font_path = os.path.join(
                settings.BASE_DIR,
                'core',
                'static',
                'assets',
                'fonts',
                'DejaVuSans',
                'DejaVuSans.ttf'
            )

            # Optional: Check file exists before registering
            if not os.path.exists(font_path):
                raise FileNotFoundError(f"Font file not found at: {font_path}")

            # Register the font
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

            custom_rupee_style = ParagraphStyle(
                name='rupee_style',
                parent=style_bold_right,
                fontName='DejaVuSans',
            )
            # Paragraph(f"<b>\u20B9 {invoice.grand_total:.2f}</b>", custom_rupee_style)

            table_data.append([
                '', 
                Paragraph("<b>TOTAL</b>", style_bold_right), 
                '', 
                Paragraph(f"<b>{total_qty} Nos</b>", style_bold_right), 
                '', 
                '', 
                Paragraph(f"<b>\u20B9 {invoice.grand_total:.2f}</b>", custom_rupee_style)
            ])

            # =========================================================================

        item_table = Table(table_data, colWidths=[1.5*cm, 6.8*cm, 2*cm, 2.3*cm, 2.1*cm, 1.3*cm, 3*cm])
        item_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'), ('ALIGN', (2, 1), (2, -1), 'CENTER'), ('ALIGN', (5, 1), (5, -1), 'CENTER'),
        ]))
        story.append(item_table)

        if not is_last_page:
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph("continued ...", style_right))
            story.append(PageBreak())
            story.append(Spacer(1, 8.7 * cm))

    # --- Final Summaries (on the last page) ---
    story.append(Paragraph("E. & O.E", style_right))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"<b>Amount Chargeable (in words)</b><br/>{invoice.total_in_words}", style_normal))
    story.append(Spacer(1, 0.5 * cm))

    # Tax Summary Table
    is_intra_state = invoice.igst_total == 0
    tax_summary_data = []
    
    if is_intra_state:
        header1 = [Paragraph(f"<b>{h}</b>", style_normal) for h in ["HSN", "Taxable Value", "Central Tax (CGST)", "", "State Tax (SGST)", "", "Total Tax"]]
        header2 = ['', '', Paragraph("<b>Rate</b>", style_normal), Paragraph("<b>Amount</b>", style_normal), Paragraph("<b>Rate</b>", style_normal), Paragraph("<b>Amount</b>", style_normal), '']
        tax_summary_data.extend([header1, header2])
        col_widths = [3*cm, 3*cm, 2*cm, 2.5*cm, 2*cm, 2.5*cm, 4*cm]
    else:
        header1 = [Paragraph(f"<b>{h}</b>", style_normal) for h in ["HSN", "Taxable Value", "Integrated Tax (IGST)", "", "Total Tax"]]
        header2 = ['', '', Paragraph("<b>Rate</b>", style_normal), Paragraph("<b>Amount</b>", style_normal), '']
        tax_summary_data.extend([header1, header2])
        col_widths = [4*cm, 4*cm, 3*cm, 4*cm, 4*cm]

    total_taxable_value, total_cgst, total_sgst, total_igst = (D(0), D(0), D(0), D(0))
    for hsn, data in hsn_summary.items():
        taxable_value, gst_rate = data['taxable_value'], data['gst_rate']
        total_taxable_value += taxable_value
        row = [hsn, Paragraph(f"{taxable_value:.2f}", style_right)]
        if is_intra_state:
            cgst_amount = (taxable_value * (gst_rate / 2) / 100).quantize(D("0.01"))
            total_cgst += cgst_amount
            total_sgst += cgst_amount
            row.extend([f"{gst_rate/2:.2f}%", Paragraph(f"{cgst_amount:.2f}", style_right), f"{gst_rate/2:.2f}%", Paragraph(f"{cgst_amount:.2f}", style_right), Paragraph(f"{cgst_amount * 2:.2f}", style_right)])
        else:
            igst_amount = (taxable_value * gst_rate / 100).quantize(D("0.01"))
            total_igst += igst_amount
            row.extend([f"{gst_rate:.2f}%", Paragraph(f"{igst_amount:.2f}", style_right), Paragraph(f"{igst_amount:.2f}", style_right)])
        tax_summary_data.append(row)

    total_row = [Paragraph("<b>Total</b>", style_left_bold), Paragraph(f"<b>{total_taxable_value:.2f}</b>", style_bold_right)]
    total_tax = D(0)
    if is_intra_state:
        total_tax = total_cgst + total_sgst
        total_row.extend(['', Paragraph(f"<b>{total_cgst:.2f}</b>", style_bold_right), '', Paragraph(f"<b>{total_sgst:.2f}</b>", style_bold_right), Paragraph(f"<b>{total_tax:.2f}</b>", style_bold_right)])
    else:
        total_tax = total_igst
        total_row.extend(['', Paragraph(f"<b>{total_igst:.2f}</b>", style_bold_right), Paragraph(f"<b>{total_tax:.2f}</b>", style_bold_right)])
    tax_summary_data.append(total_row)
    
    tax_summary_table = Table(tax_summary_data, colWidths=col_widths)
    table_styles = [
        ('GRID', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]
    if is_intra_state:
        table_styles.extend([('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (2, 0), (3, 0)), ('SPAN', (4, 0), (5, 0)), ('SPAN', (6, 0), (6, 1)), ('SPAN', (0, -1), (1, -1))])
    else:
        table_styles.extend([('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (2, 0), (3, 0)), ('SPAN', (4, 0), (4, 1)), ('SPAN', (0, -1), (1, -1))])
    tax_summary_table.setStyle(TableStyle(table_styles))
    story.append(tax_summary_table)
    story.append(Spacer(1, 0.5 * cm))

    # Tax in Words
    total_tax_integer = int(total_tax)
    total_tax_paisa = int((total_tax - total_tax_integer) * 100)
    tax_words = num2words(total_tax_integer, lang='en_IN').title()
    if total_tax_paisa > 0:
        tax_words += " and " + num2words(total_tax_paisa, lang='en_IN').title() + " Paisa"
    tax_words += " Only"
    story.append(Paragraph(f"Tax Amount (in words): <b>INR {tax_words}</b>", style_normal))

    # --- Build the PDF document ---
    doc.build(story, onFirstPage=draw_page_frame, onLaterPages=draw_page_frame)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# ==============================================================================
#  STEP 2: New view to handle PDF generation request
# ==============================================================================
@login_required
def generate_invoice_pdf_view(request, invoice_id):
 
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    pdf_bytes = generate_invoice_pdf(invoice)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    
    return response

    
@login_required
def invoice_view(request):
    if request.method == 'GET':

        latest_invoice = Invoice.objects.order_by('-id').first()
        
        if latest_invoice and latest_invoice.invoice_number:
            try:
                parts = latest_invoice.invoice_number.split('-')
                number = int(parts[-1]) + 1
            except (ValueError, IndexError):
                number = 1
        else:
            number = 1
        current_year = datetime.now().year
        next_invoice_number = f"INV/{current_year}-{number:03d}"  
        
        return render(request, 'pages/invoice/invoice.html', {
            'next_invoice_number': next_invoice_number
        })

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            with transaction.atomic():
                invoice_date_str = data.get('invoice_date')
                invoice_date_obj = datetime.strptime(invoice_date_str, '%d-%m-%Y').date()

                # --- Compute grand_total and round_off BEFORE creating the invoice ---
                raw_grand_total = float(data.get('grand_total', 0.0))
                rounded_grand_total = round(raw_grand_total)
                round_off = round(rounded_grand_total - raw_grand_total, 2)

                invoice = Invoice.objects.create(
                    invoice_number=data.get('invoice_number'),
                    invoice_date=invoice_date_obj,
                    seller_name=data.get('seller_name'),
                    seller_address=data.get('seller_address'),
                    seller_gstin=data.get('seller_gstin'),
                    seller_state=data.get('seller_state'),
                    seller_state_code=data.get('seller_state_code'),
                    buyer_name=data.get('buyer_name'),
                    buyer_address=data.get('buyer_address'),
                    buyer_gstin=data.get('buyer_gstin', ''),
                    place_of_supply=data.get('place_of_supply'),
                    payment_mode=data.get('payment_mode'),
                    total_bundles=data.get('total_bundles', 0),
                    subtotal=data.get('subtotal'),
                    cgst_total=data.get('cgst_total', 0.00),
                    sgst_total=data.get('sgst_total', 0.00),
                    igst_total=data.get('igst_total', 0.00),
                    round_off=round_off,
                    transport_name=data.get('transport_name'),
                    transport_address=data.get('transport_address'),
                    transport_gstin=data.get('transport_gstin'),
                    grand_total=rounded_grand_total,
                    total_in_words=data.get('total_in_words'),
                    created_by=request.user
                )


                items_data = data.get('items', [])
                for item_data in items_data:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        description=item_data.get('description'),
                        hsn_code=item_data.get('hsn_code'),
                        quantity=item_data.get('quantity'),
                        rate=item_data.get('rate'),
                        gst_rate=item_data.get('gst_rate')
                    )

            return JsonResponse({'message': 'Invoice created successfully!', 'invoice_id': invoice.id}, status=201)

        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)

# -----------------------

@login_required
def view_invoices(request):
    return render(request, 'pages/invoice/view-invoices.html')


@login_required
def get_invoices_api(request):

    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')

    invoices = Invoice.objects.all().order_by('-invoice_date')

    if from_date_str and to_date_str:
        try:
            from_date = parse_date(from_date_str)
            to_date = parse_date(to_date_str)
            if from_date and to_date:
                invoices = invoices.filter(invoice_date__range=(from_date, to_date))
            else:
                print("⚠️ One or both dates couldn't be parsed.")
        except ValueError as e:
            print(f"❌ Error parsing dates: {e}")


    data = [{
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'buyer_name': invoice.buyer_name,
        'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
        'grand_total': str(invoice.grand_total),
    } for invoice in invoices]
              
    return JsonResponse({'invoices': data})


# ------------------------- Logout: For Template User (HTML redirect) -------------------------
def logout_view(request):
    logout(request)
    return redirect('login-page')


# ------------------------- Logout: For API Token-based Frontend -------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])  
def logout_api(request):
    request.user.auth_token.delete()  
    logout(request)
    return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


# -----------------------Edit Invoice -----------------------------------


@login_required
def edit_invoice_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)

    if request.method == 'GET':
        invoice_data = model_to_dict(invoice)
        invoice_data['invoice_date'] = invoice.invoice_date.strftime('%d-%m-%Y')

        items_data = [model_to_dict(item) for item in invoice.items.all()]
        
        context = {
            'invoice': invoice,
            'invoice_data_json': json.dumps(invoice_data, cls=DjangoJSONEncoder),
            'items_data_json': json.dumps(items_data, cls=DjangoJSONEncoder),
        }
        return render(request, 'pages/invoice/edit_invoice.html', context)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                # --- Update main Invoice ---
                invoice.invoice_date = datetime.strptime(data.get('invoice_date'), '%d-%m-%Y').date()
                invoice.buyer_name = data.get('buyer_name')
                invoice.buyer_address = data.get('buyer_address')
                invoice.buyer_gstin = data.get('buyer_gstin', '')
                invoice.place_of_supply = data.get('place_of_supply')
                invoice.payment_mode = data.get('payment_mode')
                invoice.total_bundles = data.get('total_bundles', 0)
                invoice.subtotal = data.get('subtotal')
                invoice.cgst_total = data.get('cgst_total', 0.00)
                invoice.sgst_total = data.get('sgst_total', 0.00)
                invoice.igst_total = data.get('igst_total', 0.00)
                # --- NEW ROUNDING LOGIC ---
                raw_grand_total = float(data.get('grand_total', 0.0))
                rounded_grand_total = round(raw_grand_total)
                round_off = round(rounded_grand_total - raw_grand_total, 2)

                invoice.round_off = round_off
                invoice.grand_total = rounded_grand_total
                invoice.total_in_words = data.get('total_in_words')

               
                # --- Update Transport Details ---
                invoice.transport_name = data.get('transport_name', '')
                invoice.transport_address = data.get('transport_address', '')
                invoice.transport_gstin = data.get('transport_gstin', '')

                # --- Sync Invoice Items ---
                frontend_item_ids = {item['id'] for item in data.get('items', []) if 'id' in item}
                invoice.items.exclude(id__in=frontend_item_ids).delete()

                 # Optional override: manually update updated_on
                invoice.updated_on = now()

                invoice.save()

                for item_data in data.get('items', []):
                    item_id = item_data.get('id')
                    if item_id:
                        InvoiceItem.objects.filter(id=item_id, invoice=invoice).update(
                            description=item_data.get('description'),
                            hsn_code=item_data.get('hsn_code'),
                            quantity=item_data.get('quantity'),
                            rate=item_data.get('rate'),
                            gst_rate=item_data.get('gst_rate')
                        )
                    else:
                        InvoiceItem.objects.create(
                            invoice=invoice,
                            description=item_data.get('description'),
                            hsn_code=item_data.get('hsn_code'),
                            quantity=item_data.get('quantity'),
                            rate=item_data.get('rate'),
                            gst_rate=item_data.get('gst_rate')
                        )

            return JsonResponse({'message': 'Invoice updated successfully!', 'invoice_id': invoice.id}, status=200)

        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)
