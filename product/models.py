from collections import defaultdict
from decimal import Decimal
import uuid
import os
from django.db import models
from smart_selects.db_fields import ChainedForeignKey
from django.utils.timezone import now
from .storage import product_image_storage, strip_product_image_prefix


PRODUCT_COSTPOOL_DEFAULT_RETAIL_MULTIPLIER = Decimal('0.6')
PRODUCT_COSTPOOL_DEFAULT_BUILDER_MULTIPLIER = Decimal('0.7')
PRODUCT_COSTPOOL_DEFAULT_SURPLUS_MULTIPLIER = Decimal('1')
ADHOC_DEFAULT_RETAIL_MARKUP = Decimal('1.4')


def product_image_upload_to(instance, filename):
    """
    Custom upload_to function for ProductImage.
    Structure: product_images/{uuid-first-2-chars}/{product-uuid}_{suffix}.jpg
    Example: product_images/ab/ab001e02-2954-4ccf-bfcd-265e28764f24_200.jpg
    """
    # Get product UUID
    product_uuid = instance.product.uuid
    
    # Extract file extension
    ext = os.path.splitext(filename)[1]
    
    # Extract suffix from filename (e.g., "12704_200.jpg" -> "200")
    # If filename doesn't have underscore, use the filename without extension
    if '_' in filename:
        suffix = filename.rsplit('_', 1)[1].replace(ext, '')
    else:
        suffix = os.path.splitext(filename)[0]
    
    # Get first 2 characters of UUID for folder grouping
    uuid_prefix = str(product_uuid)[:2]
    
    # Create new filename: {uuid}_{suffix}.{ext}
    new_filename = f"{product_uuid}_{suffix}{ext}"
    
    # Return path: product_images/{uuid-prefix}/{new_filename}
    return os.path.join('product_images', uuid_prefix, new_filename)


class ProductCode(models.Model):
    """Product code categories for categorizing products"""
    code = models.CharField(max_length=10, unique=True, help_text="Product code (e.g., AP, BA, CK)")
    description = models.CharField(max_length=100, help_text="Description of the product code")
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Product Code'
        verbose_name_plural = 'Product Codes'
    
    def __str__(self):
        return f"{self.code} - {self.description}"


class FaucetDrill(models.Model):
    description = models.CharField(max_length=30)
    
    def __str__(self):
        return self.description

class LeadTime(models.Model):
    description = models.CharField(max_length=30)
    status = models.BooleanField(default=True)  
    
    def __str__(self):
        return self.description

class ProductCategory(models.Model):
    product_category = models.CharField(max_length=50)
    status = models.BooleanField(default=True)  
    
    class Meta:
        indexes = [
            models.Index(fields=['status'], name='prod_cat_status_idx'),
            models.Index(fields=['product_category'], name='prod_cat_name_idx'),
            models.Index(fields=['status', 'product_category'], name='prod_cat_status_name_idx'),
        ]
    
    def __str__(self):
        return self.product_category

class ProductSubCategory1(models.Model):
    product_sub_category = models.CharField(max_length=50)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)  
    
    class Meta:
        indexes = [
            models.Index(fields=['category', 'status'], name='sub1_cat_status_idx'),
            models.Index(fields=['product_sub_category'], name='sub1_name_idx'),
            models.Index(fields=['status', 'category'], name='sub1_status_cat_idx'),
            models.Index(fields=['category_id', 'status'], name='sub1_cat_id_status_idx'),
        ]
    
    def __str__(self):
        return self.product_sub_category

class ProductSubCategory2(models.Model):
    product_sub_category2 = models.CharField(max_length=50)
    sub_category1 = models.ForeignKey(ProductSubCategory1, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)  
    
    class Meta:
        indexes = [
            models.Index(fields=['sub_category1', 'status'], name='sub2_sub1_status_idx'),
            models.Index(fields=['product_sub_category2'], name='sub2_name_idx'),
            models.Index(fields=['status', 'sub_category1'], name='sub2_status_sub1_idx'),
            models.Index(fields=['sub_category1_id', 'status'], name='sub2_sub1_id_status_idx'),
        ]
    
    def __str__(self):
        return self.product_sub_category2

