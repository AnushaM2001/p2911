# user_panel/tasks/snapshots.py
import time
from decimal import Decimal
from django.core.cache import cache
from django.db.models import Min, Max, Avg, Count, FloatField, Q
from django.db.models.functions import Cast
from django.utils import timezone

from user_panel.models import *
from admin_panel.models import *

SNAPSHOT_PREFIX = "snapshot:filter:v1:"  # snapshot:filter:v1:cat:<id> or snapshot:filter:v1:global

def _float(x):
    if x is None:
        return None
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except Exception:
        return x

def build_snapshot_for_category(cat_id=None):
    """
    Build & store snapshot for category (or global if cat_id is None).
    Snapshot is stored persistently in Redis (cache.set with timeout=None).
    """
    start = time.time()
    now = timezone.now()

    # --- Active offers (real-time)
    offers_qs = PremiumFestiveOffer.objects.filter(is_active=True)
    active_offers = []
    for of in offers_qs:
        if of.premium_festival in ["Welcome", "Premium"]:
            active_offers.append(of)
            continue
        if of.start_date and of.end_date and (of.start_date <= now <= of.end_date):
            active_offers.append(of)

    offers_by_cat = {}
    offers_by_sub = {}
    generic_offers = []
    for of in active_offers:
        cats = getattr(of, "cached_categories", None)
        subs = getattr(of, "cached_subcategories", None)
        if cats:
            for c in cats:
                offers_by_cat.setdefault(c.id, []).append(of)
        if subs:
            for s in subs:
                offers_by_sub.setdefault(s.id, []).append(of)
        if (not cats) and (not subs):
            generic_offers.append(of)

    # --- Giftsets
    gift_qs = GiftSet.objects.select_related("product").prefetch_related("flavours")
    if cat_id:
        gift_qs = gift_qs.filter(product__category_id=cat_id)

    gift_product_ids = list(gift_qs.values_list("product_id", flat=True).distinct())
    gift_rows = GiftSet.objects.filter(product_id__in=gift_product_ids).select_related("product").prefetch_related("flavours")

    gift_map = {}
    for gs in gift_rows:
        if gs.product_id not in gift_map:
            gift_map[gs.product_id] = gs

    gift_price_map_qs = (
        GiftSet.objects.filter(product_id__in=gift_product_ids)
        .values("product_id")
        .annotate(min_price=Min("price"), max_price=Max("price"))
    )
    gift_price_map = {x["product_id"]: x for x in gift_price_map_qs}

    gift_review_qs = (
        Product.objects.filter(id__in=gift_product_ids)
        .values("id")
        .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews"))
    )
    gift_review_map = {x["id"]: x for x in gift_review_qs}

    gift_list = []
    for pid, gs in gift_map.items():
        candidates = offers_by_cat.get(gs.product.category_id, []) + offers_by_sub.get(gs.product.subcategory_id, []) + generic_offers
        discounted_price = None
        applied_offer = None
        for of in candidates:
            d = of.apply_offer(gs)
            if d:
                discounted_price = float(d)
                applied_offer = of
                break

        gp = gift_price_map.get(pid, {})
        pr_min = float(gp.get("min_price") or (gs.price or 0))
        pr_max = float(gp.get("max_price") or (gs.price or 0))
        rev = gift_review_map.get(pid, {"avg_rating": None, "review_count": 0})
        avg_rating = float(rev.get("avg_rating") or 0)
        review_count = int(rev.get("review_count") or 0)

        gift_list.append({
            "id": gs.product.id,
            "name": gs.product.name,
            "original_price": _float(gs.product.original_price or 0),
            "price": _float(gs.price or 0),
            "min_price": pr_min,
            "max_price": pr_max,
            "min_original_price": _float(gs.product.original_price or 0),
            "max_original_price": _float(gs.product.original_price or 0),
            "discounted_price": discounted_price,
            "offer_code": applied_offer.code if applied_offer else None,
            "offer_start_time": applied_offer.start_date.isoformat() if applied_offer and applied_offer.start_date else None,
            "offer_end_time": applied_offer.end_date.isoformat() if applied_offer and applied_offer.end_date else None,
            "flavours": list(gs.flavours.values_list("name", flat=True)),
            "image": gs.product.image1.url if gs.product.image1 else "",
            "image2": gs.product.image2.url if gs.product.image2 else "",
            "is_active": gs.product.is_active,
            "is_giftset": True,
            "average_rating": avg_rating,
            "review_count": review_count,
            "stock_status": gs.product.stock_status or "In Stock",
            "category_id": gs.product.category_id,
            "subcategory_id": gs.product.subcategory_id,
        })

    # --- Variants
    vqs = ProductVariant.objects.select_related("product")
    if cat_id:
        vqs = vqs.filter(product__category_id=cat_id)

    gift_product_ids_all = list(GiftSet.objects.values_list("product_id", flat=True).distinct())
    if gift_product_ids_all:
        vqs = vqs.exclude(product_id__in=gift_product_ids_all)

    product_ids = list(vqs.values_list("product_id", flat=True).distinct())

    smallest_variant = {}
    for v in ProductVariant.objects.filter(product_id__in=product_ids).order_by("product_id", "price").select_related("product"):
        if v.product_id not in smallest_variant:
            smallest_variant[v.product_id] = v

    price_map_qs = (
        ProductVariant.objects.filter(product_id__in=product_ids)
        .values("product_id")
        .annotate(
            min_price=Min("price"),
            max_price=Max("price"),
            min_original=Min(Cast("original_price", FloatField())),
            max_original=Max(Cast("original_price", FloatField()))
        )
    )
    price_map = {x["product_id"]: x for x in price_map_qs}

    review_map_qs = (
        Product.objects.filter(id__in=product_ids)
        .values("id")
        .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews"))
    )
    review_map = {x["id"]: x for x in review_map_qs}

    variant_list = []
    for pid, v in smallest_variant.items():
        candidates = offers_by_cat.get(v.product.category_id, []) + offers_by_sub.get(v.product.subcategory_id, []) + generic_offers
        discounted_price = None
        applied_offer = None
        for of in candidates:
            d = of.apply_offer(v)
            if d:
                discounted_price = float(d)
                applied_offer = of
                break

        pm = price_map.get(pid, {})
        min_p = float(pm.get("min_price") or (v.price or 0))
        max_p = float(pm.get("max_price") or (v.price or 0))
        min_orig = float(pm.get("min_original") or 0)
        max_orig = float(pm.get("max_original") or 0)

        rev = review_map.get(pid, {"avg_rating": None, "review_count": 0})
        avg_rating = float(rev.get("avg_rating") or 0)
        review_count = int(rev.get("review_count") or 0)

        variant_list.append({
            "id": v.product.id,
            "name": v.product.name,
            "original_price": _float(v.product.original_price or 0),
            "price": _float(v.price or 0),
            "min_price": min_p,
            "max_price": max_p,
            "min_original_price": min_orig,
            "max_original_price": max_orig,
            "discounted_price": discounted_price,
            "offer_code": applied_offer.code if applied_offer else None,
            "offer_start_time": applied_offer.start_date.isoformat() if applied_offer and applied_offer.start_date else None,
            "offer_end_time": applied_offer.end_date.isoformat() if applied_offer and applied_offer.end_date else None,
            "size": v.size,
            "stock": v.stock,
            "image": v.product.image1.url if v.product.image1 else "",
            "image2": v.product.image2.url if v.product.image2 else "",
            "is_active": v.product.is_active,
            "is_giftset": False,
            "average_rating": avg_rating,
            "review_count": review_count,
            "stock_status": v.product.stock_status or "In Stock",
            "category_id": v.product.category_id,
            "subcategory_id": v.product.subcategory_id,
        })

    snapshot = {
        "built_at": time.time(),
        "category_id": cat_id,
        "variants": variant_list,
        "giftsets": gift_list,
    }

    key = SNAPSHOT_PREFIX + (f"cat:{cat_id}" if cat_id else "global")
    cache.set(key, snapshot, timeout=None)  # persist until invalidated
    return snapshot
