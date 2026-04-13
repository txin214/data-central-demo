from .sitework import Sitework

def sw(request):

    return {'sw': Sitework(request)}