class Color(models.Model):
    color_name = models.CharField(max_length=30)
    sub_category2 = models.ForeignKey(ProductSubCategory2, on_delete=models.CASCADE, null=True, blank=True)  # 新增对 ProductSubCategory2 的外键
    status = models.BooleanField(default=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['sub_category2', 'status'], name='color_sub2_status_idx'),
            models.Index(fields=['color_name'], name='color_name_idx'),
            models.Index(fields=['status', 'sub_category2'], name='color_status_sub2_idx'),
            models.Index(fields=['sub_category2_id', 'status'], name='color_sub2_id_status_idx'),
        ]
    
    def __str__(self):
        return self.color_name
    
class Vendor(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    vendor_no = models.CharField(max_length=6, null=True, blank=True)
    vendor_name = models.CharField(max_length=30)
    address1 = models.CharField(max_length=50, null=True, blank=True)
    address2 = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    state = models.CharField(max_length=2, null=True, blank=True)
    zip = models.CharField(max_length=12, null=True, blank=True)
    order_phone = models.CharField(max_length=12, null=True, blank=True)
    contact_name = models.CharField(max_length=50, null=True, blank=True)
    contact_phone = models.CharField(max_length=12, null=True, blank=True)
    contact_email = models.CharField(max_length=50, null=True, blank=True)
    delivery_days = models.IntegerField(null=True)
    delivery_charges = models.DecimalField(max_digits=19, decimal_places=2, null=True)
    warehouse_address = models.CharField(max_length=50, blank=True, null=True)
    warehouse_city = models.CharField(max_length=50, blank=True, null=True)
    warehouse_state = models.CharField(max_length=2, blank=True, null=True)
    warehouse_zip = models.CharField(max_length=12, blank=True, null=True)
    comments = models.CharField(max_length=200, blank=True, null=True)
    status = models.BooleanField(default=True)
    website = models.URLField(max_length=200, null=True, blank=True)  # Optional link
    
    def __str__(self):
        return self.vendor_name

class Manufacturer(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    manufacturer_name = models.CharField(max_length=30)
    address1 = models.CharField(max_length=50, blank=True, null=True)
    address2 = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)
    zip = models.CharField(max_length=12, blank=True, null=True)
    order_phone = models.CharField(max_length=12, blank=True, null=True)
    contact_name = models.CharField(max_length=60, blank=True, null=True)
    contact_phone = models.CharField(max_length=12, blank=True, null=True)
    contact_email = models.CharField(max_length=50, blank=True, null=True)
    comments = models.CharField(max_length=200, blank=True, null=True)
    status = models.BooleanField(default=True)
    preferred_vendor = models.CharField(max_length=50, blank=True, null=True)
    website = models.URLField(max_length=200, null=True, blank=True)  # Optional link
    
    def __str__(self):
        return self.manufacturer_name

class ProductImage(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=product_image_upload_to, storage=product_image_storage)
    is_primary = models.BooleanField(default=False)
    is_spec = models.BooleanField(default=False)

    @property
    def display_url(self):
        """Return the configured product image URL while keeping relative keys in the database."""
        if not self.image:
            return ''

        from django.conf import settings

        base_url = getattr(settings, 'PRODUCT_IMAGE_PUBLIC_BASE_URL', '').strip()
        if base_url:
            key = strip_product_image_prefix(self.image.name)
            return f"{base_url.rstrip('/')}/{key}"

        return self.image.url

    def save(self, *args, **kwargs):
        # Ensure there is only one primary image for each product
        if self.is_primary:
            # Unset any other primary image for this product
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        
        super().save(*args, **kwargs)  
    
    def get_signed_url(self, expires_in=3600):
        """
        Generate a signed URL for the image (temporary, expiring URL)
        This makes the URL more secure as it expires after expires_in seconds (default 1 hour)
        
        Usage in template: {{ image.get_signed_url }}
        """
        from django.conf import settings
        import boto3
        from botocore.client import Config
        
        if not self.image:
            return None
        
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
                'Key': str(self.image)
            },
            ExpiresIn=expires_in
        )

    class Meta:
        indexes = [
            models.Index(fields=['product'], name='prodimg_prod_idx'),
            models.Index(fields=['is_primary'], name='prodimg_primary_idx'),
            models.Index(fields=['product', 'is_primary'], name='prodimg_prod_pri_idx'),
        ]
    
    def __str__(self):
        return f'{self.product.part_no} - {"Primary" if self.is_primary else "Secondary"} Image'
    
