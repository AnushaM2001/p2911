from .models import Category
from admin_panel.models import PremiumFestiveOffer
from django.utils import timezone
from django.db.models import Prefetch, Min, Max, Avg, Q

from user_panel.models import Wishlist


def category_subcategory_navbar(request):
    now = timezone.now()

    # ---------------------------
    # 1. Navbar Categories Logic
    # ---------------------------
    categories = Category.objects.prefetch_related('subcategories').order_by('-created_at')

    navbar_categories = []
    for category in categories:
        # Capitalize only if name starts with lowercase
        if category.name and category.name[0].islower():
            category.name = category.name.capitalize()

        if category.name.startswith('Buy'):
            has_valid_offer = PremiumFestiveOffer.objects.filter(
                premium_festival='Festival',
                is_active=True,
                start_date__lte=now,
                end_date__gte=now,
                category=category
            ).exists()
            if has_valid_offer:
                navbar_categories.append(category)
        else:
            navbar_categories.append(category)

    # ---------------------------
    # 2. Section Categories Logic
    # ---------------------------
    section_categories = []

    for category in categories:
        # Skip categories without an image
        if not category.gif_file:
            continue

        # Capitalize only if first letter is lowercase
        if category.name and category.name[0].islower():
            category.name = category.name.capitalize()

        if category.name.startswith("Buy"):
            has_offer = PremiumFestiveOffer.objects.filter(
                premium_festival='Festival',
                is_active=True,
                start_date__lte=now,
                end_date__gte=now,
                category=category
            ).exists()
            if has_offer:
                section_categories.append(category)
        else:
            section_categories.append(category)

        # Stop after 4 categories
        if len(section_categories) == 4:
            break

    # Fallback: if still empty, take latest 4 categories that have an image
    if not section_categories:
        section_categories = [cat for cat in categories if cat.image][:4]

    return {
        "navbar_categories": navbar_categories,
        "section_categories": section_categories,
    }



# your_app/context_processors.py



def festival_offer_context(request):
    current_time = timezone.now()

    festival_offer = PremiumFestiveOffer.objects.filter(
        premium_festival='Festival',
        start_date__lte=current_time,
        end_date__gt=current_time
    ).order_by('-created_at').first()

    if festival_offer:
        return {
            'festival_offer_percentage': festival_offer.percentage,
            'festival_offer_start': festival_offer.start_date,
            'festival_offer_end': festival_offer.end_date,
            'festival_offer_name': festival_offer.offer_name,
            'festival_offer_category': ', '.join(festival_offer.category.values_list('name', flat=True)),
            'festival_offer_category_ids': list(festival_offer.category.values_list('id', flat=True)),
            'festival_offer_subcategory': ', '.join(festival_offer.subcategory.values_list('name', flat=True)),
            'festival_offer_subcategory_ids': list(festival_offer.subcategory.values_list('id', flat=True)),
        }
    return {}  # No offer found



# user_panel/context_processors.py
from django.urls import reverse
from django.db.models import Prefetch
from admin_panel.models import Order, OrderItem

def latest_purchases_orders(request):
    purchases = []

    try:
        orders = (
            Order.objects
            .select_related("address")  # ✅ ONLY relational fields
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=OrderItem.objects.select_related("product")
                )
            )
            .order_by("-created_at")[:10]
        )

        for order in orders:
            item = order.items.first()
            if not item or not item.product:
                continue

            product = item.product

            purchases.append({
                "product_name": product.name or "Unknown Product",
                "product_price": f"₹{item.price * item.quantity}" if item.price else "Price not available",
                "product_original_price": (
                    f"₹{item.original_price}"
                    if hasattr(item, "original_price") and item.original_price
                    else ""
                ),
                "product_image": (
                    product.image1.url
                    if getattr(product, "image1", None)
                    else ""
                ),
                "location": getattr(order.address, "City", "India"),
                "user_name": getattr(order.address, "Name", "Customer"),
                "product_url": reverse("product_detail", args=[product.id]),
            })

    except Exception as e:
        print(f"Error fetching latest purchases: {e}")
        purchases = []

    return {"latest_purchases": purchases}



# user_panel/context_processors.py
from user_panel.models import Wishlist
from user_panel.views import get_guest_id

def wishlist_context(request):
    guest_id = get_guest_id(request)

    wishlist_ids = list(
        Wishlist.objects.filter(guest_id=guest_id)
        .values_list("product_id", flat=True)
    )

    return {
        "wishlist_product_ids": wishlist_ids,
        "count": len(wishlist_ids),
    }




# def add_subscription(request):
#     from admin_panel.models import Subscription
#     if request.method == 'POST':
#         email = request.POST.get('email')
#         if email:
#             Subscription.objects.get_or_create(email=email)
#     return {}


