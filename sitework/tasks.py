# Create your tasks here
# Django will hand these off to Celery/Redis for background processing.

from .models import SiteworkCat, SiteworkSubCat, SiteworkQuoteLine
from celery import shared_task
from celery import Celery
from django.conf import settings


celery_app = Celery("tasks", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_BROKER_URL)





@shared_task(bind=True)
def subcreate(self, swquote_id, total_count):
    # Now create the siteworkquoteline items
    # every new sitework quote gets a copied group of them into SiteworkQuoteLine
    # currently there are around 900 of them.
    from celery import current_task
    print(f"CELERY TASK STARTED: subcreate for quote_id={swquote_id}, total_count={total_count}")
    print(f"DEBUG TASK: app.backend={self.app.backend}")
    print(f"DEBUG TASK: task_id={self.request.id}")
    count = 0
    # Set initial progress
    self.update_state(
        state='PROGRESS',
        meta={'current': count, 'total': total_count, 'percent': 0}
    )
    cats = SiteworkCat.objects.order_by('orderby')
    for c in cats:
        subcats = SiteworkSubCat.objects.filter(siteworkcat=c, status="A").order_by('orderby')
        for s in subcats:
            qitem = SiteworkQuoteLine.objects.add_lineitem(s.id, swquote_id)
            count += 1
            # Update progress every 10 items or on completion
            if count % 10 == 0 or count == total_count:
                self.update_state(
                    state='PROGRESS',
                    meta={'current': count, 'total': total_count, 'percent': int((count / total_count) * 100)}
                )
    print(f"CELERY TASK COMPLETED: subcreate processed {count} items")
    return {'current': count, 'total': total_count, 'status': 'Completed'}
