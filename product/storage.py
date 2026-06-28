import boto3
from botocore.client import Config
from django.conf import settings
from django.utils.deconstruct import deconstructible
from storages.backends.s3boto3 import S3Boto3Storage


def strip_product_image_prefix(name):
    """Map Django's product_images/... names to the bucket's real key layout."""
    normalized_name = str(name).replace('\\', '/').lstrip('/')
    strip_prefix = getattr(settings, 'PRODUCT_IMAGE_PUBLIC_STRIP_PREFIX', '')
    if strip_prefix and normalized_name.startswith(strip_prefix):
        return normalized_name[len(strip_prefix):]
    return normalized_name


@deconstructible
class TigrisProductImageStorage(S3Boto3Storage):
    """Tigris storage for product images while preserving existing DB file names."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('access_key', settings.PRODUCT_IMAGES_TIGRIS_ACCESS_KEY_ID)
        kwargs.setdefault('secret_key', settings.PRODUCT_IMAGES_TIGRIS_SECRET_ACCESS_KEY)
        kwargs.setdefault('bucket_name', settings.PRODUCT_IMAGES_TIGRIS_BUCKET_NAME)
        kwargs.setdefault('endpoint_url', settings.S3_ENDPOINT_URL)
        kwargs.setdefault('region_name', settings.S3_REGION_NAME)
        kwargs.setdefault('default_acl', settings.PRODUCT_IMAGES_TIGRIS_DEFAULT_ACL)
        kwargs.setdefault('file_overwrite', settings.PRODUCT_IMAGES_TIGRIS_FILE_OVERWRITE)
        kwargs.setdefault('querystring_auth', False)
        kwargs.setdefault('object_parameters', {
            'CacheControl': settings.PRODUCT_IMAGES_TIGRIS_CACHE_CONTROL,
        })
        super().__init__(*args, **kwargs)

    def _save(self, name, content):
        original_name = str(name).replace('\\', '/').lstrip('/')
        super()._save(strip_product_image_prefix(original_name), content)
        return original_name

    def exists(self, name):
        return super().exists(strip_product_image_prefix(name))

    def delete(self, name):
        return super().delete(strip_product_image_prefix(name))

    def open(self, name, mode='rb'):
        return super().open(strip_product_image_prefix(name), mode)

    def size(self, name):
        return super().size(strip_product_image_prefix(name))

    def url(self, name, parameters=None, expire=None, http_method=None):
        key = strip_product_image_prefix(name)
        base_url = getattr(settings, 'PRODUCT_IMAGE_PUBLIC_BASE_URL', '').strip()
        if base_url:
            return f"{base_url.rstrip('/')}/{key}"
        return super().url(key, parameters=parameters, expire=expire, http_method=http_method)


product_image_storage = TigrisProductImageStorage()


class CustomS3Boto3Storage(S3Boto3Storage):
    """
    Custom S3 storage backend that can generate signed URLs for private files
    """
    
    def url(self, name):
        """
        Return a signed URL if files are private, otherwise return public URL
        """
        # If files are public, use the default public URL
        if getattr(settings, 'AWS_DEFAULT_ACL', 'public-read') == 'public-read':
            return super().url(name)
        
        # If files are private, generate signed URL
        # Signed URLs expire after 1 hour by default
        url_expires = getattr(settings, 'AWS_S3_SIGNED_URL_EXPIRES', 3600)
        
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(signature_version='s3v4')
        )
        
        return s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': name
            },
            ExpiresIn=url_expires
        )








