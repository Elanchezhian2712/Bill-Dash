import json
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
    return render(request, 'pages/dashboard/dashboard.html')

@login_required
def invoice_view(request):
    if request.method == 'GET':
        return render(request, 'pages/invoice/invoice.html')

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)

            # --- START OF VALIDATION AND CLEANING ---
            
            # Clean and validate Buyer GSTIN
            buyer_gstin = data.get('buyer_gstin', '').strip().upper()
            if buyer_gstin and len(buyer_gstin) != 15:
                return JsonResponse({'error': f'Invalid Buyer GSTIN. It must be 15 characters long, but it was {len(buyer_gstin)}.'}, status=400)
            
            # Clean and validate Seller GSTIN (good practice, even if readonly)
            seller_gstin = data.get('seller_gstin', '').strip().upper()
            if len(seller_gstin) != 15:
                 return JsonResponse({'error': f'Invalid Seller GSTIN. It must be 15 characters long.'}, status=400)
                 
            # --- END OF VALIDATION AND CLEANING ---

            with transaction.atomic():
                invoice_date_obj = datetime.strptime(data.get('invoice_date'), '%d-%m-%Y').date()

                invoice = Invoice.objects.create(
                    invoice_number=data.get('invoice_number'),
                    invoice_date=invoice_date_obj,
                    
                    # Use the cleaned GSTIN values
                    seller_gstin=seller_gstin,
                    buyer_gstin=buyer_gstin,
                    
                    # The rest of your fields...
                    seller_name=data.get('seller_name'),
                    seller_address=data.get('seller_address'),
                    seller_state=data.get('seller_state'),
                    seller_state_code=data.get('seller_state_code'),
                    buyer_name=data.get('buyer_name'),
                    buyer_address=data.get('buyer_address'),
                    place_of_supply=data.get('place_of_supply'),
                    payment_mode=data.get('payment_mode'),
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
                        bundles=item_data.get('bundles') or None,
                        hsn_code=item_data.get('hsn_code'),
                        quantity=item_data.get('quantity'),
                        rate=item_data.get('rate'),
                        gst_rate=item_data.get('gst_rate')
                    )

            return JsonResponse({'message': 'Invoice created successfully!', 'invoice_id': invoice.id}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except KeyError as e:
            return JsonResponse({'error': f'Missing required field: {str(e)}'}, status=400)
        except Exception as e:
            # Now this will only catch other unexpected errors
            return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)




@login_required
def view_invoices(request):
    return render(request, 'pages/invoice/view-invoices.html')


@login_required
def get_invoices_api(request):

    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')

    print(f"🛎️ API Request: from_date={from_date_str}, to_date={to_date_str}")

    invoices = Invoice.objects.all().order_by('-invoice_date')

    # Apply date filtering if dates are provided and valid
    if from_date_str and to_date_str:
        try:
            from_date = parse_date(from_date_str)
            to_date = parse_date(to_date_str)
            if from_date and to_date:
                invoices = invoices.filter(invoice_date__range=(from_date, to_date))
                # print(f"📅 Filtering invoices between {from_date} and {to_date}")
            else:
                print("⚠️ One or both dates couldn't be parsed.")
        except ValueError as e:
            print(f"❌ Error parsing dates: {e}")

    # print(f"📦 Total invoices fetched: {invoices.count()}")

    data = [{
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'buyer_name': invoice.buyer_name,
        'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d'),
        'grand_total': str(invoice.grand_total),
    } for invoice in invoices]


    # for preview in data[:3]:
    #     print(f"🧾 Invoice: {preview}")
              
    return JsonResponse({'invoices': data})


# ------------------------- Logout: For Template User (HTML redirect) -------------------------
def logout_view(request):
    logout(request)
    return redirect('login-page')


# ------------------------- Logout: For API Token-based Frontend -------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # requires auth token
def logout_api(request):
    request.user.auth_token.delete()  # delete token
    logout(request)
    return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)
