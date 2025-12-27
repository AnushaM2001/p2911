# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from admin_panel.models import *

def safe_delete_pattern(pattern):
    """
    Works with Redis.
    Falls back to full cache clear for LocMemCache.
    """
    if hasattr(cache, "delete_pattern"):
        cache.delete_pattern(pattern)
    else:
        # LocMemCache has no pattern delete
        cache.clear()

@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductVariant)
@receiver([post_save, post_delete], sender=GiftSet)
@receiver([post_save, post_delete], sender=Category)
@receiver([post_save, post_delete], sender=Subcategory)
@receiver([post_save, post_delete], sender=PremiumFestiveOffer)
def clear_product_caches(sender, **kwargs):
    safe_delete_pattern('html_filter_*')
    safe_delete_pattern('api_filter_*')

    cache.delete('active_offers_cache')
    cache.delete('filter_sidebar_data')

    print(f"[CACHE] Cleared product caches ({sender.__name__})")
