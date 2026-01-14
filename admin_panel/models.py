from django.db import models
import requests
import random
import string
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.hashers import make_password, check_password
from django.db.models.fields.files import ImageFieldFile
# from admin_panel.utils import compress_image
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings

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



from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django.conf import settings

class Category(AutoCompressImagesMixin, models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Category Name")
    created_at = models.DateTimeField(auto_now_add=True)
    banner = models.ImageField(upload_to='category_banners/', blank=True, null=True)
    gif_file = models.FileField(upload_to='gifs/', blank=True, null=True)

    slug = models.SlugField(null=True, blank=True)  # 🔥 FIXED
    seo_title = models.CharField(max_length=255, blank=True, null=True)
    seo_description = models.TextField(blank=True, null=True)
    h_tag = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            'category_products',
            kwargs={
                'category_slug': f"{self.slug}-{settings.SEO_SUFFIX}"
            }
        )

    def __str__(self):
        return self.name

class Subcategory(AutoCompressImagesMixin, models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories"
    )
    name = models.CharField(max_length=255, unique=True, verbose_name="Subcategory Name")
    created_at = models.DateTimeField(auto_now_add=True)

    sub_image = models.ImageField(upload_to='subcategory_images/', blank=True, null=True)
    banner = models.ImageField(upload_to='subcategory_banners/', blank=True, null=True)

    slug = models.SlugField(null=True,blank=True)  # 🔥 FIXED
    seo_title = models.CharField(max_length=255, blank=True, null=True)
    seo_description = models.TextField(blank=True, null=True)
    h_tag = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            # ✅ FIXED MODEL HERE
            while Subcategory.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            'subcategory_products',
            kwargs={
                'category_slug': self.category.slug,
                'subcategory_slug': f"{self.slug}-{settings.SEO_SUFFIX}",
            }
        )

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
            # No matching Plastic found  leave price as is (allow manual price)
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

    guest_id = models.CharField(max_length=64, db_index=True,)
    address = models.ForeignKey('user_panel.AddressModel', on_delete=models.SET_NULL, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    shiprocket_order_id = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_shipment_id = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_tracking_info = models.JSONField(null=True, blank=True)  # To store tracking history
    shiprocket_awb_code = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_courier_name = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_courier_id=models.CharField(max_length=100, blank=True, null=True)  #  NEW
    label_url = models.URLField(blank=True, null=True)
    invoice_url = models.URLField(blank=True, null=True)
    manifest_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    shiprocket_tracking_status = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_estimated_delivery = models.CharField(max_length=100, blank=True, null=True)
    shiprocket_tracking_events = models.JSONField(null=True, blank=True)
    shiprocket_tracking_status_updated_at = models.DateTimeField(blank=True, null=True)  #  NEW
    invoice_sent = models.BooleanField(default=False)  # To track if invoice email sent
    invoice_number = models.CharField(max_length=50, blank=True, null=True)
    invoice_date = models.DateField(auto_now_add=True, null=True)
    shiprocket_issue_flag = models.BooleanField(default=False)
    shiprocket_issue_reason = models.CharField(max_length=50, blank=True, null=True)
    shiprocket_pickup_generated = models.BooleanField(default=False)


    


    def __str__(self):
        return f"Order {self.id} - {self.guest_id}"

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
    guest_id = models.CharField(max_length=64, db_index=True,null=True,blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE,related_name='reviews',null=True, blank=True)
    review_text = models.TextField()
    rating = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.guest_id}"

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
    guest_id = models.CharField(max_length=64)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('guest_id', 'coupon') 

    def __str__(self):
        return f"{self.guest_id} - {self.coupon.code}"
    