class CostPool(models.Model):
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    sub_category1 = ChainedForeignKey(
        ProductSubCategory1,
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE
    )
    sub_category2 = ChainedForeignKey(
        ProductSubCategory2,
        chained_field="sub_category1",
        chained_model_field="sub_category1",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    retail = models.DecimalField(max_digits=5, decimal_places=2, help_text="Retail markup (0.01 to 999.99)")
    builder = models.DecimalField(max_digits=5, decimal_places=2, help_text="Builder markup (0.01 to 999.99)")
    surplus = models.DecimalField(max_digits=5, decimal_places=2, help_text="Surplus markup (0.01 to 999.99)")
    status = models.BooleanField(default=True)
    date_entered = models.DateTimeField(blank=True, null=True)
    date_updated = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['manufacturer'], name='costpool_manufacturer_idx'),
            models.Index(fields=['category'], name='costpool_category_idx'),
            models.Index(fields=['sub_category1'], name='costpool_subcat1_idx'),
            models.Index(fields=['sub_category2'], name='costpool_subcat2_idx'),
            models.Index(fields=['status'], name='costpool_status_idx'),
            models.Index(fields=['manufacturer', 'category'], name='costpool_man_cat_idx'),
            models.Index(fields=['manufacturer', 'category', 'sub_category1'], name='costpool_man_cat_sub1_idx'),
        ]
        verbose_name = "Cost Pool"
        verbose_name_plural = "Cost Pools"
    
    def __str__(self):
        subcat2_str = f" - {self.sub_category2}" if self.sub_category2 else ""
        return f"{self.manufacturer} - {self.category} - {self.sub_category1}{subcat2_str}"
    
    def sync_linked_products(self):
        """
        Sync multipliers to all products linked to this CostPool.
        
        Returns:
            int: Number of products updated
        """
        linked_products = Product.objects.filter(cost_pool=self, status=True)
        updated_count = 0
        
        for product in linked_products:
            if product.sync_multipliers_from_cost_pool():
                product.save()
                updated_count += 1
        
        return updated_count
    
    def get_linked_products_count(self):
        """
        Get count of products linked to this CostPool.
        
        Returns:
            int: Number of linked products
        """
        return Product.objects.filter(cost_pool=self, status=True).count()

    def save(self, *args, **kwargs):
        # Set date_entered on creation and date_updated on every save
        if not self.pk and not self.date_entered:  
            self.date_entered = now()
        # Always update the date_updated field when saving
        self.date_updated = now()
        
        # Check if we should skip auto-sync (for selective updates)
        skip_auto_sync = kwargs.pop('skip_auto_sync', False)
        
        super().save(*args, **kwargs)
        
        # If this is an update and multipliers changed, sync to linked products
        # Only if not explicitly skipping auto-sync
        if self.pk and not skip_auto_sync:  # Only for updates, not creation
            self.sync_linked_products()
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validate that decimal fields are between 0 and 1, but not 0
        if self.retail <= 0 or self.retail > 1:
            raise ValidationError({'retail': 'Retail markup must be greater than 0.00 and not more than 1.00'})
        if self.builder <= 0 or self.builder > 1:
            raise ValidationError({'builder': 'Builder markup must be greater than 0.00 and not more than 1.00'})
        if self.surplus <= 0 or self.surplus > 1:
            raise ValidationError({'surplus': 'Surplus markup must be greater than 0.00 and not more than 1.00'})
    
