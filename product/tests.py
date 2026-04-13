from django.test import TestCase
from decimal import Decimal
from .models import Product, ProductQuote, ProductQuoteLine, ProductCategory, Manufacturer, Vendor

# Create your tests here.

class ProductQuoteLinePriceTypeTest(TestCase):
    """Test the individual price type selection functionality for product quote line items."""
    
    def setUp(self):
        """Set up test data."""
        # Create test category
        self.category = ProductCategory.objects.create(product_category="Test Category")
        
        # Create test manufacturer
        self.manufacturer = Manufacturer.objects.create(
            manufacturer_name="Test Manufacturer",
            address1="123 Test St",
            city="Test City",
            state="TX",
            zip="12345",
            order_phone="123-456-7890",
            contact_name="Test Contact",
            contact_phone="123-456-7890",
            contact_email="test@example.com"
        )
        
        # Create test vendor
        self.vendor = Vendor.objects.create(
            vendor_no="V001",
            vendor_name="Test Vendor",
            address1="456 Vendor St",
            city="Vendor City",
            state="TX",
            zip="54321",
            order_phone="987-654-3210",
            contact_name="Vendor Contact",
            contact_phone="987-654-3210",
            contact_email="vendor@example.com"
        )
        
        # Create test product with different price types
        self.product = Product.objects.create(
            part_no="TEST001",
            description="Test Product",
            category=self.category,
            manufacturer=self.manufacturer,
            unit_total_cost=Decimal("100.00"),
            retail_sell=Decimal("150.00"),
            builder_sell=Decimal("120.00"),
            surplus_sell=Decimal("80.00")
        )
        
        # Create test quote
        self.quote = ProductQuote.objects.create(
            name="Test Quote"
        )
    
    def test_line_item_get_price_for_product_retail(self):
        """Test that retail_sell price is returned when line item price_type is retail_sell."""
        line_item = ProductQuoteLine.objects.create(
            quote=self.quote,
            product=self.product,
            price_type="retail_sell",
            quantity=1
        )
        price = line_item.get_price_for_product()
        self.assertEqual(price, Decimal("150.00"))
    
    def test_line_item_get_price_for_product_builder(self):
        """Test that builder_sell price is returned when line item price_type is builder_sell."""
        line_item = ProductQuoteLine.objects.create(
            quote=self.quote,
            product=self.product,
            price_type="builder_sell",
            quantity=1
        )
        price = line_item.get_price_for_product()
        self.assertEqual(price, Decimal("120.00"))
    
    def test_line_item_get_price_for_product_surplus(self):
        """Test that surplus_sell price is returned when line item price_type is surplus_sell."""
        line_item = ProductQuoteLine.objects.create(
            quote=self.quote,
            product=self.product,
            price_type="surplus_sell",
            quantity=1
        )
        price = line_item.get_price_for_product()
        self.assertEqual(price, Decimal("80.00"))
    
    def test_line_item_get_price_for_product_fallback(self):
        """Test that unit_total_cost is used as fallback when selected price type is None."""
        # Create product without retail_sell price
        product_no_retail = Product.objects.create(
            part_no="TEST002",
            description="Test Product No Retail",
            category=self.category,
            manufacturer=self.manufacturer,
            unit_total_cost=Decimal("100.00"),
            builder_sell=Decimal("120.00"),
            surplus_sell=Decimal("80.00")
            # retail_sell is None
        )
        
        line_item = ProductQuoteLine.objects.create(
            quote=self.quote,
            product=product_no_retail,
            price_type="retail_sell",
            quantity=1
        )
        price = line_item.get_price_for_product()
        self.assertEqual(price, Decimal("100.00"))  # Should fall back to unit_total_cost
    
    def test_add_product_with_price_type(self):
        """Test that adding a product to quote uses the specified price type."""
        line_item = self.quote.add_product(self.product, quantity=2, price_type="builder_sell")
        
        # Check that the line item uses the builder_sell price
        self.assertEqual(line_item.price_type, "builder_sell")
        self.assertEqual(line_item.unit_price, Decimal("120.00"))
        self.assertEqual(line_item.total_price, Decimal("240.00"))  # 120 * 2
    
    def test_line_item_price_recalculation(self):
        """Test that changing price type recalculates the line item price."""
        line_item = ProductQuoteLine.objects.create(
            quote=self.quote,
            product=self.product,
            price_type="retail_sell",
            quantity=2
        )
        
        # Change price type and save
        line_item.price_type = "surplus_sell"
        line_item.save()
        
        # Check that the price was recalculated
        self.assertEqual(line_item.unit_price, Decimal("80.00"))
        self.assertEqual(line_item.total_price, Decimal("160.00"))  # 80 * 2
