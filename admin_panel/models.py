from django.db import models
from django.contrib.auth.models import User
import requests
import random
import string
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.hashers import make_password, check_password
from django.db.models.fields.files import ImageFieldFile
# from admin_panel.utils import compress_image

class AutoCompressImagesMixin(models.Model):
    """
    Mixin to automatically compress all ImageFields in a model on save.
    """
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from admin_panel.utils import compress_image
        # Loop through all fields
        for field in self._meta.get_fields():
            if field.get_internal_type() == 'ImageField':
                image = getattr(self, field.name)
                if image and isinstance(image, ImageFieldFile):
                    compressed_image = compress_image(image)
                    setattr(self, field.name, compressed_image)
        super().save(*args, **kwargs)

# models.py

class AdminUser(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    password = models.CharField(max_length=100)
    profile_pic = models.ImageField(upload_to='admin_profile/', blank=True, null=True)

    def __str__(self):
        return self.name



# Category Model
class Category(AutoCompressImagesMixin,models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Category Name")
    created_at = models.DateTimeField(auto_now_add=True)
    banner = models.ImageField(upload_to='category_banners/', blank=True, null=True)
    gif_file = models.FileField(upload_to='gifs/', blank=True, null=True,)
    class Meta:
        ordering = ['-created_at']  # Order categories by name


    def __str__(self):
        return self.name

class Subcategory(AutoCompressImagesMixin,models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=255, unique=True, verbose_name="Subcategory Name")
    created_at = models.DateTimeField(auto_now_add=True)
    sub_image = models.ImageField(upload_to='subcategory_images/', null=True, blank=True)
    banner = models.ImageField(upload_to='subcategory_banners/', blank=True, null=True)

    class Meta:
        ordering = ['-created_at'] 


    def __str__(self):
        return self.name
# Example (models.py)
class Banner(AutoCompressImagesMixin,models.Model):
    SECTION_CHOICES = [
        ('new-arrival', 'New Arrival'),
        ('trending', 'Trending'),
        ('best-seller', 'Best Seller'),
        ('shopbyocassions', 'Shop By Occasions'),

    ]
    title = models.CharField(max_length=100,default='')
    banner_image = models.ImageField(upload_to='banners/',null=True, blank=True)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, unique=True,null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at'] 

    def __str__(self):
        return self.title


# Product Model
class Product(AutoCompressImagesMixin,models.Model):
    sku=models.CharField(max_length=10,unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, verbose_name="Product Name")
    description = models.TextField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    # selling_price = models.DecimalField(max_digits=10, decimal_places=2)
     
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,related_name='products')
    subcategory = models.ForeignKey(Subcategory, on_delete=models.SET_NULL, null=True, blank=True)
    image1 = models.ImageField(upload_to='product_images/', null=True, blank=True)
    image2 = models.ImageField(upload_to='product_images/', null=True, blank=True)
    image3 = models.ImageField(upload_to='product_images/', null=True, blank=True)
    image4 = models.ImageField(upload_to='product_images/', null=True, blank=True)
    glass_image = models.ImageField(upload_to='glass_images/', null=True, blank=True)
    plastic_image = models.ImageField(upload_to='plastic_images/', null=True, blank=True)
    is_trending = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)  # Best Seller Field
    is_shop_by_occassion = models.BooleanField(default=False)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivery_charges=models.PositiveIntegerField(default=0)
    platform_fee=models.PositiveIntegerField(default=0)
    scroll_bar=models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    stock_status=models.CharField(max_length=20, choices=[('In Stock', 'In Stock'), ('Out of Stock', 'Out of Stock'),('Low Stock','Low Stock')], default='In Stock')
    banner = models.ForeignKey(Banner, related_name="banners", on_delete=models.SET_NULL, null=True, blank=True)
    class Meta:
        ordering = ['-created_at'] 

    def __str__(self):
        return self.name

class ProductVideo(models.Model):
        video = models.FileField(upload_to='product_videos/')
        title = models.CharField(max_length=255, verbose_name="Video Title")
        # description = models.TextField(blank=True, null=True)
        related_products = models.ManyToManyField(Product, related_name="videos")
        created_at = models.DateTimeField(auto_now_add=True)
        class Meta:
           ordering = ['-created_at'] 

        def __str__(self):
            return f"{self.title} - {', '.join([product.name for product in self.related_products.all()])}"   

