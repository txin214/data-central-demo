"""Custom storage backend with signed URL support"""
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import boto3
from botocore.client import Config
from datetime import timedelta

class CustomS3Boto3Storage(S3Boto3Storage):
    """
    Custom S3 storage backend that can generate signed URLs for private files
    """
    
    def url(self, name):
        """
        Return a signed URL if files are private, otherwise return public URL
        """
        print(f"Generating super URL for {name}")
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
        print(f"Generating signed URL for {name}")
        return s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': name
            },
            ExpiresIn=url_expires
        )








