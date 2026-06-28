from django.conf import settings
from django.utils.deconstruct import deconstructible
from storages.backends.s3boto3 import S3Boto3Storage


@deconstructible
class JobAttachmentStorage(S3Boto3Storage):
    """Private Tigris storage for job attachments."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('access_key', settings.JOB_ATTACHMENTS_TIGRIS_ACCESS_KEY_ID)
        kwargs.setdefault('secret_key', settings.JOB_ATTACHMENTS_TIGRIS_SECRET_ACCESS_KEY)
        kwargs.setdefault('bucket_name', settings.JOB_ATTACHMENTS_TIGRIS_BUCKET_NAME)
        kwargs.setdefault('endpoint_url', settings.S3_ENDPOINT_URL)
        kwargs.setdefault('region_name', settings.S3_REGION_NAME)
        kwargs.setdefault('default_acl', settings.JOB_ATTACHMENTS_TIGRIS_DEFAULT_ACL)
        kwargs.setdefault('file_overwrite', settings.JOB_ATTACHMENTS_TIGRIS_FILE_OVERWRITE)
        kwargs.setdefault('querystring_auth', True)
        kwargs.setdefault('querystring_expire', settings.JOB_ATTACHMENTS_TIGRIS_SIGNED_URL_EXPIRES)
        super().__init__(*args, **kwargs)

    def get_available_name(self, name, max_length=None):
        return str(name).replace('\\', '/')


job_attachment_storage = JobAttachmentStorage()
