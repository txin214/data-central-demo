from .models import models
from crm.models import Customer
# see context_processors.py

# this is the "cart" used for a sitework quote
class Sitework():
  
    def __init__(self, request):
        self.session = request.session
        # Returning user - obtain his/her existing session
        swquote = self.session.get('session_akb')

        # New user - generate a new session
        if 'session_akb' not in request.session:
            swquote = self.session['session_akb'] = {}

        self.swquote = swquote

    def add(self, catid, subcatid, qty):

        #product_id = str(product.id)
        if product_id in self.cart:

            self.cart[product_id]['qty'] = product_qty

        else:

            self.cart[product_id] = {'price': str(product.price), 'qty': product_qty}


        self.session.modified = True 