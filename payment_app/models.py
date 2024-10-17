from django.db import models

class Customer(models.Model):
    customer_id = models.CharField(max_length=255, unique=True)  
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(max_length=255,blank=True,null=True)
    customer_phone = models.CharField(max_length=15,unique=True)

    def __str__(self):
        return self.customer_id


class Order(models.Model):
    order_id = models.CharField(max_length=255, unique=True) 
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    order_amount = models.DecimalField(max_digits=10, decimal_places=2)  
    order_currency = models.CharField(max_length=10, default='INR')
    order_note = models.TextField(null=True, blank=True)
    payment_sessions_id = models.CharField(max_length=255, null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  

    def __str__(self):
        return self.order_id

class Transaction(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="transactions")
    transaction_id = models.CharField(max_length=255, unique=True) 
    payment_method = models.CharField(max_length=50)  
    payment_status = models.CharField(max_length=50, default='Pending')  
    save_instrument = models.BooleanField(default=False)  
    offer_id = models.CharField(max_length=255, null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order

class Beneficiary(models.Model):
    beneficiary_id = models.CharField(max_length=50, unique=True)  
    name = models.CharField(max_length=100)  
    email = models.EmailField(max_length=200)  
    phone = models.CharField(max_length=12,unique=True) 
    bank_account = models.CharField(max_length=18, null=True, blank=True, unique=True) 
    ifsc = models.CharField(max_length=11, null=True, blank=True)  
    vpa = models.CharField(max_length=100, null=True, blank=True)  
    address1 = models.CharField(max_length=150) 
    address2 = models.CharField(max_length=150, null=True, blank=True) 
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)  
    postal_code = models.CharField(max_length=6) 

    def __str__(self):
        return self.name