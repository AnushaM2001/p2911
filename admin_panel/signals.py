# core/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging
from admin_panel.models import *
from user_panel.models import *
logger = logging.getLogger(__name__)

# 1. CRITICAL MODELS - Clear everything
@receiver([post_save, post_delete], sender='user_panel.Product')
@receiver([post_save, post_delete], sender='user_panel.ProductVariant')
@receiver([post_save, post_delete], sender='user_panel.GiftSet')
def clear_all_product_caches(sender, instance=None, **kwargs):
    """When products/variants change, clear ALL filter caches"""
    logger.info(f"Cache clear: {sender.__name__} changed")
    
    # Clear all product-related caches
    cache.delete_pattern('products_filter_*')
    cache.delete_pattern('filter_products_*')
    
    # Clear specific caches if we have instance
    if instance and hasattr(instance, 'product_id'):
        cache.delete_pattern(f'*product_{instance.product_id}*')

# 2. SUPPORTING MODELS - Selective clearing
@receiver([post_save, post_delete], sender='user_panel.Category')
@receiver([post_save, post_delete], sender='user_panel.Subcategory')
def clear_category_caches(sender, instance=None, **kwargs):
    """Clear category-related caches"""
    if instance and instance.id:
        cache.delete_pattern(f'*category_{instance.id}*')
        cache.delete_pattern(f'*subcategory_*')

# 3. OFFERS & PRICING - Clear pricing caches
@receiver([post_save, post_delete], sender='user_panel.PremiumFestiveOffer')
def clear_offer_caches(sender, **kwargs):
    """When offers change, clear active offers cache"""
    cache.delete('active_offers_cache')
    cache.delete_pattern('*offer_*')
