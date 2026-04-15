# Create your tasks here
# Django will hand these off to Celery/Redis for background processing.

from .models import SiteworkCat, SiteworkSubCat, SiteworkQuoteLine
from celery import shared_task
from celery import Celery
from django.conf import settings


celery_app = Celery("tasks", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_BROKER_URL)


@shared_task 
@celery_app.task
def subcreate(swquote_id):
    # Now create the siteworkquoteline items
    # every new sitework quote gets a copied group of them into SiteworkQuoteLine
    # currently there are around 900 of them.

    cats = SiteworkCat.objects.order_by('orderby')
    for c in cats:
        subcats = SiteworkSubCat.objects.filter(siteworkcat=c, status="A").order_by('orderby')
        for s in subcats:
            # print ("quote create sitework item: ",c.id," ",s.id)
            #SiteworkQuoteLine.objects.add_lineitem(s.id, swquote_id)
            qitem = SiteworkQuoteLine.objects.add_lineitem(s.id, swquote_id)

    return None
