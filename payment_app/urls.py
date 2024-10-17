# Django imports
from django.urls import path

# Project-specific imports
from .views import *

urlpatterns = [
    # Orders
    path('create_order/', create_order, name='create_order'),
    path('get_order/', get_order, name='get_order'),

    # Payments
    path('process_payment/', process_payment, name='process_payment'),
    path('get_payments_for_order/', get_payments_for_an_order, name='get_payments_for_order'),
    path('get_payment_by_id/', get_payment_by_id, name='get_payment_by_id'),

    # Refunds
    path('create_refund/', create_refund, name='create_refund'),
    path('get_refunds_for_order/', get_all_refunds_for_an_order, name='get_refunds_for_order'),
    path('get_refund/', get_refund, name='get_refund'),

    # Settlements
    path('get_settlements_for_order/', get_settlements_for_an_order, name='get_settlements_for_order'),

    # Beneficiaries
    path('create_beneficiary/', create_beneficiary, name='create_beneficiary'),
    path('get_beneficiary/', get_beneficiary, name='get_beneficiary'),
    path('remove_beneficiary/', remove_beneficiary, name='remove_beneficiary'),

    # Transactions
    path('standard_transfer/', standard_transfer, name='standard_transfer'),
    path('get_transfer/', get_transfer, name='get_transfer'),

    # Secure ID
    # PAN Verification
    path('verify_pan/', verify_pan, name='verify_pan'),
    path('verify_pan_status/', get_pan_status, name='verify_pan_status'),
    path('verify_pan_info/', verify_pan_info, name='verify_pan_info'),

    # Aadhaar Verification
    path('otp_aadhaar/', otp_adharcard, name='otp_aadhaar'),
    path('submit_aadhaar_otp/', submit_aadhar_otp, name='submit_aadhaar_otp'),
    path('aadhaar_masking/', aadhaar_masking, name='aadhaar_masking'),

    # GSTIN Verification
    path('gst_verification/', gst_verification, name='gst_verification'),
    path('get_gstin_with_pan/', get_gstin_with_pan, name='get_gstin_with_pan'),

    #E-Sign
    path('upload_document/', upload_document, name='upload-document'),
    path('create_esign_request/', create_esign_request, name='create-esign-request'),
    path('esign_status/', get_esign_status, name='esign-status'),

    #UPI Verification
    path('verify_upi_infoV2/', verify_upi_infoV2, name='verify-upi-infoV2'),
    path('get_upi_statusV2/', get_upi_statusV2, name='get-upi-statusV2'),

    #Mobile 360
    path('mobile_360/',mobile_360,name='mobile-360') 
]
