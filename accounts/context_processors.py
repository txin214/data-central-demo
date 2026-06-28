from django.conf import settings


def forms_bucket(request):
    return {
        'forms_public_base_url': settings.FORMS_TIGRIS_PUBLIC_BASE_URL,
    }