class ProductVariant(models.Model):
    BOTTLE_CHOICES = [
        ('Plastic_Bottle', 'Plastic Bottle'),
        ('Glass_Bottle', 'Glass Bottle'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    bottle_type = models.CharField(max_length=100, choices=BOTTLE_CHOICES,null=True, blank=True)
    size = models.CharField(max_length=20,null=True,blank=True)  # in ml
    price = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    stock = models.PositiveIntegerField(default=0,null=True, blank=True)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offer_code=models.CharField(max_length=20,null=True,blank=True)
    offer_start_time=models.DateTimeField(null=True,blank=True)
    offer_end_time=models.DateTimeField(null=True,blank=True)
    original_price = models.CharField(max_length=100,null=True,blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.bottle_type} - {self.size}"

    def save(self, *args, **kwargs):
      if self.bottle_type == 'Glass_Bottle':
        # Only adjust price if same size Plastic exists
        try:
            plastic_variant = ProductVariant.objects.get(
                product=self.product,
                bottle_type='Plastic_Bottle',
                size=self.size
            )
            if not self.price:  # Only set if price not already set manually
                self.price = plastic_variant.price + 100
        except ProductVariant.DoesNotExist:
            # No matching Plastic found – leave price as is (allow manual price)
            pass
      super().save(*args, **kwargs)

class Flavour(AutoCompressImagesMixin,models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='flavours/')
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['-created_at']
    def __str__(self):
        return self.name

class GiftSet(models.Model):
    set_name = models.CharField(max_length=50)
    price=models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gift_sets',)
    flavours = models.ManyToManyField(Flavour, related_name='gift')
    stock = models.PositiveIntegerField(default=0,null=True, blank=True)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offer_code=models.CharField(max_length=20,null=True,blank=True)
    offer_start_time=models.DateTimeField(null=True,blank=True)
    offer_end_time=models.DateTimeField(null=True,blank=True)
    original_price = models.CharField(max_length=100,null=True,blank=True)
    
    def __str__(self):
        try:
           flavour_names = ", ".join([flavour.name for flavour in self.flavours.all()])
        except:
           flavour_names = "No Flavours"
        return f"{self.set_name} - {flavour_names}"



# Order Model
class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
        ('order_created', 'Order Created'),
        ('awb_assigned', 'AWB Assigned'),
        ('pickup_generated', 'Pickup Generated'),
        ('manifest_ready', 'Manifest Ready'),
        ('label_ready', 'Label Ready'),
        ('invoice_ready', 'Invoice Ready'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.ForeignKey('user_panel.AddressModel', on_delete=models.SET_NULL, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    shiprocket_order_id = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_shipment_id = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_tracking_info = models.JSONField(null=True, blank=True)  # To store tracking history
    shiprocket_awb_code = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_courier_name = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_courier_id=models.CharField(max_length=100, blank=True, null=True)  # 👈 NEW
    label_url = models.URLField(blank=True, null=True)
    invoice_url = models.URLField(blank=True, null=True)
    manifest_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    shiprocket_tracking_status = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_estimated_delivery = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_tracking_events = models.JSONField(null=True, blank=True)
    shiprocket_tracking_status_updated_at = models.DateTimeField(blank=True, null=True)  # 👈 NEW
    invoice_sent = models.BooleanField(default=False)  # To track if invoice email sent


    def __str__(self):
        return f"Order {self.id} - {self.user.username}"

# Order Items Model (to store products in an order)
class OrderItem(models.Model):
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    gift_wrap = models.BooleanField(default=False)
    gift_set = models.ForeignKey(GiftSet, on_delete=models.SET_NULL, null=True, blank=True)
    selected_flavours = models.CharField(max_length=255, null=True, blank=True)  # New field
    offer_code = models.CharField(max_length=30, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    


    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


# Shipping Model
class Shipping(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    tracking_number = models.CharField(max_length=255, blank=True, null=True)
    carrier = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50, 
        choices=[('Processing', 'Processing'), ('Shipped', 'Shipped'), ('Delivered', 'Delivered')],
        default='Processing'
    )
    estimated_delivery = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Shipping for Order {self.order.id}"

# Payment Model (Razorpay Integrated)
class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    payment_method = models.CharField(
        max_length=50, 
        choices=[('Credit Card', 'Credit Card'), ('PayPal', 'PayPal'), ('Razorpay', 'Razorpay'), ('COD', 'Cash On Delivery')]
    )
    status = models.CharField(
        max_length=50, 
        choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Failed', 'Failed')]
    )
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    price=models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)

    def __str__(self):
        return f"Payment for Order {self.order.id}"

# Review Model
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE,related_name='reviews',null=True, blank=True)
    review_text = models.TextField()
    rating = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.username}"

# Coupon Model
class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True,null=True,blank=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2,null=True,blank=True)  # percentage or fixed
    required_amount = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)  # eligibility threshold
    created_at = models.DateTimeField(auto_now_add=True,null=True,blank=True)

    is_active = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_coupon_code()
        super().save(*args, **kwargs)

    def generate_coupon_code(self):
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def __str__(self):
        return self.code

class CouponUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'coupon') 

    def __str__(self):
        return f"{self.user.email} - {self.coupon.code}"
    



