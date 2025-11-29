from django.contrib import admin
from .models import (
    Category, Subcategory, Product, Order, OrderItem, Notification,Location_Store,
    Shipping, Payment, Review, Coupon, Notification,Banner,ProductVariant,CouponUsage,PremiumFestiveOffer,PremiumOfferUsage,GiftSet,Flavour,ProductVideo,ShiprocketToken,Client_review,Subscription
)
admin.site.register(Location_Store)
admin.site.register(ShiprocketToken)
admin.site.register(Flavour)
admin.site.register(Notification)
admin.site.register(PremiumOfferUsage)
admin.site.register(CouponUsage)
admin.site.register(PremiumFestiveOffer)
admin.site.register(ProductVideo)
admin.site.register(GiftSet)
admin.site.register(Subscription)
admin.site.register(Client_review)

# Banner
from django.contrib import admin
from .models import AdminUser

admin.site.register(AdminUser)

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display=('title',)
    
# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

# Subcategory Admin
@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_at')
    list_filter = ('category',)
    search_fields = ('name',)

# Product Admin
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

class GiftSetInline(admin.TabularInline):
    model = GiftSet
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id','name','category','subcategory', 'is_best_seller', 'is_trending', 'is_new_arrival','is_active', 'original_price', 'delivery_charges', 'platform_fee', 'created_at')
    list_filter = ('category', 'is_best_seller', 'is_trending', 'is_new_arrival','is_active')
    search_fields = ('name', 'description')
    list_editable = ('is_best_seller', 'is_trending', 'is_new_arrival')
    inlines = [ProductVariantInline,GiftSetInline]


# Discount Admin
# @admin.register(Offer)
# class OfferAdmin(admin.ModelAdmin):
#     list_display = ('size', 'discount_percent', 'start_time', 'end_time', 'active')
#     search_fields = ('size',)
#     list_editable = ('discount_percent','active')
#     list_filter = ('start_time', 'end_time','active')

# Order Admin
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_price', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'id')

# Order Items Admin
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')
    search_fields = ('order__id', 'product__name')

# Shipping Admin
@admin.register(Shipping)
class ShippingAdmin(admin.ModelAdmin):
    list_display = ('order', 'tracking_number', 'carrier', 'status', 'estimated_delivery')
    list_filter = ('status',)
    search_fields = ('tracking_number', 'order__id')

# Payment Admin
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_method', 'status', 'transaction_id', 'created_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('order__id', 'transaction_id')

# Review Admin
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('user__username', 'product__name')

# Coupon Admin
@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount', 'required_amount', 'is_active')
    list_filter = ('required_amount',)
    search_fields = ('code',)

# Notification Admin