class Product(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    legacy_product_id = models.IntegerField(null=True, blank=True, db_index=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, null=True, blank=True)
    sub_category1 = ChainedForeignKey(
        ProductSubCategory1,
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    sub_category2 = ChainedForeignKey(
        ProductSubCategory2,
        chained_field="sub_category1",
        chained_model_field="sub_category1",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    color = ChainedForeignKey( 
        Color,
        chained_field="sub_category2",
        chained_model_field="sub_category2",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE, null=True, blank=True)
    cost_pool = models.ForeignKey(
        CostPool, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Linked cost pool for multipliers"
    )
    part_no = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=80)
    pref_vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='pref_vendor')
    alt_vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='alt_vendor')
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    depth = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    drill = models.ForeignKey(FaucetDrill, on_delete=models.SET_NULL, null=True, blank=True)
    min_order = models.IntegerField(null=True, blank=True)
    min_stock = models.IntegerField(null=True, blank=True)
    unit_material_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    unit_lead_time = models.ForeignKey(LeadTime, on_delete=models.SET_NULL, null=True, blank=True, related_name='unit_lead_time')
    unit_labor_minutes = models.IntegerField(null=True, blank=True)
    unit_labor_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    unit_total_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    bulk_material_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    bulk_qty = models.IntegerField(null=True, blank=True)
    bulk_lead_time = models.ForeignKey(LeadTime, on_delete=models.SET_NULL, null=True, blank=True, related_name='bulk_lead_time')
    bulk_labor_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    bulk_total_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    retail_sell = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    builder_sell = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    surplus_sell = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    retail_sell_multiplier = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    builder_sell_multiplier = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    surplus_sell_multiplier = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    upc = models.CharField(max_length=50, blank=True, null=True)
    product_lbl = models.CharField(max_length=50, blank=True, null=True)
    date_entered = models.DateTimeField(blank=True, null=True) 
    date_updated = models.DateTimeField(blank=True, null=True)  
    status = models.BooleanField(default=True)
    component_level = models.IntegerField(choices=[(1, 'Primary'), (2, 'Secondary')], default=1)
    product_type = models.CharField(max_length=20, choices=[
        ('product', 'Product'),
        ('assembly', 'Assembly'), 
        ('component', 'Component')
    ], default='product')
    unit_base_cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    unit_top_install_minutes = models.IntegerField(null=True, blank=True)
    website = models.URLField(max_length=200, null=True, blank=True)  # Optional link
    accessories = models.ManyToManyField('self', through='ProductAccessory', symmetrical=False, related_name='main_products',blank=True)
    components = models.ManyToManyField('self', through='ProductComponent', symmetrical=False,related_name='used_in',blank=True)
    class Meta:
        indexes = [
            models.Index(fields=['status'], name='prod_status_idx'),
            models.Index(fields=['part_no'], name='prod_part_no_idx'),
            models.Index(fields=['category'], name='prod_category_idx'),
            models.Index(fields=['sub_category1'], name='prod_sub1_idx'),
            models.Index(fields=['sub_category2'], name='prod_sub2_idx'),
            models.Index(fields=['manufacturer'], name='prod_manufacturer_idx'),
            models.Index(fields=['status', 'category'], name='prod_status_cat_idx'),
            models.Index(fields=['status', 'manufacturer'], name='prod_status_man_idx'),
        ]
    
    def __str__(self):
        return self.part_no
    
    def find_matching_cost_pool(self):
        """
        Find the best matching CostPool for this product using hierarchical matching.
        
        Priority 1: Exact match (all 4 fields: manufacturer, category, sub_category1, sub_category2)
        Priority 2: Partial match (3 fields: manufacturer, category, sub_category1, costpool.sub_category2 is null)
        
        Returns:
            CostPool instance or None if no match found
        """
        if not all([self.manufacturer, self.category, self.sub_category1]):
            return None
        
        # Priority 1: Try exact match (all 4 fields)
        if self.sub_category2:
            exact_match = CostPool.objects.filter(
                manufacturer=self.manufacturer,
                category=self.category,
                sub_category1=self.sub_category1,
                sub_category2=self.sub_category2,
                status=True
            ).first()
            
            if exact_match:
                return exact_match
        
        # Priority 2: Try partial match (CostPool has null sub_category2)
        partial_match = CostPool.objects.filter(
            manufacturer=self.manufacturer,
            category=self.category,
            sub_category1=self.sub_category1,
            sub_category2__isnull=True,  # CostPool has no sub_category2
            status=True
        ).first()
        
        return partial_match
    
    def sync_multipliers_from_cost_pool(self):
        """
        Sync multipliers from linked CostPool to this Product.
        
        Returns:
            bool: True if multipliers were updated, False if no CostPool linked
        """
        if not self.cost_pool:
            return False
        
        # Update multipliers from CostPool
        self.retail_sell_multiplier = self.cost_pool.retail
        self.builder_sell_multiplier = self.cost_pool.builder
        self.surplus_sell_multiplier = self.cost_pool.surplus
        
        return True
    
    def link_to_matching_cost_pool(self):
        """
        Find and link this product to its matching CostPool.
        
        Returns:
            tuple: (success: bool, cost_pool: CostPool or None, match_type: str)
        """
        cost_pool = self.find_matching_cost_pool()
        
        if cost_pool:
            self.cost_pool = cost_pool
            # Determine match type
            if (self.sub_category2 and 
                cost_pool.sub_category2 and 
                cost_pool.sub_category2 == self.sub_category2):
                match_type = 'exact'
            else:
                match_type = 'partial'
            
            return True, cost_pool, match_type
        else:
            return False, None, 'no_match'

    def apply_cost_pool_multipliers(self):
        """
        Align sell multipliers with CostPool taxonomy (linked pool or matched pool).
        When no CostPool matches, use 0.6 / 0.7 / 1.

        Does not change retail_sell, builder_sell, or surplus_sell — entered prices
        stay as authoritative; the multiplier fields drive the algo when prices are blank
        (see ProductForm.clean).
        """
        if getattr(self, 'cost_pool_id', None):
            self.sync_multipliers_from_cost_pool()
            return

        ok, _, _ = self.link_to_matching_cost_pool()
        if ok:
            self.sync_multipliers_from_cost_pool()
            return

        self.retail_sell_multiplier = PRODUCT_COSTPOOL_DEFAULT_RETAIL_MULTIPLIER
        self.builder_sell_multiplier = PRODUCT_COSTPOOL_DEFAULT_BUILDER_MULTIPLIER
        self.surplus_sell_multiplier = PRODUCT_COSTPOOL_DEFAULT_SURPLUS_MULTIPLIER

    def save(self, *args, **kwargs):
        if not self.pk and not self.date_entered:  
            self.date_entered = now()
        
        self.apply_cost_pool_multipliers()

        # Always update the date_updated field when saving
        self.date_updated = now()
        
        super().save(*args, **kwargs)