class PremiumFestiveOffer(models.Model):
    premium_festival = models.CharField(
        max_length=20, 
        choices=[('Welcome','Welcome'),('Premium', 'Premium'), ('Festival', 'Festival')]
    )
    offer_name = models.CharField(max_length=50, blank=True, null=True)
    category = models.ManyToManyField(Category, blank=True)
    subcategory = models.ManyToManyField(Subcategory, blank=True)
    size = models.CharField(max_length=10, blank=True, null=True)  # "All" means all sizes
    code = models.CharField(max_length=20, null=True, blank=True)
    percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True, 
        help_text="Enter discount percentage (0-100%)"
    )
    start_date = models.DateTimeField(null=True,blank=True)
    end_date = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def apply_offer(self, item):
        """
        Apply discount offer to either a ProductVariant or a GiftSet.
        """
        now = timezone.now()
        if self.premium_festival != "Welcome" or self.premium_festival != "Premium":
            if self.start_date is None or self.end_date is None:
                # print("Offer has missing start_date or end_date.")
                return None
            if not self.is_active or not (self.start_date <= now <= self.end_date):
                # print("Offer inactive or expired.")
                return None
        else:
            if not self.is_active:
                # print("Offer inactive.")
                return None
        

        if isinstance(item, ProductVariant):
            result=self._apply_to_variant(item)
            if result is None:
                pass
                # print(f"No match for variant: {item}, Offer: {self.offer_name}")
            return result

        if isinstance(item, GiftSet):
            result = self._apply_to_giftset(item)
            if result is None:
                pass
                # print(f"No match for giftset: {item}, Offer: {self.offer_name}")
            return result

        return None

    def _apply_to_variant(self, variant):
        product = variant.product

        category_match = self.category.exists() and product.category in self.category.all()
        subcategory_match = self.subcategory.exists() and product.subcategory in self.subcategory.all()
        has_category_filter = self.category.exists()
        has_subcategory_filter = self.subcategory.exists()
        has_size_filter = bool(self.size)

        # Determine size match
        size_match = False
        if self.size and self.size.lower() == "all":
            size_match = True
        elif self.size:
            size_match = str(variant.size).lower() == str(self.size).lower()
        # print("=== DEBUG APPLY OFFER ===")
        # print(f"Offer: {self.offer_name}")
        # print(f"Category match: {category_match}")
        # print(f"Subcategory match: {subcategory_match}")
        # print(f"Has category filter: {has_category_filter}")
        # print(f"Has subcategory filter: {has_subcategory_filter}")
        # print(f"Size: {self.size}")
        # print(f"Variant size: {variant.size}")
        # print(f"Size match: {size_match}")
        # print(f"Offer active: {self.is_active}")
        # print(f"Offer dates: {self.start_date} - {self.end_date}")
        # print("=========================")

        if (
            (category_match and size_match) or
            (subcategory_match and size_match) or
            (self.size and self.size.lower() == "all" and (category_match or subcategory_match)) or
            (not has_category_filter and not has_subcategory_filter and size_match)
        ):
            if self.percentage and variant.price:
                discount = (self.percentage / Decimal(100)) * variant.price
                return round(variant.price - discount, 2)

        return None

    def _apply_to_giftset(self, giftset):
        product = giftset.product

        category_match = self.category.exists() and product.category in self.category.all()
        subcategory_match = self.subcategory.exists() and product.subcategory and product.subcategory in self.subcategory.all()
        has_category_filter = self.category.exists()
        has_subcategory_filter = self.subcategory.exists()

        if (
            category_match or
            subcategory_match or
            (not has_category_filter and not has_subcategory_filter)
        ):
            if self.percentage and giftset.price:
                discount = (self.percentage / Decimal(100)) * giftset.price
                return round(giftset.price - discount, 2)

        return None
    

    def get_status(self):
        """
        Returns 'Active', 'Scheduled', or 'Expired' status.
        """
        now = timezone.now()

        if self.premium_festival == "Welcome" or self.premium_festival == "Premium":
            return "Active"

        if self.start_date and self.end_date:
            if self.start_date > now:
                return "Scheduled"
            elif self.end_date < now:
                return "Expired"
            else:
                return "Active"
        return "Unknown"

    

    
    def __str__(self):
        if self.percentage:
            return f"{self.offer_name}-{self.percentage}% off on {self.size} from {self.start_date} to {self.end_date}"

       
        else:
            return "No Discount"
        


class PremiumOfferUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    offer_code = models.CharField(max_length=50)
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Offer {self.offer_code} used by {self.user.email}"



# Notification Model

# shipping 
from datetime import timedelta


class ShiprocketToken(models.Model):
    token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        # Token is valid for ~240 hours according to Shiprocket
        return self.created_at >= timezone.now() - timedelta(hours=240)

    def __str__(self):
        return f"Token at {self.created_at}"

class PushSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    endpoint = models.TextField()
    keys = models.JSONField()

    def __str__(self):
        return f"{self.user.email}'s Subscription"
    


class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('orders', 'Orders'),
        ('stocks', 'Stocks'),
        ('queries', 'Queries'),
    ]
    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES,null=True,blank=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-timestamp']  # Newest first

    def __str__(self):
        return f"{self.user} - {self.category} - {self.message[:30]}"
class Location_Store(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    map_link = models.URLField(blank=True)  # Google Maps link

    def __str__(self):
        return self.name


class Client_review(models.Model):
    client_name=models.CharField(max_length=100)
    review=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.client_name}-{self.review}"
    
class Subscription(models.Model):
    name=models.CharField(max_length=100, blank=True, null=True)
    phone_number=models.CharField(max_length=15, blank=True, null=True)
    email=models.EmailField(unique=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.email