from decimal import Decimal
import uuid
import json
import requests
from django.conf import settings
from django.db import transaction
from django.forms import ValidationError
from django.http import JsonResponse

# Rest Framework Imports
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Local App Models
from .models import * 

# Cashfree Credentials KEYS
x_client_id = "TEST379597698355e9f49312abcff4795973"
x_client_secret =  "TESTa85244521ed3349dcf149da1a167e666eab9ce93"


# ORDER CREATION
@api_view(['POST'])
def create_order(request):
    try:
        with transaction.atomic():
            customer = Customer.objects.create(
                customer_id=str(uuid.uuid4()),  
                customer_name=request.data.get('customer_name'),
                customer_email=request.data.get('customer_email'),
                customer_phone=request.data.get('customer_phone')
            )

            order = Order.objects.create(
                order_id=str(uuid.uuid4()), 
                customer=customer,  
                order_amount=request.data.get('order_amount'),
                order_currency=request.data.get('order_currency', 'INR'),
                order_note=request.data.get('order_note', 'No additional notes')
            )

            # Cashfree API URL and headers
            url = "https://sandbox.cashfree.com/pg/orders"
            headers = {
                "accept": "application/json",
                "x-api-version": "2022-09-01",
                "content-type": "application/json",
                "x-client-id": x_client_id,
                "x-client-secret": x_client_secret
            }

            order_data = {
                "order_id": order.order_id,
                "order_amount": float(order.order_amount),
                "order_currency": order.order_currency,
                "customer_details": {
                    "customer_name": customer.customer_name,
                    "customer_email": customer.customer_email,
                    "customer_phone": customer.customer_phone,
                    "customer_id": customer.customer_id,
                },
                "order_note": order.order_note
            }

            response = requests.post(url, headers=headers, json=order_data)

            if response.status_code == 200:
                response_data = response.json()
                order.payment_sessions_id = response_data.get("payment_session_id")
                order.save()

                return JsonResponse({
                    'status': 'success',
                    'message': 'Order created successfully',
                    'payment_sessions_id': response_data.get('payment_session_id'),
                    'order_id': order.order_id
                }, status=status.HTTP_200_OK)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to create order with Cashfree'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


#ORDER GET BY ORDER ID
@api_view(['GET'])
def get_order(request):
    try:
        order_id = request.data.get('order_id')

        if not order_id:
            return JsonResponse({'status': 'error', 'message': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = f"https://sandbox.cashfree.com/pg/orders/{order_id}"

        # Headers
        headers = {
            "accept": "application/json",
            "x-api-version": "2022-09-01",
            "x-client-id": x_client_id,
            "x-client-secret": x_client_secret
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'order details fetched', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': response.text}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

#ORDER PAY
@api_view(['POST'])
def process_payment(request):
    try:
        with transaction.atomic():  
            payment_session_id = request.data.get('payment_session_id')
            payment_method = request.data.get('payment_method')
            save_instrument = request.data.get('save_instrument', False)
            offer_id = request.data.get('offer_id', None)

            if not payment_session_id:
                return JsonResponse({'status': 'error','message': 'payment_session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            order = Order.objects.filter(payment_sessions_id=payment_session_id).first()
            if not order:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Order not found for the given payment session ID'
                }, status=status.HTTP_404_NOT_FOUND)

            cashfree_url = "https://sandbox.cashfree.com/pg/orders/sessions"

            headers = {
                "x-api-version": "2022-09-01",
                "x-request-id": str(uuid.uuid4()),  
                "x-idempotency-key": str(uuid.uuid4()),  
                "Content-Type": "application/json",
                "Authorization": "Bearer TESTa85244521ed3349dcf149da1a167e666eab9ce93"  
            }

            data = {
                "payment_session_id": payment_session_id,
                "payment_method": payment_method,
                "save_instrument": save_instrument
            }

            if offer_id is not None:
                data["offer_id"] = offer_id

            response = requests.post(cashfree_url, json=data, headers=headers)

            if response.status_code == 200:
                response_data = response.json()
                payment_status = response_data.get('payment_status', 'Success')  
                
                transactions = Transaction.objects.create(
                    order=order,
                    transaction_id=str(uuid.uuid4()), 
                    payment_method=payment_method,
                    payment_status=payment_status,
                    save_instrument=save_instrument,
                    offer_id=offer_id
                )

                return JsonResponse({
                    'status': 'success',
                    'message': 'Payment processed successfully',
                    'data':response.json(),
                    'transaction_id': transactions.transaction_id,
                    'payment_status': transactions.payment_status
                }, status=status.HTTP_200_OK)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Payment processing failed',
                    'data': response.json()
                }, status=response.status_code)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    
#GET PAYMENTS FOR AN ORDER
@api_view(['GET'])
def get_payments_for_an_order(request):
    try:
        with transaction.atomic():  
            order_id = request.data.get('order_id')
            
            if not order_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'order_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/payments"

            headers = {
                "accept": "application/json",
                "x-api-version": "2022-09-01",
                "x-request-id": "4dfb9780-46fe-11ee-be56-0242ac120002",
                "x-idempotency-key": "47bf8872-46fe-11ee-be56-0242ac120002",
                "x-client-id": x_client_id,
                "x-client-secret": x_client_secret
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Payments fetched successfully',
                    'data': response.json()
                }, status=status.HTTP_200_OK, safe=False)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to fetch payments',
                }, status=response.status_code)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

