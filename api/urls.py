from django.urls import path
from . import views

urlpatterns = [
    # Public login page
    path('', views.login_view, name='login-page'),

    # API auth
    path('api/login/', views.login_api, name='login-api'),
    path('api/logout/', views.logout_api, name='logout-api'),  # for token-based frontend apps

    # Logout for HTML templates
    path('logout/', views.logout_view, name='logout'),

    # Pages (must be logged in)
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('invoice/', views.invoice_view, name='invoice'),
    path('invoice/<int:invoice_id>/pdf/', views.generate_invoice_pdf_view, name='generate-invoice-pdf'),
    path('invoice/<int:invoice_id>/edit/', views.edit_invoice_view, name='edit-invoice'),
    path('view/', views.view_invoices, name='view-invoices'),
    path('api/invoices/', views.get_invoices_api, name='api-get-invoices'),
]