class ProductAccessory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_accessories')
    accessory = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='accessory_for')

    class Meta:
        unique_together = ('product', 'accessory')
        
class ProductComponent(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_components')
    component = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='components_for')
    component_qty = models.DecimalField(max_digits=10, decimal_places=4, default=1)

    class Meta:
        unique_together = ('product', 'component')
    
class VendorProductCategory(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    status = models.CharField(max_length=1, blank=True, null=True)

class Finish(models.Model):
    finish_id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=200)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, null=True, blank=True)
    sub_category1 = ChainedForeignKey(
        ProductSubCategory1,
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    sub_category2 = ChainedForeignKey(
        ProductSubCategory2,
        chained_field="sub_category1",
        chained_model_field="sub_category1",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE, null=True, blank=True)
    status = models.BooleanField(default=True)
    comments = models.TextField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status'], name='finish_status_idx'),
            models.Index(fields=['description'], name='finish_description_idx'),
            models.Index(fields=['category'], name='finish_category_idx'),
            models.Index(fields=['sub_category1'], name='finish_sub1_idx'),
            models.Index(fields=['sub_category2'], name='finish_sub2_idx'),
            models.Index(fields=['manufacturer'], name='finish_manufacturer_idx'),
            models.Index(fields=['status', 'category'], name='finish_status_cat_idx'),
        ]
        verbose_name = "Finish"
        verbose_name_plural = "Finishes"
    
    def __str__(self):
        return self.description
    