#GET PAYMENT BY ID
@api_view(['GET'])
def get_payment_by_id(request):
    try:
        order_id = request.data.get('order_id')
        cf_payment_id = request.data.get('cf_payment_id')

        if not order_id or not cf_payment_id:
            return JsonResponse({
                "status": "failure",
                "message": "order_id and cf_payment_id are required",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)

        # API URL
        url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/payments/{cf_payment_id}"

        # Headers
        headers = {
            "accept": "application/json",
            "x-api-version": "2022-09-01",
            "x-client-id": x_client_id,  
            "x-client-secret": x_client_secret
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return JsonResponse({
                "status": "success",
                "message": "Payment details retrieved successfully",
                "data": response.json()
            }, status=status.HTTP_200_OK)
        else:
            return JsonResponse({
                "status": "error",
                "message": "Failed to retrieve payment details",
                "data": response.json()
            }, status=response.status_code)

    except Exception as e:
        return JsonResponse({
            "status": "erorr",
            "message":str(e),
            "data": None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#CREATE REFUND
@api_view(['POST'])
def create_refund(request):
    try:
        order_id = request.data.get('order_id')
        refund_amount = request.data.get('refund_amount')
        refund_id = str(uuid.uuid4()) 
        # refund_note = request.data.get('refund_note', '')  
        # refund_speed = request.data.get('refund_speed', 'STANDARD') 
        # refund_splits = request.data.get('refund_splits', [])  

        if not order_id or not refund_amount:
            return JsonResponse({'status': 'error', 'message': 'order_id and refund_amount are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(order_id=order_id)
        except Order.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)


        existing_transaction = Transaction.objects.filter(order=order, payment_status='Refunded').first()
        if existing_transaction:
            return JsonResponse({'status': 'error', 'message': 'Refund has already been issued for this order'}, status=status.HTTP_400_BAD_REQUEST)


        if Decimal(refund_amount) != order.order_amount:
            return JsonResponse({'status': 'error', 'message': 'Refund amount does not match the order amount'}, status=status.HTTP_400_BAD_REQUEST)


        url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/refunds"

        headers = {
            "accept": "application/json",
            "x-api-version": "2022-09-01",
            "content-type": "application/json",
            "x-client-id": x_client_id,
            "x-client-secret": x_client_secret
        }


        payload = {
            "refund_amount": refund_amount, 
            "refund_id": refund_id,
            # "refund_note": refund_note,
            # "refund_speed": refund_speed,
            # "refund_splits": refund_splits
        }

        response = requests.post(url, json=payload, headers=headers)

        with transaction.atomic(): 
            if response.status_code == 200:
                Transaction.objects.create(
                    order=order,
                    transaction_id=refund_id,  
                    payment_method='Refund',  
                    payment_status='Refunded',
                    save_instrument=False 
                )

                return JsonResponse({'status': 'success', 'message':'Refund request successful', 'data': response.json()}, status=status.HTTP_200_OK)

        return JsonResponse({'status': 'error', 'message': 'Refund request failed', 'data': response.json()}, status=response.status_code)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#GET ALL REFUNDS FOR AN ORDER
@api_view(['GET'])
def get_all_refunds_for_an_order(request):
    try:
        order_id = request.data.get('order_id')
        if not order_id:
            return JsonResponse({'status': 'error', 'message': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/refunds"

        headers = {
            "accept": "application/json",
            "x-api-version": "2022-09-01",
            "content-type": "application/json",
            "x-client-id": x_client_id,
            "x-client-secret": x_client_secret
        }

        response = requests.get(url, headers=headers)

        return JsonResponse({'status': 'success', 'message':'Refund data retrieved successful','data': response.json()},status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#GET REFUND BY ID
@api_view(['GET'])
def get_refund(request):
    try:
        order_id = request.data.get('order_id')
        refund_id = request.data.get('refund_id')
        if not order_id:
            return JsonResponse({'status': 'error', 'message': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/refunds/{refund_id}"

        headers = {
            "accept": "application/json",
            "x-api-version": "2022-09-01",
            "content-type": "application/json",
            "x-client-id": x_client_id,
            "x-client-secret": x_client_secret
            }

        response = requests.get(url, headers=headers)

        return JsonResponse({'status': 'success', 'message':'Refund data retrieved successful','data': response.json()},status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#GET SETTELMENTS BY ORDER ID
@api_view(['GET'])
def get_settlements_for_an_order(request):
    try:
        order_id = request.data.get('order_id')
        if not order_id:
            return JsonResponse({'status': 'error', 'message': 'order_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = f"https://sandbox.cashfree.com/pg/orders/{order_id}/settlements"

        headers = {
            "accept": "application/json",
            "x-api-version": "2022-09-01",
            "content-type": "application/json",
            "x-client-id": x_client_id,
            "x-client-secret": x_client_secret
            }

        response = requests.get(url, headers=headers)

        return JsonResponse({'status': 'success', 'message':'Settlement data retrieved successful','data': response.json()},status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


#===================PAYOUT========================>

x_client_idV2='CF379597CR4QJ3VPU07S7391HLIG'
x_client_secretV2='cfsk_ma_test_579d140d50ce6d479c922805f91c1f9a_747f96ec'


#CREATE BENEFICIARY
@api_view(['POST'])
def create_beneficiary(request):
    try:
        with transaction.atomic():
            beneficiary_id = request.data.get('beneficiary_id')
            name = request.data.get('beneficiary_name')
            email = request.data.get('beneficiary_email')
            phone = request.data.get('beneficiary_phone')
            bank_account = request.data.get('bank_account_number', None)
            ifsc = request.data.get('bank_ifsc', None)
            vpa = request.data.get('vpa', None)
            address1 = request.data.get('beneficiary_address')
            address2 = request.data.get('address2', None)
            city = request.data.get('beneficiary_city')
            state = request.data.get('beneficiary_state')
            postal_code = request.data.get('beneficiary_postal_code')

            # Validations
            if not name or not email or not phone or not address1 or not city or not state or not postal_code:
                return JsonResponse({'status': 'error', 'message': 'Required fields are missing'}, status=status.HTTP_400_BAD_REQUEST)

            # Cashfree API request
            url = "https://sandbox.cashfree.com/payout/beneficiary"
            headers = {
                "accept": "application/json",
                "x-api-version": "2024-01-01",
                "x-request-id": str(uuid.uuid4()),
                "content-type": "application/json",
                "x-client-id": x_client_idV2,  
                "x-client-secret": x_client_secretV2  
            }

            data = {
                "beneficiary_id": beneficiary_id,
                "beneficiary_name": name,
                "beneficiary_instrument_details": {
                    "bank_account_number": bank_account,
                    "bank_ifsc": ifsc,
                    "vpa": vpa
                },
                "beneficiary_contact_details": {
                    "beneficiary_email": email,
                    "beneficiary_phone": phone,
                    "beneficiary_country_code": "+91",
                    "beneficiary_address": address1,
                    "beneficiary_city": city,
                    "beneficiary_state": state,
                    "beneficiary_postal_code": postal_code
                },
                "beneficiary_purpose": "AMAZON_UPI_BENE"
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))
            # print(response.json())
            # print(response.status_code,'-------------')

            if response.status_code == 201:
                Beneficiary.objects.create(
                    beneficiary_id=beneficiary_id,
                    name=name,
                    email=email,
                    phone=phone,
                    bank_account=bank_account,
                    ifsc=ifsc,
                    vpa=vpa,
                    address1=address1,
                    address2=address2,
                    city=city,
                    state=state,
                    postal_code=postal_code
                )
                return JsonResponse({'status': 'success', 'message': 'Beneficiary created successfully', 'data': response.json()}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({'status': 'error', 'message': 'Failed to create beneficiary', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#GET BENEFICIARIESY DETAILS
@api_view(['GET'])
def get_beneficiary(request):
    try:
        beneficiary_id = request.data.get('beneficiary_id')
        bank_account_number = request.data.get('bank_account_number')
        bank_ifsc = request.data.get('bank_ifsc')
        print(  )

        if not beneficiary_id and (not bank_account_number or not bank_ifsc):
            return JsonResponse({'status': 'error', 'message': 'Either beneficiary_id or both bank_account_number and bank_ifsc must be provided'},status=status.HTTP_400_BAD_REQUEST)

        if beneficiary_id:
            url = f"https://sandbox.cashfree.com/payout/beneficiary/{beneficiary_id}"
        else:
            url = f"https://sandbox.cashfree.com/payout/beneficiary?bank_account_number={bank_account_number}&bank_ifsc={bank_ifsc}"

        headers = {
            "accept": "application/json",
            "x-api-version": "2024-01-01",
            "content-type": "application/json",
            "x-client-id": x_client_idV2,  
            "x-client-secret": x_client_secretV2
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return JsonResponse(
                {'status': 'success', 'message': 'Beneficiary details fetched successfully', 'data': response.json()},
                status=status.HTTP_200_OK
            )
        else:
            return JsonResponse(
                {'status': 'error', 'message': 'Failed to fetch beneficiary details', 'data': response.json()},
                status=response.status_code
            )

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
# #GET BANEFICIARIES ID
# @api_view(['GET'])
# def get_beneficiary_id(request):
#     try:
#         bankAccount = request.data.get('bankAccount')
#         ifsc = request.data.get('ifsc')

#         if not bankAccount:
#             return JsonResponse({'status': 'error', 'message': 'beneId is required'}, status=status.HTTP_400_BAD_REQUEST)

#         if not ifsc:
#             return JsonResponse({'status': 'error', 'message': 'beneId is required'}, status=status.HTTP_400_BAD_REQUEST)

#         url = f"https://payout-gamma.cashfree.com/payout/v1/getBeneId?bankAccount={bankAccount}&ifsc={ifsc}"

#         headers = {
#             "accept": "application/json",
#             "x-api-version": "2022-09-01",
#             "content-type": "application/json",
#             "Authorization": f"Bearer {x_client_secret}",
#             "x-client-id": x_client_id,  
#             "x-client-secret": x_client_secret
#         }

#         response = requests.get(url, headers=headers)

#         if response.status_code == 200:
#             return JsonResponse({'status': 'success', 'message': 'Beneficiary ID fetched successfully', 'data': response.json()}, status=status.HTTP_200_OK)
#         else:
#             return JsonResponse({'status': 'error', 'message': 'Failed to fetch beneficiary ID', 'data': response.json()}, status=response.status_code)

#     except Exception as e:
#         return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

#REMOVE BENEFICIARY
@api_view(['POST'])
def remove_beneficiary(request):
    beneficiary_id = request.data.get('beneficiary_id')  
    if not beneficiary_id:
        return JsonResponse({"success": False, "message": "Beneficiary ID is required."}, status=status.HTTP_400_BAD_REQUEST)

    url = f"https://sandbox.cashfree.com/payout/beneficiary?beneficiary_id={beneficiary_id}"
    
    # Set the required headers
    headers = {
        "accept": "application/json",
        "x-api-version": "2024-01-01",
        "x-client-id": x_client_idV2,  
        "x-client-secret": x_client_secretV2
    }

    try:
        response = requests.delete(url, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            return JsonResponse({"success": True, "message": "Beneficiary removed successfully", "data": response_data}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({"success": False, "message": "Failed to remove beneficiary", "data": response_data}, status=response.status_code)

    except Exception as e:
        return JsonResponse({"success": False, "message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#STANDARD TRANSFER
@api_view(['POST'])
def standard_transfer(request):
    beneficiary_id = request.data.get('beneficiary_id')
    transfer_id = request.data.get('transfer_id')
    amount = request.data.get('amount')  
    transfer_currency = request.data.get('transfer_currency')
    transfer_mode = request.data.get('transfer_mode')
    
    if not transfer_id:
        return JsonResponse({'status': 'error', 'message': 'transfer_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not amount:
        return JsonResponse({'status': 'error', 'message': 'amount is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not beneficiary_id:
        return JsonResponse({'status': 'error', 'message': 'beneficiary_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    url = "https://sandbox.cashfree.com/payout/transfers"

    payload = {
        "beneficiary_details": {"beneficiary_id": beneficiary_id},
        "transfer_id": transfer_id,
        "transfer_amount": amount, 
        "transfer_currency": transfer_currency,
        "transfer_mode": transfer_mode
    }

    headers = {
        "accept": "application/json",
        "x-api-version": "2024-01-01",
        "x-client-id": x_client_idV2,  
        "x-client-secret": x_client_secretV2
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'Transfer initiated successfully', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to initiate transfer', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
#GET TRANSERS
@api_view(['GET'])
def get_transfer(request):
    cf_transfer_id = request.data.get('cf_transfer_id')
    transfer_id = request.data.get('transfer_id')

    print(cf_transfer_id, transfer_id)

    if not cf_transfer_id and not transfer_id:
        return JsonResponse({
            "success": 'error',
            "message": "Either 'cf_transfer_id' or 'transfer_id' must be provided."
        }, status=status.HTTP_400_BAD_REQUEST)

    url = "https://sandbox.cashfree.com/payout/v1.2/"
    params = {
        "cf_transfer_id": cf_transfer_id,
        "transfer_id": transfer_id
    }
    
    headers = {
        "accept": "application/json",
        "x-api-version": "2024-01-01",
        "x-client-id": x_client_idV2,  
        "x-client-secret": x_client_secretV2
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response_data = response.json()

        if response.status_code == 200:
            return JsonResponse({
                "success": 'success',
                "data": response_data
            }, status=status.HTTP_200_OK)
        else:
            return JsonResponse({
                "success": 'error',
                "message": response_data.get('message', 'Unable to fetch transfer status.')
            }, status=response.status_code)

    except Exception as e:
        return JsonResponse({
            "success": 'error',
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#=================== PAN ========================>


#VERIFY PAN
@api_view(['POST'])
def verify_pan(request):
    pan= request.data.get('pan')
    name = request.data.get('name')
    print(pan, name) 

    if not pan:
        return JsonResponse({'status','error','message','Pan Card number is requred'},status=status.HTTP_400_BAD_REQUEST_400_bad_request)
    if not name:
        return JsonResponse({'status','error','message','Name is requred'},status=status.HTTP_400_BAD_REQUEST_400_bad_request)
    
    url = "https://sandbox.cashfree.com/verification/pan"

    payload = {
        "pan": pan,
        "name": name
    }
    
    print('payload', payload)
    
    headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "x-client-id": x_client_idV2,
    "x-client-secret": x_client_secretV2
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        

        print('response',response.status_code)

        print('response____',response.json())

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'PAN verified successfully', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to verify PAN', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#GET PAN STATUS
@api_view(['GET'])
def get_pan_status(request):
    reference_id = request.data.get('reference_id')
    print('reference_id', reference_id)
    try:
        url = f"https://sandbox.cashfree.com/verification/pan/{reference_id}"
        
        headers = {
            "accept": "application/json",
            "x-client-id": "CF379597CR4QJ3VPU07S7391HLIG",
            "x-client-secret": "cfsk_ma_test_579d140d50ce6d479c922805f91c1f9a_747f96ec",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'PAN verified successfully', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse(
                {"status": "error", "status": response.json()},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except Exception as e:
        return JsonResponse(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


#VERIFY THE PAN INFORMATION
@api_view(['POST'])
def verify_pan_info(request):
    pan = request.data.get('pan')
    verification_id =request.data.get('verification_id')
    name = request.data.get('name')

    if not pan:
        return JsonResponse({'status','error','message','Pan Card number is requred'},status=status.HTTP_400_BAD_REQUEST_400_bad_request)
    
    if not name:
        return JsonResponse({'status','error','message','Name is requred'},status=status.HTTP_400_BAD_REQUEST_400_bad_request)
    
    url = "https://sandbox.cashfree.com/verification/pan/advance"

    payload ={
        'pan':pan,
        'name':name,
        'verification_id':verification_id
    }

    headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "x-client-id": x_client_idV2,
    "x-client-secret": x_client_secretV2

    }   

    try:
        response = requests.post(url, json=payload, headers=headers)
        print('response____',response.json())

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'PAN verified successfully', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to verify PAN', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ADHAR CARD
#GANERATE OTP TO VERIFY AADHAR
@api_view(['POST'])
def otp_adharcard(request):
    try:
        aadhaar_number = request.data.get('aadhaar_number')

        if not aadhaar_number:
            return JsonResponse({'status': 'error', 'message': 'Aadhaar number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = "https://sandbox.cashfree.com/verification/offline-aadhaar/otp"

        payload = { "aadhaar_number": aadhaar_number }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-client-id": x_client_idV2,  
            "x-client-secret": x_client_secretV2  
        }

        with transaction.atomic():  
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code != 200:
                return JsonResponse({'status': 'error', 'message': 'Failed to send OTP', 'data': response.json()}, status=response.status_code)

            return JsonResponse({'status': 'success', 'message': 'OTP sent successfully', 'data': response.json()}, status=status.HTTP_200_OK)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message':str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 

#Submit OTP
@api_view(['POST'])
def submit_aadhar_otp(request):
    try:
        otp = request.data.get('otp')
        ref_id = request.data.get('ref_id')

        if not otp :
            return JsonResponse({'status': 'error', 'message': 'OTP is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not ref_id :
            return JsonResponse({'status': 'error', 'message': 'ref_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = "https://sandbox.cashfree.com/verification/offline-aadhaar/verify"

        payload = {
            "otp": otp,
            "ref_id": ref_id
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-client-id": x_client_idV2,
            "x-client-secret": x_client_secretV2
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'OTP verified successfully', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to verify OTP', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Aadhar Masking
@api_view(['POST'])
def aadhaar_masking(request):
    try:
        images = request.FILES.getlist('image')  
        verification_id = request.data.get('verification_id')

        if not images:
            return JsonResponse({'status': 'error', 'message': 'File path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            file = images[0]  
            files = {
                "image": (file.name, file.read(), file.content_type)
            }

            payload = {
                'verification_id': verification_id
            }

            headers = {
                'accept': 'application/json',
                'x-client-id': 'CF379597CR4QJ3VPU07S7391HLIG',
                'x-client-secret': 'cfsk_ma_test_579d140d50ce6d479c922805f91c1f9a_747f96ec'
            }

            url = "https://sandbox.cashfree.com/verification/aadhaar-masking"
            response = requests.post(url, data=payload, files=files, headers=headers)

            if response.status_code == 200:
                return JsonResponse({'status': 'success', 'message': 'data retrieved', 'data': response.json()}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({'status': 'error', 'message': 'Failed to get data', 'data': response.json()}, status=response.status_code)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST) 

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#VERIFY GSTIN
@api_view(['POST'])
def gst_verification(request):
    gstin = request.data.get('GSTIN')
    business_name = request.data.get('businessName')

    if not gstin:
        return JsonResponse({'status': 'error', 'message': 'GSTIN is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not business_name:
        return JsonResponse({'status': 'error', 'message': 'businessName is required'}, status=status.HTTP_400_BAD_REQUEST)

    url = "https://sandbox.cashfree.com/verification/gstin"
    
    payload = {
        "GSTIN": gstin,
        "businessName": business_name
    }
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": "CF379597CR4QJ3VPU07S7391HLIG",
        "x-client-secret": "cfsk_ma_test_579d140d50ce6d479c922805f91c1f9a_747f96ec"
    }
    

    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        return JsonResponse({
            'status': 'success',
            'message': 'Data retrieved successfully',
            'data': response.json()
        }, status=status.HTTP_200_OK)
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to retrieve data',
            'data': response.json()
        }, status=response.status_code)
    
#FATCH  GSTIN WITH PAN
@api_view(['POST'])
def get_gstin_with_pan(request):
    try:
        pan = request.data.get('pan')
        verification_id = request.data.get('verification_id')

        if not pan:
            return JsonResponse({'status': 'error', 'message': 'pan is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not verification_id:
            return JsonResponse({'status': 'error', 'message': 'verification_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        url = "https://sandbox.cashfree.com/verification/pan-gstin"

        payload = {
            "pan": pan,
            "verification_id": verification_id
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-client-id": "CF379597CR4QJ3VPU07S7391HLIG",
            "x-client-secret": "cfsk_ma_test_579d140d50ce6d479c922805f91c1f9a_747f96ec"
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success','message': 'Data retrieved successfully','data': response.json()}, status=status.HTTP_200_OK)
    
        else:
            return JsonResponse({'status': 'error','message': 'Failed to retrieve data','data': response.json()}, status=response.status_code)
   
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#E-SIGN
#UPLOAD DOCUMENT
@api_view(['POST'])
def upload_document(request):
    try:
        document = request.FILES.getlist('document')
        
        print(document)

        if not document:
            return JsonResponse({'status': 'error', 'message': 'File path is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            file = document[0]  
            files = {
                "image": (file.name, file.read(), file.content_type)
            }

            headers = {
                'accept': 'application/json',
                'x-client-id': 'CF379597CR4QJ3VPU07S7391HLIG',
                'x-client-secret': 'cfsk_ma_test_579d140d50ce6d479c922805f91c1f9a_747f96ec'
            }

            url = "https://sandbox.cashfree.com/verification/esignature/document"
            response = requests.post(url, files=files, headers=headers)

            if response.status_code == 200:
                return JsonResponse({'status': 'success', 'message': 'data retrieved', 'data': response.json()}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({'status': 'error', 'message': 'Failed to get data', 'data': response.json()}, status=response.status_code)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST) 

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

#CREATE E-SIGN
@api_view(['POST'])
def create_esign_request(request):
    try:
        verification_id = request.data.get("verification_id")
        document_id = request.data.get("document_id")
        auth_type = request.data.get("auth_type")
        expiry_in_days = request.data.get("expiry_in_days")
        signers = request.data.get("signers")
        redirect_url = request.data.get("redirect_url",)
        notification_modes = request.data.get("notification_modes")

        payload = {
            "verification_id": verification_id,
            "document_id": document_id,
            "auth_type": auth_type,
            "expiry_in_days": expiry_in_days,
            "signers": signers,
            "redirect_url": redirect_url,
            "notification_modes": notification_modes
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-client-id": x_client_idV2,
            "x-client-secret": x_client_secretV2
        }

        url = "https://sandbox.cashfree.com/verification/esignature"

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success','message': 'E-Sign request created successfully','data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error','message': 'Failed to create E-Sign request','data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error','message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Get E-Sign Status
@api_view(['GET'])
def get_esign_status(request):
    try:
        reference_id = request.data.get("reference_id")
        verification_id = request.data.get("verification_id")
        print(reference_id, verification_id)

        if not reference_id:
            return JsonResponse({'status': 'error', 'message': 'reference_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not verification_id:
            return JsonResponse({'status': 'error', 'message': 'verification_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        

        url = f"https://sandbox.cashfree.com/verification/esignature?reference_id={reference_id}&verification_id={verification_id}"
        print(url)

        headers = {
            "accept": "application/json",
            "x-client-id": x_client_idV2,
            "x-client-secret": x_client_secretV2
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'data retrieved', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to get data', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

#UPI VERSION 2
#UPI Verification V2
@api_view(['POST'])
def verify_upi_infoV2(request):
    try:
        verification_id = request.data.get('verification_id')
        name = request.data.get('name')
        vpa = request.data.get('vpa')

        if not verification_id:
            return JsonResponse({'status': 'error', 'message': 'verification_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not name:
            return JsonResponse({'status': 'error', 'message': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not vpa:
            return JsonResponse({'status': 'error', 'message': 'vpa is required'}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
        "verification_id": verification_id,
        "name": name,
        "vpa": vpa
        }

        headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-client-id": x_client_idV2,
        "x-client-secret": x_client_secretV2
        }

        url = "https://sandbox.cashfree.com/verification/upi"

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'data retrieved', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to get data', 'data': response.json()}, status=response.status_code)
    except Exception as e:  
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#Get Status of UPI Verification V2 
@api_view(['GET'])
def get_upi_statusV2(request):
    try:
        reference_id = request.data.get('reference_id')
        verification_id = request.data.get('verification_id')

        if not reference_id:
            return JsonResponse({'status': 'error', 'message': 'reference_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not verification_id:
            return JsonResponse({'status': 'error', 'message': 'verification_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        

        url = f"https://sandbox.cashfree.com/verification/upi?reference_id={reference_id}&verification_id={verification_id}"
        headers = {
            "accept": "application/json",
            "x-client-id": x_client_idV2,
            "x-client-secret": x_client_secretV2
        }

        response = requests.get(url, headers=headers)
        print(response.json(),response.status_code)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'data retrieved', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to get data', 'data': response.json()}, status=response.status_code)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#MOBILE 360
@api_view(['POST'])
def mobile_360(request):
    try:
        print()
        verification_id = request.data.get('verification_id')
        mobile_number = request.data.get('mobile_number')
        name = request.data.get('name')
        typ = request.data.get('type')
        consent_desc = request.data.get('consent_desc')

        if not verification_id:
            return JsonResponse({'status': 'error', 'message': 'verification_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not mobile_number:
            return JsonResponse({'status': 'error', 'message': 'mobile_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not name:
            return JsonResponse({'status': 'error', 'message': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not typ:
            return JsonResponse({'status': 'error', 'message': 'type is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not consent_desc:
            return JsonResponse({'status': 'error', 'message': 'consent_desc is required'}, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            "verification_id": verification_id,
            "mobile_number": mobile_number,
            "name": name,
            "type": typ,
            "consent_desc": consent_desc
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-client-id": x_client_idV2,
            "x-client-secret": x_client_secretV2
        }

        url = "https://sandbox.cashfree.com/verification/mobile360/otpless"

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'data retrieved', 'data': response.json()}, status=status.HTTP_200_OK)
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to get data', 'data': response.json()}, status=response.status_code)
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