class PremiumFestiveOffer(models.Model):
  premium_festival = models.CharField(max_length=20,choices=[('Welcome','Welcome'),('Premium', 'Premium'), ('Festival', 'Festival')])
  offer_name = models.CharField(max_length=50, blank=True, null=True)
  category = models.ManyToManyField(Category, blank=True)
  subcategory = models.ManyToManyField(Subcategory, blank=True)
  size = models.CharField(max_length=10, blank=True, null=True)
  code = models.CharField(max_length=20, null=True, blank=True)
  percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
  start_date = models.DateTimeField(null=True, blank=True)
  end_date = models.DateTimeField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  is_active = models.BooleanField(default=True)

  # -------------------------------
  # CACHED M2M LISTS (SUPER FAST)
  # -------------------------------
  @property
  def cached_categories(self):
    if not hasattr(self, "_cached_categories"):
      self._cached_categories = list(self.category.all())
    return self._cached_categories

  @property
  def cached_subcategories(self):
    if not hasattr(self, "_cached_subcategories"):
      self._cached_subcategories = list(self.subcategory.all())
    return self._cached_subcategories

  # -------------------------------
  # OFFER STATUS + DATE VALIDATION
  # -------------------------------
  def offer_active_now(self):
    

    # Welcome & Premium  always active
    if self.premium_festival != "Festival":
      return False
    
    if not self.is_active:
      return False

    # Festival  requires dates
    if not self.start_date or not self.end_date:
      return False

    now = timezone.now()
    return self.start_date <= now <= self.end_date

  # -------------------------------
  # APPLY OFFER ENTRY POINT
  # -------------------------------
  def apply_offer(self, item):
    if not self.offer_active_now():
      return None

    if isinstance(item, ProductVariant):
      return self._apply_to_variant(item)

    if isinstance(item, GiftSet):
      return self._apply_to_giftset(item)

    return None

  # -------------------------------
  # APPLY TO PRODUCT VARIANT
  # -------------------------------
  def _apply_to_variant(self, variant):
    product = variant.product

    cat_list = self.cached_categories
    subcat_list = self.cached_subcategories

    # Matches
    category_match = product.category in cat_list
    subcategory_match = product.subcategory in subcat_list

    has_cat_filter = len(cat_list) > 0
    has_subcat_filter = len(subcat_list) > 0

    # -------- SIZE MATCH --------
    if self.size:
      if self.size.lower() == "all":
        size_match = True
      else:
        size_match = str(variant.size).lower() == str(self.size).lower()
    else:
      size_match = True # No size filter = match all sizes

    if not size_match:
      return None

    # -------- CATEGORY/SUBCATEGORY MATCHING LOGIC ----------
    if (
      (has_cat_filter and category_match) or
      (has_subcat_filter and subcategory_match) or
      (not has_cat_filter and not has_subcat_filter) # global offer
    ):
      if self.percentage and variant.price:
        discount = (self.percentage / Decimal(100)) * variant.price
        return round(variant.price - discount, 2)

    return None

  # -------------------------------
  # APPLY TO GIFTSET
  # -------------------------------
  def _apply_to_giftset(self, giftset):
    product = giftset.product

    cat_list = self.cached_categories
    subcat_list = self.cached_subcategories

    category_match = product.category in cat_list
    subcategory_match = product.subcategory in subcat_list

    has_cat_filter = len(cat_list) > 0
    has_subcat_filter = len(subcat_list) > 0

    if (
      category_match or
      subcategory_match or
      (not has_cat_filter and not has_subcat_filter)
    ):
      if self.percentage and giftset.price:
        discount = (self.percentage / Decimal(100)) * giftset.price
        return round(giftset.price - discount, 2)

    return None

  # -------------------------------
  # HUMAN-READABLE STATUS
  # -------------------------------
  def get_status(self):
    if self.premium_festival in ["Welcome", "Premium"]:
      return "Active"

    now = timezone.now()

    if not self.start_date or not self.end_date:
      return "Unknown"

    if self.start_date > now:
      return "Scheduled"
    if self.end_date < now:
      return "Expired"

    return "Active"

  def __str__(self):
    if self.percentage:
      return f"{self.offer_name} - {self.percentage}% off ({self.size})"
    return "No Discount"

        


class PremiumOfferUsage(models.Model):
    guest_id = models.CharField(max_length=64, db_index=True,null=True,blank=True)
    offer_code = models.CharField(max_length=50)
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Offer {self.offer_code} used by {self.guest_id}"



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
    guest_id = models.CharField(max_length=64, db_index=True,null=True,blank=True)
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
