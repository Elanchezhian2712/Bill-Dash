import json
import traceback
from django.http import JsonResponse
from django.shortcuts import render, redirect
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
from django.shortcuts import render 
from datetime import date
from django.db.models import Sum, Count

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
@login_required
def dashboard_view(request):
    # Get the current date to determine the current month
    today = date.today()
    first_day_of_month = today.replace(day=1)
    total_invoice_count = Invoice.objects.count()
    total_invoiced_amount_agg = Invoice.objects.aggregate(total=Sum('grand_total'))
    total_invoiced_amount = total_invoiced_amount_agg['total'] or 0
    invoices_this_month = Invoice.objects.filter(invoice_date__gte=first_day_of_month)
    invoices_this_month_count = invoices_this_month.count()
    amount_this_month_agg = invoices_this_month.aggregate(total=Sum('grand_total'))
    amount_this_month = amount_this_month_agg['total'] or 0
    total_clients_count = Invoice.objects.values('buyer_name').distinct().count()
    buyers_this_month = set(invoices_this_month.values_list('buyer_name', flat=True).distinct())
    buyers_before_this_month = set(Invoice.objects.filter(invoice_date__lt=first_day_of_month).values_list('buyer_name', flat=True).distinct())
    new_clients_count = len(buyers_this_month - buyers_before_this_month)

    context = {
        'total_invoice_count': total_invoice_count,
        'total_invoiced_amount': total_invoiced_amount,
        'invoices_this_month_count': invoices_this_month_count,
        'amount_this_month': amount_this_month,
        'total_clients_count': total_clients_count,
        'new_clients_count': new_clients_count
    }

    return render(request, 'pages/dashboard/dashboard.html', context)

@login_required
def invoice_view(request):
    if request.method == 'GET':
        # Get the latest invoice_number
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
                    round_off=data.get('round_off', 0.00),
                    grand_total=data.get('grand_total'),
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
