from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Cart)
admin.site.register(AddressModel)

admin.site.register(UserProfile)

admin.site.register(HelpQuery)
admin.site.register(ContactMessage)
@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'product__name')
@admin.register(InternationalOrder)
class InternationalOrderAdmin(admin.ModelAdmin):
    list_display = ('Name', 'Country', 'City', 'MobileNumber', 'Email', 'created_at')
    fieldsets = (
        ('Customer Info', {'fields': ('Name', 'Email', 'MobileNumber', 'Alternate_MobileNumber')}),
        ('Address Details', {'fields': ('Country', 'Pincode', 'City', 'State', 'location', 'Building', 'Landmark')}),
    )