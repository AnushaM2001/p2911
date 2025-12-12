# user_panel/signals.py
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache

from admin_panel.models import ProductVariant, GiftSet, Product, PremiumFestiveOffer, Review
from user_panel.tasks.celery_tasks import rebuild_snapshot_task

SNAPSHOT_PREFIX = "snapshot:filter:v1:"

def invalidate_and_rebuild(cat_id):
    key = SNAPSHOT_PREFIX + (f"cat:{cat_id}" if cat_id else "global")
    cache.delete(key)
    try:
        rebuild_snapshot_task.delay(cat_id)
    except Exception:
        # Fallback synchronous rebuild if Celery unavailable
        from user_panel.tasks.snapshots import build_snapshot_for_category
        build_snapshot_for_category(cat_id)

@receiver(post_save, sender=PremiumFestiveOffer)
@receiver(post_delete, sender=PremiumFestiveOffer)
def offer_changed(sender, instance, **kwargs):
    # rebuild global and affected categories
    invalidate_and_rebuild(None)
    try:
        for c in instance.category.all():
            invalidate_and_rebuild(c.id)
    except Exception:
        pass
    try:
        for s in instance.subcategory.all():
            # rebuild snapshot for category of subcategory (safer: rebuild all categories that include subcategory)
            invalidate_and_rebuild(s.category_id)
    except Exception:
        pass

@receiver(post_save, sender=ProductVariant)
@receiver(post_delete, sender=ProductVariant)
def variant_changed(sender, instance, **kwargs):
    cat_id = instance.product.category_id if instance and instance.product else None
    invalidate_and_rebuild(cat_id)

@receiver(post_save, sender=GiftSet)
@receiver(post_delete, sender=GiftSet)
def giftset_changed(sender, instance, **kwargs):
    cat_id = instance.product.category_id if instance and instance.product else None
    invalidate_and_rebuild(cat_id)

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def product_changed(sender, instance, **kwargs):
    if instance:
        invalidate_and_rebuild(instance.category_id)

@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def review_changed(sender, instance, **kwargs):
    if instance and instance.product_id:
        try:
            p = Product.objects.get(id=instance.product_id)
            invalidate_and_rebuild(p.category_id)
        except Product.DoesNotExist:
            pass