class ProductQuote(models.Model):
    """Model for the overall product quote."""
    name = models.CharField(max_length=100, blank=True, null=True, help_text="Name for this quote")
    customer = models.ForeignKey(
        'crm.Customer',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product_quotes'
    )
    job = models.ForeignKey(
        'job.Job',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product_quotes',
        verbose_name='Job'
    )
    quoted_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=1,
        choices=[('A', 'Active'), ('I', 'Inactive')],
        default='A'
    )
    subtotal = models.DecimalField(max_digits=19, decimal_places=2, default=0.0)
    comments = models.TextField(blank=True, null=True)
    is_primary = models.BooleanField(default=False, help_text="Primary product quote for this job")

    def calculate_subtotal(self):
        """Recalculate the subtotal based on associated line items and adhoc line items."""
        product_total = sum(line.total_price for line in self.line_items.all())
        adhoc_total = sum(line.total_price for line in self.adhoc_line_items.all())
        self.subtotal = product_total + adhoc_total
        self.save()

    def add_product(self, product, quantity=1, price_type='retail_sell'):
        """
        Add a product to the quote or update its quantity.

        Uses the specified price type for the line item.
        """
        line_item, created = ProductQuoteLine.objects.get_or_create(
            quote=self,
            product=product,
            defaults={
                'quantity': quantity,
                'price_type': price_type,
                'product_description': product.description,
            }
        )
        if not created:
            # If the line item exists, update the quantity
            line_item.quantity += quantity
            line_item.save()

        self.calculate_subtotal()
        return line_item

    def remove_product(self, product):
        """Remove a product from the quote."""
        ProductQuoteLine.objects.filter(quote=self, product=product).delete()
        self.calculate_subtotal()

    def update_quantity(self, product, quantity):
        """Update the quantity of a specific product in the quote."""
        try:
            line_item = ProductQuoteLine.objects.get(quote=self, product=product)
            line_item.quantity = quantity
            line_item.save()
            self.calculate_subtotal()
        except ProductQuoteLine.DoesNotExist:
            raise ValueError(f"Product '{product}' not found in quote.")
        
    def calculate_category_subtotals(self):
        """
        Calculate the subtotal for each main product category in the quote.

        Returns:
            dict: A dictionary with categories as keys and subtotals as values.
        """

        category_subtotals = defaultdict(Decimal)  # Use Decimal for monetary precision

        for line_item in self.line_items.all():
            category = line_item.product.category  
            if category:
                unit_price = Decimal(line_item.unit_price) if line_item.unit_price else Decimal(0)
                quantity = Decimal(line_item.quantity)
                category_subtotals[category.product_category] += unit_price * quantity

        return dict(category_subtotals)
    
    def get_tax_rate(self):
        """Get the tax rate from the associated job's county."""
        if self.job and self.job.county:
            return Decimal(str(self.job.county.taxrate))  # Tax rate is already in decimal form (e.g., 0.055 = 5.5%)
        return Decimal('0')
    
    def calculate_tax(self):
        """Calculate tax amount based on subtotal and county tax rate."""
        tax_rate = self.get_tax_rate()
        return self.subtotal * tax_rate
    
    def get_total_with_tax(self):
        """Calculate total amount including tax."""
        return self.subtotal + self.calculate_tax()

    def __str__(self):
        if self.name:
            return f"{self.name} (Quote #{self.id})"
        return f"Quote #{self.id} - Subtotal: ${self.subtotal:.2f}"


class ProductQuoteLine(models.Model):
    """Model for individual products in a product quote."""
    quote = models.ForeignKey(
        ProductQuote,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='quoted_lines'
    )
    product_description = models.CharField(max_length=80, blank=True, null=True)  # Copied from Product
    unit_price = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)  # Historical price
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=19, decimal_places=2, default=0.0)
    price_type = models.CharField(
        max_length=20,
        choices=[
            ('retail_sell', 'Retail Sell'),
            ('builder_sell', 'Builder Sell'),
            ('surplus_sell', 'Surplus Sell'),
        ],
        default='retail_sell',
        help_text="Price type used for this line item"
    )

    def save(self, *args, **kwargs):
        """
        Calculate the total price. 
        Use the line item's selected price type for pricing.
        """
        # Always recalculate unit_price based on current price_type
        self.unit_price = self.get_price_for_product()

        if not self.product_description:
            self.product_description = self.product.description

        # Calculate the total price
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

        # Update the parent quote's subtotal
        self.quote.calculate_subtotal()

    def get_price_for_product(self):
        """Get the appropriate price for this product based on the line item's price type."""
        if self.price_type == 'retail_sell':
            return self.product.retail_sell or self.product.unit_total_cost or Decimal(0.0)
        elif self.price_type == 'builder_sell':
            return self.product.builder_sell or self.product.unit_total_cost or Decimal(0.0)
        elif self.price_type == 'surplus_sell':
            return self.product.surplus_sell or self.product.unit_total_cost or Decimal(0.0)
        else:
            return self.product.unit_total_cost or Decimal(0.0)

    def get_current_price(self):
        """Return the current product price based on line item's price type."""
        return self.get_price_for_product()

    def get_current_total(self):
        """Calculate the current total based on the current product price."""
        return self.get_current_price() * self.quantity

    def __str__(self):
        return f"{self.product.part_no} - Qty: {self.quantity} - Total: ${self.total_price:.2f}"

