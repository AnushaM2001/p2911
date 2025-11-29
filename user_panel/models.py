from django.db import models
from django.contrib.auth.models import User
from admin_panel.models import Category, Subcategory, Product, Order, OrderItem, Payment,ProductVariant,GiftSet,Flavour,Order

# 🛒 Cart Model
class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_variant=models.ForeignKey(ProductVariant,on_delete=models.CASCADE,null=True,blank=True)
    quantity = models.PositiveIntegerField(default=1)
    gift_wrap = models.BooleanField(default=False)
    gift_set = models.ForeignKey(GiftSet, on_delete=models.CASCADE, null=True, blank=True)
    wishlist = models.BooleanField(default=False)
    razorpay_order_id = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    offer = models.TextField(null=True, blank=True)
    offer_code=models.CharField(max_length=30,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    selected_flavours = models.CharField(max_length=255, null=True, blank=True)


    def total_price(self):
        return self.quantity * self.product.original_price

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class OTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    # def save(self, *args, **kwargs):
    #     if not self.expires_at:
    #         self.expires_at = timezone.now() + timedelta(minutes=2)
    #     super().save(*args, **kwargs)

    
    def __str__(self):
        return f"{self.email} - {self.otp}"
    
class AddressModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    Name=models.CharField(max_length=100)
    MobileNumber=models.CharField(max_length=15)
    Alternate_MobileNumber = models.CharField(max_length=15)
    Pincode=models.CharField(max_length=7)
    City=models.CharField(max_length=50)
    State=models.CharField(max_length=50)
    location=models.CharField(max_length=100,verbose_name='Location/Area/Street/House No')
    # Building=models.CharField(max_length=100,verbose_name='Building Name/Flat No./House No.')
    Landmark=models.CharField(max_length=100,null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return str(self.id)

class SavedCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card_holder = models.CharField(max_length=100)
    card_last4 = models.CharField(max_length=4)
    card_network = models.CharField(max_length=20)  # e.g., Visa, Mastercard
    card_token = models.CharField(max_length=255)  # For future real token
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.card_network} - **** {self.card_last4}"

class GiftSetSelection(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    gift_set = models.ForeignKey(GiftSet, on_delete=models.CASCADE)
    flavours = models.ManyToManyField(Flavour, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.gift_set.set_name} - {self.user or 'Guest'}"


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE,null=True, blank=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey('admin_panel.Product', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')  # Prevents duplicate entries
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'

    def __str__(self):
        return f"{self.user.username}'s Wishlist - {self.product.name}"




class HelpQuery(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Solved', 'Solved'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    admin_reply = models.TextField(blank=True, null=True)  # new field
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.subject} - {self.status}"


class HelpQueryMessage(models.Model):
    query = models.ForeignKey(HelpQuery, related_name="messages", on_delete=models.CASCADE)
    sender = models.CharField(max_length=10, choices=[('User', 'User'), ('Admin', 'Admin')])
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.text[:30]}"
    
    class Meta:
        ordering = ['created_at']



class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.message}"
class InternationalOrder(models.Model):
    Name = models.CharField(max_length=100)
    MobileNumber = models.CharField(max_length=20)
    Alternate_MobileNumber = models.CharField(max_length=20, blank=True, null=True)
    Email = models.EmailField(blank=True, null=True)
    Country = models.CharField(max_length=100)
    Pincode = models.CharField(max_length=10)
    City = models.CharField(max_length=100)
    State = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    Building = models.CharField(max_length=255)
    Landmark = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.Name} - {self.Country}"
