# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from admin_panel.models import *
@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductVariant)
@receiver([post_save, post_delete], sender=GiftSet)
@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Subcategory)
@receiver([post_save, post_delete], sender=PremiumFestiveOffer)
def clear_product_caches(sender, **kwargs):
    """Clear all product caches when data changes"""
    # Clear HTML caches
    cache.delete_pattern('html_filter_*')
    
    # Clear API caches  
    cache.delete_pattern('api_filter_*')
    
    # Clear specific caches
    cache.delete('active_offers_cache')
    cache.delete('filter_sidebar_data')
    
    print(f"[CACHE] Cleared all product caches - {sender.__name__}")