class AdHoc(models.Model):
    """
    One-time product snapshot for a quote line.
    Created only from Search and Add Products on a quote — not a reusable catalog item.
    """
    part_no = models.CharField(max_length=20, help_text="Part number for this one-time quote item")
    description = models.CharField(max_length=80, help_text="Description of the Ad-Hoc item")
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, null=True, blank=True, help_text="Category for the Ad-Hoc item")
    retail_price = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True, help_text="Retail price of the Ad-Hoc item")
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE, null=True, blank=True, help_text="Manufacturer of the Ad-Hoc item")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True, blank=True, help_text="Vendor for the Ad-Hoc item")
    cost = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True, help_text="Cost of the Ad-Hoc item")
    date_entered = models.DateField(blank=True, null=True, auto_now_add=True)
    date_updated = models.DateField(blank=True, null=True, auto_now=True)
    status = models.BooleanField(default=True, help_text="Active status of the Ad-Hoc item")
    
    class Meta:
        verbose_name = "Ad-Hoc Item"
        verbose_name_plural = "Ad-Hoc Items"
        indexes = [
            models.Index(fields=['status'], name='adhoc_status_idx'),
            models.Index(fields=['part_no'], name='adhoc_part_no_idx'),
            models.Index(fields=['category'], name='adhoc_category_idx'),
            models.Index(fields=['manufacturer'], name='adhoc_manufacturer_idx'),
            models.Index(fields=['vendor'], name='adhoc_vendor_idx'),
            models.Index(fields=['status', 'category'], name='adhoc_status_cat_idx'),
        ]
    
    def __str__(self):
        return f"{self.part_no} - {self.description}"

    @classmethod
    def compute_retail_price(cls, cost, retail_price=None):
        """Return retail_price if set, otherwise cost × 40% markup."""
        if retail_price is not None:
            return retail_price
        if cost is not None:
            return (Decimal(cost) * ADHOC_DEFAULT_RETAIL_MARKUP).quantize(Decimal('0.01'))
        return None

    def get_quote_unit_price(self):
        """Unit price for quote lines: retail, defaulting to 1.4 × cost."""
        return self.compute_retail_price(self.cost, self.retail_price) or Decimal('0.00')
    
    def save(self, *args, **kwargs):
        if self.retail_price is None and self.cost is not None:
            self.retail_price = self.compute_retail_price(self.cost)
        super().save(*args, **kwargs)


class AdHocQuoteLine(models.Model):
    """Model for Ad-Hoc items in a product quote."""
    quote = models.ForeignKey(
        ProductQuote,
        on_delete=models.CASCADE,
        related_name='adhoc_line_items'
    )
    adhoc = models.ForeignKey(
        AdHoc,
        on_delete=models.CASCADE,
        related_name='quoted_lines'
    )
    adhoc_description = models.CharField(max_length=80, blank=True, null=True)  # Copied from AdHoc
    unit_price = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)  # Historical price
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=19, decimal_places=2, default=0.0)

    def save(self, *args, **kwargs):
        """
        Calculate the total price. 
        Ensure the copied price (unit_price) remains unchanged for existing lines.
        """
        if self.unit_price is None:
            self.unit_price = self.adhoc.get_quote_unit_price()

        if not self.adhoc_description:
            self.adhoc_description = self.adhoc.description

        # Calculate the total price
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

        # Update the parent quote's subtotal
        self.quote.calculate_subtotal()

    def get_current_price(self):
        """Return the current adhoc retail price."""
        return self.adhoc.get_quote_unit_price()

    def get_current_total(self):
        """Calculate the current total based on the current adhoc retail price."""
        return self.get_current_price() * self.quantity

    def __str__(self):
        return f"{self.adhoc.part_no} - Qty: {self.quantity} - Total: ${self.total_price:.2f}"