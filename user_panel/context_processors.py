from .models import Category
from admin_panel.models import PremiumFestiveOffer
from django.utils import timezone
from django.db.models import Prefetch, Min, Max, Avg, Q

from user_panel.models import Wishlist


# user_panel/context_processors/category_subcategory_navbar.py
from django.utils import timezone
from django.db.models import Prefetch

def category_subcategory_navbar(request):
    """
    Fast navbar builder:
    - Fetch categories+subcategories in one DB hit
    - Fetch current festival offers in one DB hit, build set of category ids
    - No per-category DB queries
    """
    now = timezone.now()

    # 1 query -> categories + subcategories
    categories = list(Category.objects.prefetch_related('subcategories').order_by('-created_at'))

    # 1 query -> active festival offers with their categories
    festival_offers = PremiumFestiveOffer.objects.filter(
        premium_festival='Festival',
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    ).prefetch_related('category')

    # Build set of category ids that have festival offers
    offer_category_ids = set()
    for fo in festival_offers:
        offer_category_ids.update(fo.category.values_list('id', flat=True))

    # Build navbar list without extra queries
    navbar_categories = []
    for cat in categories:
        # keep display-friendly name without changing DB value permanently
        display_name = cat.name.capitalize() if cat.name and cat.name[0].islower() else cat.name

        # Decide inclusion for "Buy..." categories using precomputed set
        if display_name.startswith('Buy'):
            if cat.id in offer_category_ids:
                navbar_categories.append(cat)
        else:
            navbar_categories.append(cat)

    # section categories: first 4 with gifs (fast in-memory filter)
    section_categories = [c for c in categories if getattr(c, "gif_file", None)]
    section_categories = section_categories[:4]

    return {
        "navbar_categories": navbar_categories,
        "section_categories": section_categories,
    }

# your_app/context_processors.py



def festival_offer_context(request):
    """
    Return the currently active Festival offer (if any).
    Single fast query; return only required fields.
    """
    now = timezone.now()

    festival_offer = PremiumFestiveOffer.objects.filter(
        premium_festival='Festival',
        is_active=True,
        start_date__lte=now,
        end_date__gt=now
    ).order_by('-created_at').first()

    if not festival_offer:
        return {}

    # Only fetch IDs & names, avoid heavy fields
    category_ids = list(festival_offer.category.values_list('id', flat=True))
    subcategory_ids = list(festival_offer.subcategory.values_list('id', flat=True))

    return {
        'festival_offer_percentage': festival_offer.percentage,
        'festival_offer_start': festival_offer.start_date,
        'festival_offer_end': festival_offer.end_date,
        'festival_offer_name': festival_offer.offer_name,
        'festival_offer_category_ids': category_ids,
        'festival_offer_subcategory_ids': subcategory_ids,
    }



# user_panel/context_processors.py
from django.urls import reverse
from admin_panel.models import Order,OrderItem
# user_panel/context_processors/latest_purchases_orders.py
from django.core.cache import cache


CACHE_KEY = "latest_purchases_cache_v1"
CACHE_TTL = 300  # 5 minutes (adjustable)

def latest_purchases_orders(request):
    """
    Return a small list of recent purchases for the navbar.
    - Cached for CACHE_TTL seconds to avoid heavy per-request work.
    - Only the minimal fields required by frontend are returned.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return {"latest_purchases": cached}

    purchases = []
    try:
        # Single DB hit to fetch last 10 orders + first item per order (prefetch with select_related)
        orders = Order.objects.select_related("user", "address").prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product"))
        ).order_by("-created_at")[:10]

        for order in orders:
            item = next(iter(order.items.all()), None)
            if not item or not getattr(item, "product", None):
                continue

            product = item.product
            purchases.append({
                "product_name": product.name or "Unknown Product",
                "product_price": f"₹{item.price}" if item.price is not None else "Price not available",
                "product_original_price": f"₹{getattr(item, 'original_price', '')}" if getattr(item, 'original_price', None) else "",
                "product_image": product.image1.url if getattr(product, "image1", None) else "",
                "location": getattr(order.address, "City", "India"),
                "user_name": getattr(order.address, "Name", "Customer"),
                "product_url": reverse("product_detail", args=[product.id]) if product.id else "#",
            })

        # Cache compact result
        cache.set(CACHE_KEY, purchases, CACHE_TTL)

    except Exception as e:
        # Keep retry-safe: return empty list if anything goes wrong
        # Log server-side if you have logging configured; avoid printing in production
        purchases = []

    return {"latest_purchases": purchases}


# user_panel/context_processors/wishlist_count.py
from user_panel.models import Wishlist

def wishlist_count(request):
    """
    Fast wishlist count: a single COUNT query when user is authenticated.
    This is cheap; if you want, cache per-user with a short TTL.
    """
    if request.user.is_authenticated:
        try:
            count = Wishlist.objects.filter(user=request.user).count()
        except Exception:
            count = 0
        return {"wishlist_count": count}
    return {"wishlist_count": 0}



# def add_subscription(request):
#     from admin_panel.models import Subscription
#     if request.method == 'POST':
#         email = request.POST.get('email')
#         if email:
#             Subscription.objects.get_or_create(email=email)
#     return {}

