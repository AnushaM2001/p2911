import random
import string
import json
import time
import traceback
from io import BytesIO
from urllib.parse import urlparse
from django.utils.http import url_has_allowed_host_and_scheme

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.template.loader import render_to_string, get_template
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, Http404, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Sum, Q, Min, Max, Avg, Count
from django.db.models.functions import Lower
from django.core.mail import send_mail, EmailMessage
from django.views.decorators.cache import cache_page
from django.db.models import Min, Max, Avg, Count, IntegerField, Value
from django.db.models.functions import Cast
from django.db.models.functions import Coalesce, Cast

import razorpay
import redis
from requests import request
from xhtml2pdf import pisa

from .models import Category, Subcategory, Product, Order, OrderItem, Payment, Cart, GiftSet
from .forms import InternationalOrderForm
from .forms import *  # If there are other forms in your module
from user_panel.models import *
from user_panel.forms import *
from admin_panel.models import *
from admin_panel.utils import create_shiprocket_order
from admin_panel.views import notify_admins
from admin_panel.tasks import (
    create_shiprocket_order_task,
    send_invoice_email_task,
    notify_low_stock_task
)
from django.utils.timezone import now
from django.apps import apps
from django.db.models.functions import Cast, Lower, Greatest
import uuid
import time
import json
import hashlib
from decimal import Decimal

from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.cache import cache

from django.db.models import (
    Q,
    F,
    Min,
    Max,
    Avg,
    Count,
    FloatField,
    Prefetch,
    Window,
)
from django.db.models.functions import (
    Cast,
    RowNumber,
)
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
# from channels.layers import get_channel_layer
# from asgiref.sync import async_to_sync
import redis
import json

import logging

# def get_guest_id(request):
#     if not request.session.get("guest_id"):
#         request.session["guest_id"] = f"guest_{uuid.uuid4().hex}"
#     return request.session["guest_id"]
def get_guest_id(request):
    if not request.session.get("guest_id"):
        request.session["guest_id"] = f"guest_{uuid.uuid4().hex}"
    return request.session["guest_id"]

# Redis client
r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

def progress(request):
    return render(request, 'user_panel/progress.html')


def a(req):
    return render(req,'user_panel/home3.html')

def generate_otp():
    return ''.join(random.choices(string.digits, k=4))



# ---------------- ADD TO CART ----------------


def blocked_user_view(request):
    return render(request, 'user_panel/blocked_user.html')


def home1(request):
    current_time = timezone.now()

    # --------------------------------------------------
    # 🔹 Common product annotations (REUSED everywhere)
    # --------------------------------------------------
    product_annotations = {
"min_price": Min("variants__price", filter=Q(variants__price__isnull=False)),
    "max_price": Max("variants__price", filter=Q(variants__price__isnull=False)) - Value(100),
    "s_price": Min(Cast("variants__original_price", IntegerField())),
    "e_price": Max(Cast("variants__original_price", IntegerField())),
    "average_rating": Avg("reviews__rating"),
    "review_count": Count("reviews", distinct=True),
    }

    # --------------------------------------------------
    # 🔹 Festival Offer (single query)
    # --------------------------------------------------
    festival_offer = (
        PremiumFestiveOffer.objects
        .filter(
            premium_festival="Festival",
            start_date__lte=current_time,
            end_date__gt=current_time
        )
        .only("percentage", "start_date", "end_date", "offer_name")
        .order_by("-created_at")
        .first()
    )

    offer_percentage = festival_offer.percentage if festival_offer else None
    startdatetime = festival_offer.start_date if festival_offer else None
    enddatetime = festival_offer.end_date if festival_offer else None
    offername = festival_offer.offer_name if festival_offer else None

    # --------------------------------------------------
    # 🔹 Banners (split once, no loop logic later)
    # --------------------------------------------------
    banners = list(Banner.objects.all().order_by("created_at"))
    first_banner_no_section = next(
        (b for b in banners if not b.section), None
    )
    other_banners = [b for b in banners if b != first_banner_no_section]

    # --------------------------------------------------
    # 🔹 Categories & Subcategories
    # --------------------------------------------------
    categories = Category.objects.all().order_by("-created_at")[:4]

    subcategories = (
        Subcategory.objects
        .annotate(name_lower=Lower("name"))
        .filter(
            name_lower__in=[
                "french perfumes",
                "arabic perfumes",
                "french attars",
                "arabic attars",
            ]
        )
        .order_by("-created_at")[:4]
    )

    occasions = (
        Subcategory.objects
        .annotate(name_lower=Lower("name"))
        .filter(
            name_lower__in=["sports", "office", "party", "travel"]
        )
        .order_by("-created_at")[:4]
    )

    # --------------------------------------------------
    # 🔹 Scroll Bar Product (cheap query)
    # --------------------------------------------------
    ScrollBar = (
        Product.objects
        .exclude(scroll_bar__isnull=True)
        .exclude(scroll_bar="")
        .order_by("-created_at")
        .first()
    )

    # --------------------------------------------------
    # 🔹 Product Sections (BEST / NEW / TRENDING)
    # --------------------------------------------------
    base_products = (
        Product.objects
        .select_related()
        .prefetch_related("variants", "reviews")
        .annotate(**product_annotations)
        .order_by("-created_at")
    )

    best_selling = base_products.filter(is_best_seller=True)[:12]
    new_arrival = base_products.filter(is_new_arrival=True)[:12]
    trending = base_products.filter(is_trending=True)[:12]


    # --------------------------------------------------
    # 🔹 Videos & Reviews
    # --------------------------------------------------
    videos = ProductVideo.objects.all().order_by("-created_at")[:10]
    out_reviews = Client_review.objects.all()

    # --------------------------------------------------
    # 🔹 Render
    # --------------------------------------------------
    return render(request, "user_panel/home1.html", {
        "offername": offername,
        "offer_percentage": offer_percentage,
        "startdatetime": startdatetime,
        "enddatetime": enddatetime,
        "festival_offer": festival_offer,

        "banners": banners,
        "first_banner_no_section": first_banner_no_section,
        "other_banners": other_banners,

        "categories": categories,
        "subcategories": subcategories,
        "occasions": occasions,

        "best_selling": best_selling,
        "new_arrival": new_arrival,
        "trending": trending,
        "ScrollBar": ScrollBar,

        "videos": videos,
        "out_reviews": out_reviews,
        "other_banners": other_banners,
    })


##filter subcategory items ---is is shown filtered subcategories

def video_detail(request, video_id):
    video = get_object_or_404(ProductVideo, id=video_id)
    related_products = video.related_products.all()
    return render(request, 'user_panel/video_detail.html', {
        'video': video,
        'related_products': related_products,
    })

def all_view(request):
    letters = list("#ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    resolved_product_map = {letter: [] for letter in letters}

    # Fetch all products with related category & subcategory
    products = Product.objects.select_related('category', 'subcategory').all()

    seen_names= set()

    for product in products:
        name_upper = product.name.strip().upper()
        if name_upper in seen_names:
            continue
        seen_names.add(name_upper)
        first_char = name_upper[0]
        key = '#' if first_char.isdigit() else first_char
        if key in resolved_product_map:
            resolved_product_map[key].append(product)

    context = {
        'letters': letters,
        'letter_sections': [
            {
                'letter': letter,
                'products': resolved_product_map[letter],
            }
            for letter in letters if resolved_product_map[letter]  # only non-empty
        ]
    }
    return render(request, 'user_panel/All.html', context)


from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Product


@require_POST
def toggle_wishlist(request):
    guest_id = get_guest_id(request)
    product_id = request.POST.get("product_id")

    product = get_object_or_404(Product, id=product_id)

    wishlist_item = Wishlist.objects.filter(
        guest_id=guest_id,
        product=product
    ).first()

    if wishlist_item:
        wishlist_item.delete()
        status = "removed"
    else:
        Wishlist.objects.create(
            guest_id=guest_id,
            product=product
        )
        status = "added"

    count = Wishlist.objects.filter(guest_id=guest_id).count()

    return JsonResponse({
        "success":True,
        "status": status,
        "count": count
    })




def strip_seo_suffix(slug):
    suffix = f"-{settings.SEO_SUFFIX}"
    return slug.replace(suffix, "") if slug and slug.endswith(suffix) else slug


def filtered_products(request, category_slug=None, subcategory_slug=None):
    start_time = time.time()
   

    raw_category_slug = category_slug
    raw_subcategory_slug = subcategory_slug

    category_slug = strip_seo_suffix(category_slug)
    subcategory_slug = strip_seo_suffix(subcategory_slug)
    # print("========== CATEGORY DEBUG ==========")
    # print("CATEGORY SLUG FROM URL:", category_slug)
    # print("DB SLUGS:", list(Category.objects.values_list("slug", flat=True)))
    # print("====================================")

    

    # ================= FETCH OBJECTS =================
    category = None
    subcategory = None

    if category_slug:
        if category_slug.isdigit():
            category = get_object_or_404(Category, id=int(category_slug))
            return redirect(category.get_absolute_url(), permanent=True)
        else:
            category = get_object_or_404(Category, slug=category_slug)

    if subcategory_slug:
        if subcategory_slug.isdigit():
            subcategory = get_object_or_404(Subcategory, id=int(subcategory_slug))
            return redirect(subcategory.get_absolute_url(), permanent=True)
        else:
            subcategory = get_object_or_404(Subcategory, slug=subcategory_slug)

    # ================== CANONICAL SEO REDIRECT ==================
    # ================== CANONICAL SEO (SAFE) ==================
    # ================== CANONICAL SEO REDIRECT (FIXED) ==================
    if category or subcategory:
        if subcategory:
            canonical_url = subcategory.get_absolute_url()
        else:
            canonical_url = category.get_absolute_url()

    # 🔥 Do NOT block JS/AJAX-based filtering
        if canonical_url and request.path.rstrip("/") != canonical_url.rstrip("/"):
            return redirect(canonical_url, permanent=True)


    active_category_id = category.id if category else None
    active_subcategory_id = subcategory.id if subcategory else None
    # 🔥 FALLBACK: inject URL-based filters if GET is empty
    

    # Banner priority logic
    category_banner_url = None
    subcategory_banner_url = None

    if subcategory and subcategory.banner:
       subcategory_banner_url = subcategory.banner.url
    elif category and category.banner:
       category_banner_url = category.banner.url

    # ================== SEO TITLE & META ==================
    H_TAG = "Perfume Valley Best Perfumes and Attars"
    DEFAULT_TITLE = "Perfume Valley | Premium Perfumes & Attars"
    DEFAULT_DESC = (
    "Buy premium perfumes and attars online in India from Perfume Valley. "
    "Best prices, authentic fragrances, fast delivery."
)

    seo_title = DEFAULT_TITLE
    seo_description = DEFAULT_DESC
    h_tag= H_TAG
    if subcategory:
    # Priority 1: Subcategory SEO
        seo_title = (
        subcategory.seo_title
        if subcategory.seo_title
        else f"Buy {subcategory.name} Online in India | Perfume Valley"
    )
        seo_description = (
        subcategory.seo_description
        if subcategory.seo_description
        else f"Shop {subcategory.name.lower()} online in India. Premium fragrances at Perfume Valley."
    )
        h_tag=(
            subcategory.h_tag if subcategory.h_tag else f"Perfume Valley World {subcategory.name}"
        )

    elif category:
    # Priority 2: Category SEO
        seo_title = (
        category.seo_title
        if category.seo_title
        else f"Buy {category.name} Online in India | Perfume Valley"
    )
        seo_description = (
        category.seo_description
        if category.seo_description
        else f"Explore premium {category.name.lower()} online in India at Perfume Valley."
    )
        h_tag =(
            category.h_tag if category.h_tag else f"Perfume Valley World { category.name }"
        )

    # ================= STRIP SEO SUFFIX =================
    


    # ================== CREATE CACHE KEY ==================
    params_dict = {
        'category_slug': category_slug,
        'subcategory_slug': subcategory_slug,
        'categories': request.GET.get('categories', ''),
        'subcategories': request.GET.get('subcategories', ''),
        'path': request.path
    }
    cache_key = f"html_filter_{hashlib.md5(json.dumps(params_dict, sort_keys=True).encode()).hexdigest()}"
    cached_context = cache.get(cache_key)
    # if cached_context:
    #     cached_context['cache_hit'] = True
    #     cached_context['execution_time'] = round(time.time() - start_time, 3)
    #     return render(request, 'user_panel/filtered_products.html', cached_context)

    # ================== FILTER PARAMETERS ==================
    # ================== FILTER PARAMETERS (FIXED) ==================
    category_ids = []
    subcategory_ids = []

# From GET params
    if request.GET.get('categories'):
        try:
            category_ids = [int(i) for i in request.GET.get('categories').split(',') if i]
        except ValueError:
            category_ids = []

    if request.GET.get('subcategories'):
        try:
           subcategory_ids = [int(i) for i in request.GET.get('subcategories').split(',') if i]
        except ValueError:
            subcategory_ids = []

# 🔥 FALLBACK FROM URL SLUG (CRITICAL)
    if not category_ids and category:
        category_ids = [category.id]

    if not subcategory_ids and subcategory:
        subcategory_ids = [subcategory.id]


    # ================== CHECK IF GIFTSET ==================
    is_giftset = False
    if category:
        is_giftset = (
    category and
    not subcategory and
    'giftsets' in category.slug.lower()
)

    # ================== PROCESS PRODUCTS ==================
    product_list = []

    if is_giftset and category:
        # GIFTSETS
        giftsets_products = Product.objects.filter(category=category).prefetch_related('gift_sets__flavours')

        # Active offers
        now = timezone.now()
        active_offers = PremiumFestiveOffer.objects.filter(
            Q(premium_festival__in=['Welcome', 'Premium']) |
            Q(start_date__lte=now, end_date__gte=now)
        )

        for product in giftsets_products:
            giftset = product.gift_sets.first()
            if not giftset:
                continue

            discounted_price = None
            offer_code = None
            for offer in active_offers:
                discounted = offer.apply_offer(giftset)
                if discounted:
                    discounted_price = discounted
                    offer_code = offer.code
                    break

            product_list.append({
                'id': product.id,
                'name': product.name,
                'price': float(giftset.price or 0),
                'discounted_price': float(discounted_price) if discounted_price else None,
                'original_price': float(giftset.original_price or 0),
                'offer_code': offer_code,
                'flavours': list(giftset.flavours.values_list('name', flat=True)) if hasattr(giftset, 'flavours') else [],
                'image': product.image1.url if product.image1 else '',
                'average_rating': 0,
                'is_giftset': True,
            })

        context_products = product_list

    else:
        # REGULAR PRODUCTS
        base_qs = Product.objects.all()

        # if category_ids:
        #     base_qs = base_qs.filter(category_id__in=category_ids)
        if subcategory_ids:
            base_qs = base_qs.filter(subcategory_id__in=subcategory_ids)

        elif category_ids:
            base_qs = base_qs.filter(category_id__in=category_ids)

        # if subcategory_ids:
        #     base_qs = base_qs.filter(subcategory_id__in=subcategory_ids)
        # if subcategory:
        #     base_qs = base_qs.filter(subcategory=subcategory)

        # Annotate prices & ratings
        products_qs = base_qs.annotate(
            min_price=Min('variants__price'),
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        ).prefetch_related(Prefetch('variants', queryset=ProductVariant.objects.all()))

        # Active offers
        now = timezone.now()
        active_offers = PremiumFestiveOffer.objects.filter(
            Q(premium_festival__in=['Welcome', 'Premium']) |
            Q(start_date__lte=now, end_date__gte=now)
        )

        for product in products_qs:
            cheapest_variant = product.variants.order_by('price').first()
            discounted_price = None
            offer_code = None

            if cheapest_variant:
                for offer in active_offers:
                    discounted = offer.apply_offer(cheapest_variant)
                    if discounted:
                        discounted_price = discounted
                        offer_code = offer.code
                        break

            product_list.append({
                'id': product.id,
                'name': product.name,
                'price': float(product.min_price or 0),
                'discounted_price': float(discounted_price) if discounted_price else None,
                'original_price': float(product.original_price or 0),
                'offer_code': offer_code,
                'image': product.image1.url if product.image1 else '',
                'average_rating': float(product.average_rating or 0),
                'review_count': product.review_count or 0,
                'is_giftset': False,
            })

        context_products = product_list

    # ================== SIDEBAR DATA ==================
    sidebar_cache_key = 'filter_sidebar_data'
    sidebar_data = cache.get(sidebar_cache_key)
    if not sidebar_data:
        try:
            price_range = ProductVariant.objects.filter(product__is_active=True).aggregate(
                min_price=Min('price'), max_price=Max('price')
            )
        except:
            price_range = ProductVariant.objects.all().aggregate(min_price=Min('price'), max_price=Max('price'))

        sidebar_data = {
            'categories': list(Category.objects.all().values('id', 'name', 'slug')),
            'subcategories': list(Subcategory.objects.all().values('id', 'name', 'slug', 'category_id')),
            'sizes': list(ProductVariant.objects.values_list('size', flat=True).distinct()),
            'min_price': int(price_range['min_price'] or 0),
            'max_price': int(price_range['max_price'] or 1000)
        }
        cache.set(sidebar_cache_key, sidebar_data, 3600)

    # ================== CONTEXT ==================
    context = {
        'category': category,
        'subcategory': subcategory,
        'categories': sidebar_data['categories'],
        'subcategories': sidebar_data['subcategories'],
        'sizes': sidebar_data['sizes'],
        'min_price': sidebar_data['min_price'],
        'max_price': sidebar_data['max_price'],
        'products': context_products,
        'category_banner_url': category_banner_url,
        'subcategory_banner_url': subcategory_banner_url,

        'is_giftset': is_giftset,
        'cache_key': cache_key,
        'execution_time': round(time.time() - start_time, 3),
        'cache_hit': False,
        'seo_title': seo_title,
        'seo_description':seo_description,
        'h_tag':h_tag,
        'active_category_id': active_category_id,
        'active_subcategory_id': active_subcategory_id,
    }

    if is_giftset:
        context['giftsets'] = product_list

    cache.set(cache_key, context, 300)
    return render(request, 'user_panel/filtered_products.html', context)
from django.contrib.auth import logout 
# ============================================================
# 2) AJAX API VIEW (ajax_filter_products) - FIXED VERSION
# ============================================================
def ajax_filter_products(request):
    print("🔥 AJAX GET:", dict(request.GET))
    print("🔥 REFERER:", request.META.get("HTTP_REFERER"))

    """Optimized AJAX API with caching - FIXED with correct original price calculations"""
    start_time = time.time()
    
    # Create cache key
    # params_str = json.dumps(dict(request.GET), sort_keys=True)
    params_str = json.dumps({
    "get": dict(request.GET),
    "path": request.META.get("HTTP_REFERER", "")
}, sort_keys=True)

    cache_key = f"api_filter_{hashlib.md5(params_str.encode()).hexdigest()}"

    
    # Check cache
    cached_response = cache.get(cache_key)
    if cached_response:
        cached_response['cache_hit'] = True
        cached_response['execution_time'] = round(time.time() - start_time, 3)
        return JsonResponse(cached_response)
    
    # ========== PARSE FILTERS ==========
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1
    
    # Get filter lists
    category_ids = []
    for cat_id in request.GET.getlist('category[]', []):
        if cat_id.isdigit():
            category_ids.append(int(cat_id))
    
    subcategory_ids = []
    for subcat_id in request.GET.getlist('subcategory[]', []):
        if subcat_id.isdigit():
            subcategory_ids.append(int(subcat_id))
    # print("AJAX category_ids:", category_ids)
    # print("AJAX subcategory_ids:", subcategory_ids)

    # ================= URL SLUG FALLBACK =================
# If AJAX has no filters, infer from referer URL
    if not category_ids and not subcategory_ids and not request.GET.getlist('category[]') and not request.GET.getlist('subcategory[]'):
        referer = request.META.get("HTTP_REFERER", "")
    #     print("URL fallback triggered:", (
    # not category_ids and
    # not subcategory_ids and
    # not request.GET.getlist('category[]') and
    # not request.GET.getlist('subcategory[]')
# ))

    
        try:
            path = urlparse(referer).path.strip("/").split("/")
            # Expected:
            # ['products', 'category-slug', 'subcategory-slug']
        
            if len(path) >= 2 and path[0] == "products":
                category_slug = strip_seo_suffix(path[1])
                category = Category.objects.filter(slug=category_slug).first()
                if category:
                    category_ids = [category.id]

            if len(path) >= 3:
                sub_slug = strip_seo_suffix(path[2])
                subcategory = Subcategory.objects.filter(slug=sub_slug).first()
                if subcategory:
                    subcategory_ids = [subcategory.id]
        except Exception:
            pass

    
    sizes = request.GET.getlist('size[]', [])
    
    # Price filters
    min_price = max_price = None
    try:
        min_price = float(request.GET.get('min_price', 0))
    except (ValueError, TypeError):
        min_price = None
    
    try:
        max_price = float(request.GET.get('max_price', 100000))
    except (ValueError, TypeError):
        max_price = None

    # ========== PERFUME PRICE RULE ===
    if max_price is not None and (
        Category.objects.filter(
        id__in=category_ids,
        name__icontains="perfume"
    ).exists()
    or
        Subcategory.objects.filter(
        id__in=subcategory_ids,
        name__icontains="perfume"
    ).exists()
):
        max_price = max(0, max_price - 100)


    
    # ========== GET CATEGORY/SUBCATEGORY ==========
    cat_obj = subcat_obj = None
    category_name = subcategory_name = ""
    category_banner_url = subcategory_banner_url = ""
    giftsets_flag = False
    
    if category_ids:
        cat_obj = Category.objects.filter(id__in=category_ids).first()
        if cat_obj:
            category_name = cat_obj.name
            category_banner_url = cat_obj.banner.url if cat_obj.banner else ""
            giftsets_flag = 'giftsets' in category_name.lower()
    
    if subcategory_ids:
        subcat_obj = Subcategory.objects.filter(id__in=subcategory_ids).first()
        if subcat_obj:
            subcategory_name = subcat_obj.name
            subcategory_banner_url = subcat_obj.banner.url if subcat_obj.banner else ""
    
    # ========== CACHE ACTIVE OFFERS ==========
    now = timezone.now()
    active_offers = cache.get('active_offers_cache')
    if active_offers is None:
        active_offers = [
        offer for offer in PremiumFestiveOffer.objects.filter(
            is_active=True,
            premium_festival="Festival"
        )
        if offer.offer_active_now()
    ]
        cache.set('active_offers_cache', active_offers, 300)
    
    # ========== USER WISHLIST ==========
    wishlist_product_ids = set(request.session.get("wishlist", []))
    
    # ========== PROCESS PRODUCTS ==========
    combined_products = []
    
    if giftsets_flag and cat_obj:
        # ========== GIFTSETS ==========
        giftsets_qs = GiftSet.objects.filter(
            product__category=cat_obj
        )
        
        # Apply price filters
        if min_price is not None:
            giftsets_qs = giftsets_qs.filter(price__gte=min_price)
        if max_price is not None:
            giftsets_qs = giftsets_qs.filter(price__lte=max_price)
        
        # Get distinct products
        product_ids = list(giftsets_qs.values_list('product_id', flat=True).distinct())
        
        if product_ids:
            # ========== GET ORIGINAL PRICE RANGES FOR GIFTSETS ==========
            # Convert original_price (CharField) to Float for min/max calculation
            from django.db.models import F, Value, CharField
            from django.db.models.functions import Cast, Coalesce, NullIf
            
            # Method 1: Using annotation with Cast (more accurate)
            try:
                price_range_data = GiftSet.objects.filter(
                    product_id__in=product_ids
                ).annotate(
                    # Convert original_price string to float, handle empty/None
                    original_float=Cast(
                        NullIf('original_price', Value('')),
                        FloatField()
                    )
                ).values('product_id').annotate(
                    min_price=Min('price'),
                    max_price=Max('price'),
                    min_original=Min('original_float'),
                    max_original=Max('original_float')
                )
            except:
                # Method 2: Simple approach - get all and calculate in Python
                all_giftsets = GiftSet.objects.filter(product_id__in=product_ids)
                price_range_dict = {}
                for gs in all_giftsets:
                    if gs.product_id not in price_range_dict:
                        price_range_dict[gs.product_id] = {
                            'min_price': float('inf'),
                            'max_price': float('-inf'),
                            'min_original': float('inf'),
                            'max_original': float('-inf')
                        }
                    
                    # Current price
                    current_price = float(gs.price) if gs.price else 0
                    price_range_dict[gs.product_id]['min_price'] = min(
                        price_range_dict[gs.product_id]['min_price'],
                        current_price
                    )
                    price_range_dict[gs.product_id]['max_price'] = max(
                        price_range_dict[gs.product_id]['max_price'],
                        current_price
                    )
                    
                    # Original price (from original_price CharField)
                    try:
                        original_val = float(gs.original_price) if gs.original_price else 0
                    except (ValueError, TypeError):
                        original_val = 0
                    
                    price_range_dict[gs.product_id]['min_original'] = min(
                        price_range_dict[gs.product_id]['min_original'],
                        original_val
                    )
                    price_range_dict[gs.product_id]['max_original'] = max(
                        price_range_dict[gs.product_id]['max_original'],
                        original_val
                    )
            
            # ========== GET REVIEWS ==========
            reviews = {}
            review_data = Review.objects.filter(
                product_id__in=product_ids
            ).values('product_id').annotate(
                avg_rating=Avg('rating'),
                review_count=Count('id')
            )
            
            for rd in review_data:
                reviews[rd['product_id']] = rd
            
            # ========== PROCESS GIFTSETS ==========
            # Get cheapest giftset for each product
            giftsets_by_product = {}
            for gs in giftsets_qs.order_by('product_id', 'price'):
                if gs.product_id not in giftsets_by_product:
                    giftsets_by_product[gs.product_id] = gs
            
            for product_id, gs in giftsets_by_product.items():
                # Apply offers
                base_price = float(gs.price) if gs.price else 0
                discounted_price = None
                offer_applied = None
                
                for offer in active_offers:
                    discounted = offer.apply_offer(gs)
                    if discounted:
                        discounted_price = float(discounted)
                        offer_applied = offer
                        break
                
                # ========== GET ORIGINAL PRICE RANGES ==========
                # Get product's original price from Product model
                product_original = float(gs.product.original_price) if gs.product.original_price else 0
                
                # Get min/max original from GiftSet table
                try:
                    # Get original price from this specific gift set
                    gs_original = float(gs.original_price) if gs.original_price else 0
                    
                    # Get price ranges from calculated dict or query
                    if 'price_range_dict' in locals():
                        price_info = price_range_dict.get(product_id, {
                            'min_price': base_price,
                            'max_price': base_price,
                            'min_original': gs_original,
                            'max_original': gs_original
                        })
                    else:
                        # Get from query result
                        pr_data = next((p for p in price_range_data if p['product_id'] == product_id), None)
                        price_info = {
                            'min_price': pr_data.get('min_price', base_price) if pr_data else base_price,
                            'max_price': pr_data.get('max_price', base_price) if pr_data else base_price,
                            'min_original': pr_data.get('min_original', gs_original) if pr_data else gs_original,
                            'max_original': pr_data.get('max_original', gs_original) if pr_data else gs_original
                        }
                except:
                    # Fallback if any calculation fails
                    price_info = {
                        'min_price': base_price,
                        'max_price': base_price,
                        'min_original': product_original,
                        'max_original': product_original
                    }
                
                # ========== GET REVIEW DATA ==========
                review_info = reviews.get(product_id, {'avg_rating': 0, 'review_count': 0})
                
                # ========== BUILD PRODUCT DATA ==========
                combined_products.append({
                    "id": product_id,
                    "name": gs.product.name,
                    "price": base_price,
                    "original_price": product_original,  # From Product model
                    "min_price": float(price_info.get('min_price', base_price)),
                    "max_price": float(price_info.get('max_price', base_price)),
                    "min_original_price": float(price_info.get('min_original', product_original)),
                    "max_original_price": float(price_info.get('max_original', product_original)),
                    "discounted_price": discounted_price,
                    "is_offer_active": bool(offer_applied),
                    "offer_code": offer_applied.code if offer_applied else None,
                    "offer_start_time": offer_applied.start_date if offer_applied else None,
                    "offer_end_time": offer_applied.end_date if offer_applied else None,
                    "flavours": list(gs.flavours.values_list("name", flat=True)),
                    "image": gs.product.image1.url if gs.product.image1 else "",
                    "image2": gs.product.image2.url if gs.product.image2 else "",
                    "is_active": getattr(gs.product, 'is_active', True),
                    "is_giftset": True,
                    "average_rating": float(review_info.get('avg_rating', 0)),
                    "review_count": review_info.get('review_count', 0),
                    "stock_status": getattr(gs.product, 'stock_status', 'In Stock'),
                    "is_favorite": product_id in wishlist_product_ids,
                    "is_best_seller": getattr(gs.product, 'is_best_seller', False),
                    "is_trending": getattr(gs.product, 'is_trending', False),
                    "is_new_arrival": getattr(gs.product, 'is_new_arrival', False),
                })
    
    else:
        # ========== REGULAR PRODUCTS ==========
        # Start with Product model and filter by category/subcategory
        products_qs = Product.objects.all()
        
        if subcat_obj:
            products_qs = products_qs.filter(subcategory=subcat_obj)

        elif cat_obj:
            products_qs = products_qs.filter(category=cat_obj)
        
        # Get product IDs
        product_ids = list(products_qs.values_list('id', flat=True))
        
        if product_ids:
            # Get variants for these products
            variants_qs = ProductVariant.objects.filter(
                product_id__in=product_ids
            )
            
            # Apply size filter
            if sizes:
                variants_qs = variants_qs.filter(size__in=sizes)
            
            # Apply price filters
            if min_price is not None:
                variants_qs = variants_qs.filter(price__gte=min_price)
            if max_price is not None:
                variants_qs = variants_qs.filter(price__lte=max_price)
            
            # Group by product to get cheapest variant
            # variants_by_product = {}
            # for var in variants_qs.order_by('product_id', 'price'):
            #     if var.product_id not in variants_by_product:
            #         variants_by_product[var.product_id] = var

            variants_by_product = {}
            for var in variants_qs:
                variants_by_product.setdefault(var.product_id, []).append(var)
            
            # Get filtered product IDs
            filtered_product_ids = list(variants_by_product.keys())
            
            # ========== GET ORIGINAL PRICE RANGES FOR VARIANTS ==========
            try:
                # Convert original_price (CharField) to Float for calculation
                price_range_data = ProductVariant.objects.filter(
                    product_id__in=filtered_product_ids
                ).annotate(
                    original_float=Cast(
                        NullIf('original_price', Value('')),
                        FloatField()
                    )
                ).values('product_id').annotate(
                    min_price=Min('price'),
                    max_price=Max('price'),
                    min_original=Min('original_float'),
                    max_original=Max('original_float')
                )
                
                price_ranges = {}
                for pd in price_range_data:
                    price_ranges[pd['product_id']] = {
                        'min_price': pd.get('min_price'),
                        'max_price': pd.get('max_price'),
                        'min_original': pd.get('min_original'),
                        'max_original': pd.get('max_original')
                    }
            except:
                # Fallback: manual calculation
                all_variants = ProductVariant.objects.filter(product_id__in=filtered_product_ids)
                price_ranges = {}
                for var in all_variants:
                    if var.product_id not in price_ranges:
                        price_ranges[var.product_id] = {
                            'min_price': float('inf'),
                            'max_price': float('-inf'),
                            'min_original': float('inf'),
                            'max_original': float('-inf')
                        }
                    
                    # Current price
                    current_price = float(var.price) if var.price else 0
                    price_ranges[var.product_id]['min_price'] = min(
                        price_ranges[var.product_id]['min_price'],
                        current_price
                    )
                    price_ranges[var.product_id]['max_price'] = max(
                        price_ranges[var.product_id]['max_price'],
                        current_price
                    )
                    
                    # Original price (from original_price CharField)
                    try:
                        original_val = float(var.original_price) if var.original_price else 0
                    except (ValueError, TypeError):
                        original_val = 0
                    
                    price_ranges[var.product_id]['min_original'] = min(
                        price_ranges[var.product_id]['min_original'],
                        original_val
                    )
                    price_ranges[var.product_id]['max_original'] = max(
                        price_ranges[var.product_id]['max_original'],
                        original_val
                    )
            
            # ========== GET REVIEWS ==========
            reviews = {}
            review_data = Review.objects.filter(
                product_id__in=filtered_product_ids
            ).values('product_id').annotate(
                avg_rating=Avg('rating'),
                review_count=Count('id')
            )
            
            for rd in review_data:
                reviews[rd['product_id']] = rd
            
            # ========== GET PRODUCTS DATA ==========
            products_dict = {p.id: p for p in products_qs.filter(id__in=filtered_product_ids)}
            
            # ========== PROCESS VARIANTS ==========
            for product_id, var_list in variants_by_product.items():
                product = products_dict.get(product_id)
                if not product:
                    continue
                
                
                # Apply offers
                # base_price = float(var.price) if var.price else 0
                best_variant = None
                discounted_price = None
                offer_applied = None
                cheapest_variant = min(var_list, key=lambda v: v.price if v.price else 999999)
                for var in var_list:
                
                    for offer in active_offers:
                        discounted = offer.apply_offer(var)
                        if discounted:
                            best_variant=var
                            discounted_price = float(discounted)
                            offer_applied = offer
                            break
                    if offer_applied:
                        break
                if not best_variant:
                    best_variant = cheapest_variant

                base_price = float(best_variant.price or 0)
                # ========== GET PRICE RANGES ==========
                # price_info = price_ranges.get(product_id, {})
                
                # Product's original price from Product model
                # product_original = float(product.original_price) if product.original_price else 0
                
                # Variant's original price
                try:
                    var_original = float(best_variant.original_price) if best_variant.original_price else float(product.original_price or 0)

                except (ValueError, TypeError):
                    var_original = float(product.original_price or 0)
                price_info = price_ranges.get(product_id, {})
                # ========== GET REVIEW DATA ==========
                review_info = reviews.get(product_id, {'avg_rating': 0, 'review_count': 0})
                
                # ========== BUILD PRODUCT DATA ==========
                combined_products.append({
                    "id": product_id,
                    "name": product.name,
                    "price": base_price,
                    "original_price": float(product.original_price or 0),  # From Product model
                    "min_price": float(price_info.get('min_price', base_price)),
                    "max_price": float(price_info.get('max_price', base_price)),
                    "min_original_price": float(price_info.get('min_original', var_original)),
                    "max_original_price": float(price_info.get('max_original', var_original)),
                    "discounted_price": discounted_price,
                    "is_offer_active": bool(offer_applied),
                    "offer_code": offer_applied.code if offer_applied else None,
                    "offer_start_time": offer_applied.start_date if offer_applied else None,
                    "offer_end_time": offer_applied.end_date if offer_applied else None,
                    "size": best_variant.size,
                    "stock": best_variant.stock,
                    "image": product.image1.url if product.image1 else "",
                    "image2": product.image2.url if product.image2 else "",
                    "is_active": getattr(product, 'is_active', True),
                    "is_giftset": False,
                    "average_rating": float(review_info.get('avg_rating', 0)),
                    "review_count": review_info.get('review_count', 0),
                    "stock_status": getattr(product, 'stock_status', 'In Stock'),
                    "is_favorite": product_id in wishlist_product_ids,
                    "is_best_seller": getattr(product, 'is_best_seller', False),
                    "is_trending": getattr(product, 'is_trending', False),
                    "is_new_arrival": getattr(product, 'is_new_arrival', False),
                })
    
    # ========== PAGINATION ==========
    paginator = Paginator(combined_products, 10)
    try:
        page_items = paginator.get_page(page)
    except:
        page = 1
        page_items = paginator.get_page(page)
    
    # ========== PREPARE RESPONSE ==========
    response_data = {
        "products": list(page_items),
        "category_name": category_name,
        "subcategory_name": subcategory_name,
        "category_banner_url": category_banner_url,
        "subcategory_banner_url": subcategory_banner_url,
        "current_page": page_items.number,
        "total_pages": paginator.num_pages,
        "has_next": page_items.has_next(),
        "next_page": page_items.next_page_number() if page_items.has_next() else None,
        "total_products": len(combined_products),
        "execution_time": round(time.time() - start_time, 3),
        "cache_hit": False,
    }
    
    # Cache the response
    cache.set(cache_key, response_data, 300)
    
    return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
def product_detail(request, product_id):
    guest_id=get_guest_id(request)
    product = get_object_or_404(Product, id=product_id)
    reviews = Review.objects.filter(product=product).order_by('-created_at')
    review_stats = reviews.aggregate(
    avg_rating=Avg('rating'),
    total_reviews=Count('id')
)
    average_rating = review_stats['avg_rating'] or 0
    total_reviews = review_stats['total_reviews'] or 0
    rating_percentage = round((average_rating / 5) * 100, 2)
    from_video = request.GET.get('from_video')
    all_variants = product.variants.all().order_by('bottle_type')
    in_cart = Cart.objects.filter(guest_id=guest_id, product=product).exists()
    cart_item = Cart.objects.filter(guest_id=guest_id, product=product).first()

    is_giftset = product.category.name.lower().replace(' ', '').replace('-', '') == 'giftsets'
    flavours = Flavour.objects.all()
    gift_sets = GiftSet.objects.filter(product=product).select_related('product').prefetch_related('flavours')

    offers = PremiumFestiveOffer.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
    enhanced_reviews = []
    for r in reviews:
        enhanced_reviews.append({
        'username': r.guest_id if r.guest_id else 'Anonymous',
        'rating': r.rating,
        'review_text': r.review_text,
        'bar_width': round((r.rating / 5) * 100, 2),
    })
    
    # Apply offers to GiftSets
    gift_set_data = []
    for giftset in gift_sets:
        originalprice = giftset.price
        # Stock=giftset.stock or 0
        realprice=giftset.original_price
        discounted_price = None
        applied_offer = None

        for offer in offers:
            discount = offer.apply_offer(giftset)
            if discount:
                discounted_price = discount
                applied_offer = offer
                break  # Only first matching offer

        gift_set_data.append({
            'id': giftset.id,
            'giftset': giftset,
            'price': originalprice,
            'original_price': realprice,
            'discounted_price': discounted_price,
            'offer': {
                'name': applied_offer.offer_name,
                'percentage': applied_offer.percentage,
            } if applied_offer else None,
        })

    

    # Prepare all variants with offer & stock
    variants = []
    seen_bottle_types = set()
    unique_bottle_variants = []

    for variant in all_variants:
        if variant.bottle_type not in seen_bottle_types:
            unique_bottle_variants.append(variant)
            seen_bottle_types.add(variant.bottle_type)

        originalprice = variant.price
        stock = variant.stock or 0
        realprice=variant.original_price
        discounted_price = None
        applied_offer = None

        for offer in offers:
            discount = offer.apply_offer(variant)
            if discount:
                discounted_price = discount
                applied_offer = offer
                break

        variants.append({
            'id': variant.id,
            'size': variant.size,
            'price': originalprice,
            'original_price': realprice,
            'discounted_price': discounted_price,
            'stock': variant.stock,
            'in_stock': stock > 0,
            'bottle_type': variant.bottle_type,
            'offer': {
                'name': applied_offer.offer_name,
                'percentage': applied_offer.percentage,
            } if applied_offer else None
        })

    # Use first variant with discount to show on product header
    first_variant_with_offer = next((v for v in variants if v['discounted_price']), None)
    if first_variant_with_offer:
        product.discounted_price = first_variant_with_offer['discounted_price']
        product.originalprice = first_variant_with_offer['price']
        product.offer = first_variant_with_offer['offer']
    else:
        product.original_price = product.original_price
        print(product.original_price,"prrrrrrrr")
        product.offer = None

    # Related Products
   
    if product.subcategory:
        related_products = Product.objects.filter(
        subcategory=product.subcategory
    ).exclude(id=product.id)
    else:
        related_products = Product.objects.filter(
        category=product.category
    ).exclude(id=product.id)



    related_products_with_price = []
    for p in related_products:
        variant_prices = p.variants.aggregate(
        min_variant_price=Min('price'),
        max_variant_price=Max('price'),
        min_original_price=Min('original_price'),
        max_original_price=Max('original_price')
        )
            # Get min/max price from giftsets
        giftset_prices = p.gift_sets.aggregate(
        min_gift_price=Min('price'),
        max_gift_price=Max('price'),
        min_original_price=Min('original_price'),
        max_original_price=Max('original_price')
        ) 
        # Combine all prices
        all_prices = [price for price in [
        variant_prices['min_variant_price'],
        variant_prices['max_variant_price'],
        giftset_prices['min_gift_price'],
        giftset_prices['max_gift_price'],
    ] if price is not None]
        
        if all_prices:
            min_price = min(all_prices)
            max_price = max(all_prices)
            if min_price == max_price:
              price_display = f"₹{min_price}"
            else:
              price_display = f"₹{min_price} - ₹{max_price}"
        else:
            price_display = "Price not available"

        all_original_prices = [
        variant_prices['min_original_price'],
        variant_prices['max_original_price'],
        giftset_prices['min_original_price'],
        giftset_prices['max_original_price'],
    ]
        all_original_prices = [x for x in all_original_prices if x is not None]
        if all_original_prices:
            min_original_price = min(all_original_prices)
            max_original_price = max(all_original_prices)
           
        else:
            min_original_price = None
            max_original_price = None
        related_products_with_price.append({
        'product': p,
        'price_display': price_display,
        'min_original_price': min_original_price,
        'max_original_price': max_original_price,
    })
    # Best Selling Products
    

   

    return render(request, 'user_panel/product_detail.html', {
        'product': product,
        'in_cart': in_cart,
        'variants': variants,
        'cart_item': cart_item,
        'unique_bottle_variants': unique_bottle_variants,
        'related_products': related_products_with_price,
        'flavours': flavours,
        'gift_sets': gift_set_data,
        'is_giftset': is_giftset,
        'from_video':from_video,
        'reviews':reviews,
        'average_rating': average_rating,
        'rating_percentage':rating_percentage,
        'reviews': enhanced_reviews,
        'total_reviews':total_reviews


        
    })


@require_POST
def add_to_cart(request, product_id):
    guest_id = get_guest_id(request)
    product = get_object_or_404(Product, id=product_id)
   
    try:
        quantity = int(request.POST.get("quantity", 1))
        variant_id = request.POST.get("variant_id")
        gift_set_id = request.POST.get("gift_set_id")
        selected_price = request.POST.get("selected_price")
        selected_flavours = request.POST.get("selected_flavours", "")

        if quantity < 1:
            raise ValueError("Quantity must be at least 1")

        if not variant_id and not gift_set_id:
            raise ValueError("Please select a variant or gift set")

        # 🔥 USE SELECTED PRICE (offer price)
        price = Decimal(selected_price)

        cart_filter = {
            "guest_id": guest_id,
            "product": product,
            "product_variant_id": variant_id or None,
            "gift_set_id": gift_set_id or None,
            "selected_flavours": selected_flavours or ""
        }

        cart_item = Cart.objects.filter(**cart_filter).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.price = price   # 🔥 DO NOT reset to base price
            cart_item.save()
        else:
            Cart.objects.create(
                guest_id=guest_id,
                product=product,
                product_variant_id=variant_id or None,
                gift_set_id=gift_set_id or None,
                quantity=quantity,
                price=price,
                selected_flavours=selected_flavours or ""
            )

        # ✅ DO NOT BUILD CART HERE
        # ✅ ALWAYS RETURN SYNC RESPONSE
        return sync_redis_cart(request)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=400)

import traceback

@require_POST
def update_cart_item(request, item_id):
    guest_id = get_guest_id(request)
    try:
        # 1️⃣ Fetch cart item
        cart_item = get_object_or_404(
            Cart, id=item_id, guest_id=guest_id
        )

        # 2️⃣ Update quantity
        action = request.POST.get("action")
        if action == "increase":
            cart_item.quantity += 1
        elif action == "decrease" and cart_item.quantity > 1:
            cart_item.quantity -= 1

        cart_item.save()

        # 3️⃣ Recalculate EVERYTHING using single source of truth
        totals = calculate_cart_totals(request)

        # 4️⃣ Total items count
        total_items = Cart.objects.filter(
            guest_id=guest_id
        ).aggregate(total=Sum("quantity"))["total"] or 0

        # 5️⃣ Return clean response (frontend will sync cart)
        return JsonResponse({
            "status": "success",
            "new_quantity": cart_item.quantity,
            "cart_count": total_items,

            # 🔥 Use server-calculated prices ONLY
            "prices": {
                "subtotal": float(totals["products_total"]),
                "delivery": float(totals["delivery"]),
                "platform_fee": float(totals["platform_fee"]),
                "gift_wrap": float(totals["gift_wrap"]),
                "premium_discount": float(totals["premium_discount"]),
                "total_price": float(totals["final_total"]),
            }
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }, status=400)


def calculate_cart_totals(request):
    guest_id = get_guest_id(request)
    cart_items = Cart.objects.filter(guest_id=guest_id)
    now = timezone.now()

    festival_offers = list(
        PremiumFestiveOffer.objects.filter(
            is_active=True,
            premium_festival="Festival",
            start_date__lte=now,
            end_date__gte=now
        )
    )

    products_total = Decimal('0.00')
    festival_pct = request.session.get("premium_offer_percentage", 0)
    festival_active = bool(festival_pct)

    for item in cart_items:
        price = Decimal('0.00')

        if item.gift_set:
            base_price = Decimal(item.price or 0)
            valid = [o for o in festival_offers if o.apply_offer(item.gift_set)]
            if valid:
                best = max(valid, key=lambda o: o.percentage)
                price = base_price - (base_price * best.percentage / Decimal('100'))
            else:
                price = base_price

        elif item.product_variant:
            base_price = Decimal(item.product_variant.price)
            valid = [o for o in festival_offers if o.apply_offer(item.product_variant)]
            if valid:
                best = max(valid, key=lambda o: o.percentage)
                price = base_price - (base_price * best.percentage / Decimal('100'))
            else:
                price = base_price

        else:
            price = Decimal(item.product.price)

        products_total += price * item.quantity

    delivery = max(
        (Decimal(item.product.delivery_charges or 0) for item in cart_items),
        default=Decimal('0.00')
    )

    platform_fee = max(
        (Decimal(item.product.platform_fee or 0) for item in cart_items),
        default=Decimal('0.00')
    )

    gift_wrap = Decimal('150.00') if request.session.get('gift_wrap') else Decimal('0.00')

    coupon_discount = Decimal('0.00')
    applied_code = request.session.get("applied_coupon")
    if applied_code:
        try:
            coupon = Coupon.objects.get(code=applied_code, is_active=True)
            if products_total < coupon.required_amount:
                request.session.pop("applied_coupon", None)
                request.session.pop("applied_coupon_discount", None)
            else:
                coupon_discount = Decimal(
                    request.session.get("applied_coupon_discount", 0)
                )
        except Coupon.DoesNotExist:
            request.session.pop("applied_coupon", None)
            request.session.pop("applied_coupon_discount", None)


    # coupon_discount = Decimal(request.session.get('applied_coupon_discount', 0))

    # ✅ PREMIUM DISCOUNT (TOTAL LEVEL)
    premium_discount = Decimal('0.00')
    pct = request.session.get('premium_offer_percentage')
    if pct:
        premium_discount = (products_total * Decimal(pct)) / Decimal('100')

    final_total = (
        products_total
        + delivery
        + platform_fee
        + gift_wrap
        - coupon_discount
        - premium_discount
    )

    final_total = max(final_total, Decimal('0.00'))

    total_items = cart_items.aggregate(total=Sum('quantity'))['total'] or 0

    return {
        "products_total": products_total,
        "delivery": delivery,
        "platform_fee": platform_fee,
        "gift_wrap": gift_wrap,
        "coupon_discount": coupon_discount,
        "premium_discount": premium_discount,
        "final_total": final_total,
        "cart_count": total_items,
        "festival": {
        "active": festival_active,
        "percentage": festival_pct,
        "label": "Festival Offer"
    }
    }


@require_POST
def sync_redis_cart(request):
    guest_id = get_guest_id(request)

    try:
        # 1️⃣ Totals
        totals = calculate_cart_totals(request)
        subtotal = totals["products_total"]

        # 2️⃣ Time
        now = timezone.now()

        # 3️⃣ Festival offers
        festival_offers = list(
            PremiumFestiveOffer.objects.filter(
                is_active=True,
                premium_festival="Festival",
                start_date__lte=now,
                end_date__gte=now
            )
        )

        # 4️⃣ Cart items (GUEST)
        cart_items = Cart.objects.filter(
            guest_id=guest_id
        ).select_related("product", "product_variant", "gift_set")

        items = []
        quantities = {}

        for item in cart_items:

            # ---------- ORIGINAL PRICE ----------
            if item.gift_set:
                original_price = Decimal(item.gift_set.price)
                valid = [o for o in festival_offers if o.apply_offer(item.gift_set)]

            elif item.product_variant:
                original_price = Decimal(item.product_variant.price)
                valid = [o for o in festival_offers if o.apply_offer(item.product_variant)]

            else:
                original_price = Decimal(item.product.price)
                valid = []

            # ---------- FINAL PRICE ----------
            if valid:
                best = max(valid, key=lambda o: o.percentage)
                final_price = original_price - (
                    original_price * best.percentage / Decimal("100")
                )
                festival_active = True
                festival_percentage = best.percentage
            else:
                final_price = original_price
                festival_active = False
                festival_percentage = 0

            items.append({
                "id": item.id,
                "name": item.product.name,
                "quantity": item.quantity,
                "original_price": float(original_price),
                "final_price": float(final_price),
                "festival_active": festival_active,
                "festival_percentage": festival_percentage,
                "image": item.product.image1.url if item.product.image1 else ""
            })

            quantities[str(item.id)] = item.quantity

        # 5️⃣ Eligible coupons (GUEST)
        eligible_coupons = Coupon.objects.filter(
            is_active=True,
            required_amount__lte=subtotal
        )

        used_coupon_ids = CouponUsage.objects.filter(
            guest_id=guest_id
        ).values_list("coupon_id", flat=True)

        eligible_coupons = eligible_coupons.exclude(id__in=used_coupon_ids)

        # 6️⃣ Response
        return JsonResponse({
            "status": "success",
            "cart_items": items,
            "order_summary": {
                "subtotal": float(totals["products_total"]),
                "delivery": float(totals["delivery"]),
                "platform_fee": float(totals["platform_fee"]),
                "gift_wrap": float(totals["gift_wrap"]),
                "premium_discount": float(totals["premium_discount"]),
                "discount": float(totals["coupon_discount"]),
                "total": float(totals["final_total"]),
            },
            "cart_count": totals["cart_count"],
            "quantities": quantities,
            "applied_coupon": request.session.get("applied_coupon"),
            "eligible_coupons": list(
                eligible_coupons.values_list("code", flat=True)
            )
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=400)



logger = logging.getLogger(__name__)
@require_POST
def remove_cart_item(request, item_id):
    guest_id = get_guest_id(request)

    try:
        # 1️⃣ Fetch cart item (guest-only)
        cart_item = get_object_or_404(
            Cart, id=item_id, guest_id=guest_id
        )

        # 2️⃣ Delete item
        cart_item.delete()

        # 3️⃣ Recalculate cart totals (DB = source of truth)
        totals = calculate_cart_totals(request)

        # 4️⃣ Total cart count
        cart_count = Cart.objects.filter(
            guest_id=guest_id
        ).aggregate(total=Sum("quantity"))["total"] or 0

        return JsonResponse({
            "status": "success",
            "message": "Item removed successfully",
            "cart_count": cart_count,
            "is_empty": cart_count == 0,
            "prices": {
                "subtotal": float(totals["products_total"]),
                "delivery": float(totals["delivery"]),
                "platform_fee": float(totals["platform_fee"]),
                "gift_wrap": float(totals["gift_wrap"]),
                "premium_discount": float(totals["premium_discount"]),
                "discount": float(totals["coupon_discount"]),
                "total": float(totals["final_total"]),
            }
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc(),
            "cart_count": 0,
            "is_empty": True
        }, status=400)


@require_GET
def cart_count(request):
    guest_id = get_guest_id(request)

    try:
        total_items = Cart.objects.filter(
            guest_id=guest_id
        ).aggregate(total=Sum("quantity"))["total"] or 0

        return JsonResponse({
            "count": total_items,
            "status": "success",
            "source": "database"
        })

    except Exception as e:
        return JsonResponse({
            "count": 0,
            "status": "error",
            "message": str(e)
        }, status=400)



@require_POST
def apply_coupon(request):
    guest_id=get_guest_id(request)
    code = request.POST.get('code', '').strip()

    try:
        coupon = Coupon.objects.get(code=code, is_active=True)

        # ❌ Already used
        if CouponUsage.objects.filter(guest_id=guest_id, coupon=coupon).exists():
            return JsonResponse({
                "status": "error",
                "message": "Coupon already used"
            })

        # ✅ Check minimum cart value
        totals_before = calculate_cart_totals(request)
        if totals_before["final_total"] < coupon.required_amount:
            return JsonResponse({
                "status": "error",
                "message": f"Shop above ₹{coupon.required_amount} to use this coupon"
            })

        # ❌ REMOVE premium/welcome if exists
        request.session.pop('premium_offer_code', None)
        request.session.pop('premium_offer_percentage', None)
        request.session.pop('premium_offer_type', None)

        # ✅ Apply coupon
        request.session['applied_coupon'] = coupon.code
        request.session['applied_coupon_discount'] = float(coupon.discount)

        totals = calculate_cart_totals(request)

        return JsonResponse({
            "status": "success",
            "message": f"You saved ₹{coupon.discount}!",
            "totals": {
                "products_total": float(totals["products_total"]),
                "delivery": float(totals["delivery"]),
                "platform_fee": float(totals["platform_fee"]),
                "gift_wrap": float(totals["gift_wrap"]),
                "coupon_discount": float(totals["coupon_discount"]),
                "premium_discount": float(totals["premium_discount"]),
                "final_total": float(totals["final_total"]),
            }
        })

    except Coupon.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Invalid coupon"
        })
@require_POST
def remove_coupon(request):
    request.session.pop('applied_coupon', None)
    request.session.pop('applied_coupon_discount', None)

    totals = calculate_cart_totals(request)

    return JsonResponse({
        "status": "success",
        "message": "Coupon removed",
        "totals": {
            "products_total": float(totals["products_total"]),
            "delivery": float(totals["delivery"]),
            "platform_fee": float(totals["platform_fee"]),
            "gift_wrap": float(totals["gift_wrap"]),
            "coupon_discount": float(totals["coupon_discount"]),
            "premium_discount": float(totals["premium_discount"]),
            "final_total": float(totals["final_total"]),
        }
    })



def apply_premium_offer(request):
    guest_id=get_guest_id(request)
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': "Invalid request."})

    code_entered = request.POST.get('code', '').strip().upper()

    try:
        offer = PremiumFestiveOffer.objects.get(
            code__iexact=code_entered,
            is_active=True,
            premium_festival__in=["Premium", "Welcome"]
        )

        if PremiumOfferUsage.objects.filter(
            guest_id=guest_id,
            offer_code=offer.code
        ).exists():
            return JsonResponse({'status': 'error', 'message': "Offer already used."})

        # save session
        request.session['premium_offer_code'] = offer.code
        request.session['premium_offer_percentage'] = float(offer.percentage)

        PremiumOfferUsage.objects.create(
            guest_id=guest_id,
            offer_code=offer.code
        )

        totals = calculate_cart_totals(request)

        return JsonResponse({
            'status': 'success',
            'message': f"{offer.percentage}% discount applied!",
            'totals': {
                'subtotal': float(totals['products_total']),
                'delivery': float(totals['delivery']),
                'platform_fee': float(totals['platform_fee']),
                'gift_wrap': float(totals['gift_wrap']),
                'discount': float(totals['coupon_discount']),
                'premium_discount': float(totals['premium_discount']),
                'total': float(totals['final_total']),
            }
        })

    except PremiumFestiveOffer.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': "Invalid premium / welcome code."
        })


def remove_premium_offer(request):
    guest_id=get_guest_id(request)
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': "Invalid request."})

    code = request.session.get('premium_offer_code')

    if not code:
        return JsonResponse({'status': 'error', 'message': "No premium offer applied."})

    PremiumOfferUsage.objects.filter(guest_id=guest_id, offer_code=code).delete()

    request.session.pop('premium_offer_code', None)
    request.session.pop('premium_offer_percentage', None)

    totals = calculate_cart_totals(request)

    return JsonResponse({
        'status': 'success',
        'message': "Premium offer removed.",
        'totals': {
            'subtotal': float(totals['products_total']),
            'delivery': float(totals['delivery']),
            'platform_fee': float(totals['platform_fee']),
            'gift_wrap': float(totals['gift_wrap']),
            'discount': float(totals['coupon_discount']),
            'premium_discount': float(totals['premium_discount']),
            'total': float(totals['final_total']),
        }
    })




from django.views.decorators.http import require_POST
from admin_panel.utils import create_shiprocket_order
@require_POST
def toggle_gift_wrap(request):
    guest_id=get_guest_id(request)
    gift_wrap_status = request.session.get('gift_wrap', False)
    new_status = not gift_wrap_status

    # Update session
    request.session['gift_wrap'] = new_status
    request.session.modified = True

    # Update all cart items for the logged-in user
    Cart.objects.filter(guest_id=guest_id).update(gift_wrap=new_status)

    return redirect(request.META.get('HTTP_REFERER', '/'))


import hashlib
import razorpay
def view_cart(request):
    guest_id=get_guest_id(request)
    from_video = request.GET.get('from_video')

    all_messages = messages.get_messages(request)
    error_messages = []
    success_messages = []
    applied_successfully = False
    premium_offer_removed = False

    cart_items = Cart.objects.filter(guest_id=guest_id).order_by('-created_at')
    selected_address_id = request.session.get('selected_address_id')
  
    address = None
    if selected_address_id:
        address = AddressModel.objects.filter(id=selected_address_id, guest_id=guest_id).first()
        print("address",address)
    else:
        address = AddressModel.objects.filter(guest_id=guest_id).last()
        if not address:
            request.session.pop('selected_address_id', None)
            address = AddressModel.objects.filter(
                guest_id=guest_id
            ).order_by('-id').first()
        else:
            address = AddressModel.objects.filter(
            guest_id=guest_id
        ).order_by('-id').first()
        print("address", address)


    if not cart_items.exists():
        pass
        return render(request, 'user_panel/cart.html', {
            'cart_items': [], 'total_price': 0, 'total_items': 0,
        })

    total_price = Decimal('0.00')
    total_items = 0
    delivery_charges = Decimal('0.00')
    platform_fee = Decimal('0.00')
    gift_wrap_display = Decimal('0.00')
    now = timezone.now()
    active_offers = list(
    PremiumFestiveOffer.objects.filter(
        is_active=True,
        premium_festival="Festival",
        start_date__lte=now,
        end_date__gte=now
    )
)

    for cart_item in cart_items:
        if cart_item.selected_flavours:
            flavour_ids = [int(fid) for fid in cart_item.selected_flavours.split(',') if fid.isdigit()]
            flavour_names = Flavour.objects.filter(id__in=flavour_ids).values_list('name', flat=True)
            cart_item.flavour_names = ', '.join(flavour_names)
        else:
            cart_item.flavour_names = ''
        product = cart_item.product
        average_rating = product.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        review_count = product.reviews.count()
        rating_percentage = (average_rating / 5) * 100  # For star fill width

    # Attach to cart_item for use in template
        cart_item.average_rating = round(average_rating, 1)
        cart_item.review_count = review_count
        cart_item.rating_percentage = rating_percentage
        variant = cart_item.product_variant
        gift_set = cart_item.gift_set if cart_item.gift_set else None
        selling_price = Decimal('0.00')
        discounted_price = None
        offer_applied = None

        if gift_set:
            selling_price = cart_item.price if cart_item.price else Decimal('0.00')
            valid_offers = [offer for offer in active_offers if offer.apply_offer(gift_set)]
            if valid_offers:
                best_offer = max(valid_offers, key=lambda x: x.percentage)
                discounted_price = selling_price - ( (selling_price * best_offer.percentage) / Decimal('100'))
                offer_applied = best_offer
        elif variant:
            selling_price = variant.price
            valid_offers = [offer for offer in active_offers if offer.apply_offer(variant)]
            if valid_offers:
                best_offer = max(valid_offers, key=lambda x: x.percentage)
                discounted_price = selling_price - ((selling_price * best_offer.percentage) / Decimal('100'))
                offer_applied = best_offer

        else:
            selling_price = product.price

        quantity = cart_item.quantity
        final_price = discounted_price if discounted_price is not None else selling_price
        total_items += quantity
        item_total = final_price * quantity
        total_price += item_total

        cart_item.final_price = final_price
        cart_item.original_price = selling_price
        cart_item.discounted_price = discounted_price
        cart_item.offer_applied = offer_applied

    if request.session.get('gift_wrap', False):
        gift_wrap_display = Decimal('150.00')
    cart_total=total_price
    delivery_charges = max([
    (item.product.delivery_charges or Decimal('0.00'))
    for item in cart_items
])

    platform_fee = max([
    (item.product.platform_fee or Decimal('0.00'))
    for item in cart_items
])
    current_cart_total = total_price + delivery_charges + platform_fee  

    # Coupon
    applied_coupon_code = request.session.get('applied_coupon')
    discount = Decimal('0.00')
    applied_coupon = None
    all_coupons = Coupon.objects.filter(is_active=True)
    used_coupons = CouponUsage.objects.filter(guest_id=guest_id).values_list('coupon__id', flat=True)
    eligible_coupons = [
        coupon for coupon in all_coupons
        if coupon.required_amount <= current_cart_total and coupon.id not in used_coupons
    ]

    if applied_coupon_code:
        try:
            coupon_obj = Coupon.objects.get(code=applied_coupon_code, is_active=True)
            applied_coupon = coupon_obj
            discount = applied_coupon.discount if applied_coupon.discount else Decimal('0.00')
        except Coupon.DoesNotExist:
            request.session.pop('applied_coupon', None)

    base_amount = current_cart_total + gift_wrap_display - discount
    print("Total price after coupon:", total_price)

    # Premium offer
    premium_discount = Decimal('0.00')
    premium_offer_visible = False
    welcome_offer_visible = False

    premium_offer_code = request.session.get('premium_offer_code')
    premium_offer_percentage = request.session.get('premium_offer_percentage')

    premium_base_amount = current_cart_total + gift_wrap_display - discount
    welcome_offer = (
    PremiumFestiveOffer.objects
    .filter(is_active=True, premium_festival="Welcome")
    .exclude(
        code__in=PremiumOfferUsage.objects
        .filter(guest_id=guest_id)
        .values_list("offer_code", flat=True)
    )
    .first()
)

    if premium_offer_code and premium_offer_percentage:
        try:
            offer = PremiumFestiveOffer.objects.filter(
            code=premium_offer_code,
            is_active=True,
            premium_festival__in=["Premium", "Welcome"]
        ).first()

            if offer:
                premium_offer_percentage = Decimal(premium_offer_percentage)
                premium_discount = (
                    premium_base_amount * premium_offer_percentage
                ) / Decimal('100')
            # ✅ SINGLE SOURCE OF TRUTH
                premium_offer_visible = True

                if offer.premium_festival == "Welcome":
                    welcome_offer_visible = True

        except Exception:
           pass


    total_price = base_amount - premium_discount
    total_price = max(total_price, Decimal('0.00'))
    print("Total price after premium discount:", total_price)
    # Razorpay
    cart_hash_data = f"{guest_id}_{total_items}_{float(total_price)}"
    cart_hash = hashlib.md5(cart_hash_data.encode()).hexdigest()
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))

    if request.session.get('razorpay_cart_hash') == cart_hash:
        razorpay_order_id = request.session.get('razorpay_order_id')
    else:
        razorpay_order = client.order.create({
            "amount": int(total_price * 100),
            "currency": "INR",
            "payment_capture": 1
        })
        razorpay_order_id = razorpay_order['id']
        request.session['razorpay_order_id'] = razorpay_order_id
        request.session['razorpay_cart_hash'] = cart_hash

    # Festival offers
    applicable_offers = []
    for offer in active_offers:
        if total_price >= getattr(offer, 'min_required', Decimal('0.00')) and offer.premium_festival == 'Welcome':
            discounted_price = (total_price * offer.percentage) / Decimal('100')
            applicable_offers.append({
                'name': offer.offer_name,
                'code': getattr(offer, 'code', ''),
                'percentage': offer.percentage,
                'discounted_price': discounted_price,
                'premium_festival': offer.premium_festival,
            })

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'total_items': total_items,
        'address': address,
        'amount': cart_total,
        'delivery_charges': delivery_charges,
        'platform_fee': platform_fee,
        'discount': discount,
        'gift_wrap_display': gift_wrap_display,
        'eligible_coupons': eligible_coupons,
        'all_coupons': all_coupons,
        'used_coupons': used_coupons,
        'applied_coupon': applied_coupon,
        'razorpay_order_id': razorpay_order_id,
        'key_id': settings.RAZORPAY_KEY_ID,
        'amount_in_paise': int(total_price * 100),
        'premium_offer_code': premium_offer_code,
        'premium_discount': premium_discount,
        'error_messages': error_messages,
        'success_messages': success_messages,
        'applied_successfully': applied_successfully,
        'applicable_offers': applicable_offers,
        'premium_offer_removed': premium_offer_removed,
        'premium_offer_visible': premium_offer_visible,
        'from_video': from_video,
        'rating_percentage': rating_percentage,
        'average_rating': average_rating,
        "welcome_offer_visible": welcome_offer_visible,
        "welcome_offer": welcome_offer,

    }
    # Save applied coupon discount into session for later use
    request.session['applied_coupon_discount'] = float(discount)

    return render(request, 'user_panel/cart.html', context)

# @csrf_exempt
# def order_success(request):
#     guest_id = get_guest_id(request)
#     if request.method == "POST":
        
#         total_price = float(request.POST.get("total_price", 0))
#         razorpay_payment_id = request.POST.get("razorpay_payment_id")
#         razorpay_order_id = request.POST.get("razorpay_order_id")
#         razorpay_signature = request.POST.get("razorpay_signature")
#         selected_address_id = request.session.get("selected_address_id")

#         # ✅ Fetch address
#         address = AddressModel.objects.filter(
#             id=selected_address_id, guest_id=guest_id
#         ).first() if selected_address_id else AddressModel.objects.filter(guest_id=guest_id).last()

#         # ✅ Prevent duplicate orders (same user + same price in last 5 mins)
#         existing_order = Order.objects.filter(
#             guest_id=guest_id,
#             total_price=total_price,
#             status="Completed",
#             created_at__gte=timezone.now() - timedelta(minutes=5),
#         ).first()

#         if existing_order:
#             order = existing_order
#             print("⚠️ Using existing order to prevent duplicate:", order.id)
#         else:
#             try:
#                 # ✅ Verify Razorpay signature
#                 client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))
#                 client.utility.verify_payment_signature({
#                     "razorpay_order_id": razorpay_order_id,
#                     "razorpay_payment_id": razorpay_payment_id,
#                     "razorpay_signature": razorpay_signature,
#                 })

#                 with transaction.atomic():
#                     # ✅ Create order
#                     order = Order.objects.create(
#                         guest_id=guest_id,
#                         address=address,
#                         total_price=total_price,
#                         status="Completed",
#                     )

#                     Payment.objects.create(
#                         order=order,
#                         payment_method="Razorpay",
#                         status="Completed",
#                         transaction_id=razorpay_payment_id,
#                         price=total_price,
#                     )

#                     # ✅ Move cart → order items
#                     cart_items = Cart.objects.filter(guest_id=guest_id)
#                     cart_total_before_discount = sum(item.price * item.quantity for item in cart_items)

#                     coupon_discount = Decimal(request.session.get("applied_coupon_discount", 0.00))
#                     premium_discount_percentage = Decimal(request.session.get("premium_offer_percentage", 0.00))

#                     for item in cart_items:
#                         quantity = item.quantity
#                         original_total = item.price * quantity
#                         discounted_total = item.price * quantity if item.price else original_total

#                         # Discounts
#                         product_offer_discount = original_total - discounted_total
#                         coupon_ratio = (original_total / cart_total_before_discount) if cart_total_before_discount > 0 else Decimal("0.00")
#                         coupon_discount_amount = coupon_discount * coupon_ratio
#                         premium_discount_amount = (discounted_total * premium_discount_percentage) / Decimal("100") if premium_discount_percentage > 0 else Decimal("0.00")

#                         total_discount = product_offer_discount + coupon_discount_amount + premium_discount_amount

#                         OrderItem.objects.create(
#                             order=order,
#                             product=item.product,
#                             product_variant=item.product_variant,
#                             quantity=quantity,
#                             price=item.price,
#                             gift_wrap=item.gift_wrap,
#                             gift_set=item.gift_set,
#                             offer_code=item.offer_code,
#                             discount_amount=total_discount.quantize(Decimal("0.01")),
#                             discount_percentage=item.discount_percentage,
#                             selected_flavours=item.selected_flavours if item.selected_flavours else None,
#                         )

#                         # ✅ Decrease stock
#                         if item.product_variant:
#                             item.product_variant.stock = max(item.product_variant.stock - item.quantity, 0)
#                             item.product_variant.save()
#                         elif item.gift_set:
#                             item.gift_set.stock = max(item.gift_set.stock - item.quantity, 0)
#                             item.gift_set.save()
#                         elif item.product:
#                             item.product.stock = max(item.product.stock - item.quantity, 0)
#                             item.product.save()

#                     cart_items.delete()

#                     # ✅ Fire Celery tasks *after commit*
#                     transaction.on_commit(lambda: create_shiprocket_order_task.delay(order.id))
#                     transaction.on_commit(lambda: send_invoice_email_task.delay(order.id))
#                     transaction.on_commit(lambda: notify_low_stock_task.delay(order.id))

#             except razorpay.errors.SignatureVerificationError:
#                 return render(request, "user_panel/payment_failed.html", {"error": "Signature verification failed"})

#         # ✅ Handle coupon usage
#         coupon_code = request.session.pop("applied_coupon", None)
#         if coupon_code:
#             try:
#                 coupon = Coupon.objects.get(code=coupon_code)
#                 CouponUsage.objects.create(guest_id=guest_id, coupon=coupon)
#             except Coupon.DoesNotExist:
#                 pass

#         # ✅ Handle premium offer usage
#         premium_offer_code = request.session.pop("premium_offer_code", None)
#         if premium_offer_code:
#             offer = PremiumFestiveOffer.objects.filter(code=premium_offer_code).first()
#             if offer:
#                 PremiumOfferUsage.objects.create(guest_id=guest_id, offer_code=offer.code)
#             request.session.pop("premium_offer_percentage", None)
#             request.session.pop(f"premium_offer_used_{premium_offer_code}", None)

#         # ✅ Clear unused session keys
#         for key in ["gift_wrap", "razorpay_order_id", "razorpay_cart_hash"]:
#             request.session.pop(key, None)

#         messages.success(request, "🎉 Your order has been placed successfully!")

#         return render(request, "user_panel/order_success.html", {"order": order})

#     return redirect("view_cart")

def generate_cart_hash(cart_items):
    """
    Generate a unique hash for the current cart items to detect duplicates.
    """
    cart_list = [
        {
            "product_id": str(item.product.id if item.product else ""),
            "variant_id": str(item.product_variant.id if item.product_variant else ""),
            "gift_set_id": str(item.gift_set.id if item.gift_set else ""),
            "quantity": item.quantity
        }
        for item in cart_items
    ]
    cart_json = json.dumps(cart_list, sort_keys=True)
    return hashlib.sha256(cart_json.encode()).hexdigest()


@csrf_exempt
def order_success(request):
    guest_id = get_guest_id(request)

    if request.method != "POST":
        return redirect("view_cart")

    # Fetch POST data
    total_price = float(request.POST.get("total_price", 0))
    razorpay_payment_id = request.POST.get("razorpay_payment_id")
    razorpay_order_id = request.POST.get("razorpay_order_id")
    razorpay_signature = request.POST.get("razorpay_signature")
    selected_address_id = request.session.get("selected_address_id")

    # Fetch address
    address = None
    if selected_address_id:
        address = AddressModel.objects.filter(id=selected_address_id, guest_id=guest_id).first()
    if not address:
        address = AddressModel.objects.filter(guest_id=guest_id).last()

    # ✅ Fetch cart items
    cart_items = Cart.objects.filter(guest_id=guest_id)
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("view_cart")

    # Generate cart hash
    cart_hash = generate_cart_hash(cart_items)

    # ✅ Prevent duplicate payment by Razorpay payment ID
    existing_payment = Payment.objects.filter(transaction_id=razorpay_payment_id).select_related('order').first()
    if existing_payment:
        order = existing_payment.order
        messages.info(request, "⚠️ Payment already processed. Showing existing order.")
        return render(request, "user_panel/order_success.html", {"order": order})

    # ✅ Prevent duplicate order for same guest + same cart hash in last 5 mins
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    recent_order = Order.objects.filter(
        guest_id=guest_id,
        cart_hash=cart_hash,
        created_at__gte=five_minutes_ago
    ).order_by('-created_at').first()
    if recent_order:
        messages.info(request, "⚠️ You already placed this order recently.")
        return render(request, "user_panel/order_success.html", {"order": recent_order})

    # Verify Razorpay signature
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        return render(request, "user_panel/payment_failed.html", {"error": "Signature verification failed"})

    # ✅ Create order transactionally
    with transaction.atomic():
        order = Order.objects.create(
            guest_id=guest_id,
            address=address,
            total_price=total_price,
            status="Pending",
            cart_hash=cart_hash  # store cart hash to detect duplicates
        )

        Payment.objects.create(
            order=order,
            payment_method="Razorpay",
            status="Completed",
            transaction_id=razorpay_payment_id,
            price=total_price,
        )

        cart_total_before_discount = sum(item.price * item.quantity for item in cart_items)
        coupon_discount = Decimal(request.session.get("applied_coupon_discount", 0.00))
        premium_discount_percentage = Decimal(request.session.get("premium_offer_percentage", 0.00))

        for item in cart_items:
            quantity = item.quantity
            original_total = item.price * quantity
            discounted_total = original_total

            # Discounts
            product_offer_discount = original_total - discounted_total
            coupon_ratio = (original_total / cart_total_before_discount) if cart_total_before_discount > 0 else Decimal("0.00")
            coupon_discount_amount = coupon_discount * coupon_ratio
            premium_discount_amount = (discounted_total * premium_discount_percentage) / Decimal("100") if premium_discount_percentage > 0 else Decimal("0.00")
            total_discount = product_offer_discount + coupon_discount_amount + premium_discount_amount

            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_variant=item.product_variant,
                quantity=quantity,
                price=item.price,
                gift_wrap=item.gift_wrap,
                gift_set=item.gift_set,
                offer_code=item.offer_code,
                discount_amount=total_discount.quantize(Decimal("0.01")),
                discount_percentage=item.discount_percentage,
                selected_flavours=item.selected_flavours if item.selected_flavours else None,
            )

            # Reduce stock safely
            if item.product_variant:
                item.product_variant.stock = max(item.product_variant.stock - quantity, 0)
                item.product_variant.save()
            elif item.gift_set:
                item.gift_set.stock = max(item.gift_set.stock - quantity, 0)
                item.gift_set.save()
            elif item.product:
                item.product.stock = max(item.product.stock - quantity, 0)
                item.product.save()

        # Clear cart
        cart_items.delete()
        order.status = "Completed"
        order.save()

        # Fire Celery tasks after commit
        transaction.on_commit(lambda: create_shiprocket_order_task.delay(order.id))
        # transaction.on_commit(lambda: send_invoice_email_task.delay(order.id))
        transaction.on_commit(lambda: notify_low_stock_task.delay(order.id))

    # Handle coupon usage
    coupon_code = request.session.pop("applied_coupon", None)
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code)
            CouponUsage.objects.create(guest_id=guest_id, coupon=coupon)
        except Coupon.DoesNotExist:
            pass

    # Handle premium offer usage
    premium_offer_code = request.session.pop("premium_offer_code", None)
    if premium_offer_code:
        offer = PremiumFestiveOffer.objects.filter(code=premium_offer_code).first()
        if offer:
            PremiumOfferUsage.objects.create(guest_id=guest_id, offer_code=offer.code)
        request.session.pop("premium_offer_percentage", None)
        request.session.pop(f"premium_offer_used_{premium_offer_code}", None)

    # Clear temporary session keys
    for key in ["gift_wrap", "razorpay_order_id", "razorpay_cart_hash"]:
        request.session.pop(key, None)

    messages.success(request, "🎉 Your order has been placed successfully!")
    return render(request, "user_panel/order_success.html", {"order": order})

from django.contrib.auth import logout
def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect('/')

from django.db.models import Min, Max, Avg, Prefetch, Q
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.db.models.functions import Lower, Replace
from django.db.models import Q, Value, IntegerField, Case, When, Prefetch
import re
@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    RESULT_LIMIT = 20

    # ---------- Categories ----------
    all_categories = list(
        Category.objects.only('id', 'name').values('id', 'name')
    )

    # ---------- Base queryset ----------
    products = (
        Product.objects.only(
            'id', 'name', 'image1', 'description', 'category_id'
        )
        .select_related('category')
        .prefetch_related(
            Prefetch(
                'gift_sets',
                queryset=GiftSet.objects.only(
                    'id', 'product_id',
                    'price', 'original_price', 'discounted_price'
                ),
                to_attr='gs'
            ),
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.only(
                    'id', 'product_id',
                    'price', 'original_price'
                ),
                to_attr='vars'
            ),
            Prefetch(
                'reviews',
                queryset=Review.objects.only(
                    'id', 'product_id', 'rating'
                ),
                to_attr='revs'
            )
        )
    )

    # ---------- SEARCH LOGIC ----------
    if query:
        q = re.sub(r'\s+', ' ', query.lower())
        q_clean = q.replace(" ", "")

        products = (
            products.annotate(
                name_clean=Replace(
                    Lower('name'),
                    Value(' '),
                    Value('')
                ),
                relevance=Case(
                    When(name__icontains=q, then=3),
                    When(name_clean__icontains=q_clean, then=2),
                    When(description__icontains=q, then=1),
                    default=0,
                    output_field=IntegerField(),
                )
            )
            .filter(
                Q(name__icontains=q) |
                Q(name_clean__icontains=q_clean) |
                Q(description__icontains=q)
            )
            .order_by('-relevance', 'id')   # 🔥 CRITICAL
        )

    # ---------- CATEGORY FILTER ----------
    if category_id:
        products = products.filter(category_id=category_id)

    # ---------- LIMIT ----------
    products = products.filter(category__isnull=False)
    products = products[:RESULT_LIMIT]

    # ---------- RESPONSE BUILD ----------
    results = []
# products = products.filter(category__isnull=False)

    for p in products:
        cat = (
          p.category.name.lower().replace(" ", "").replace("-", "")
          if p.category else ""
    )

        # ----- PRICE HANDLING -----
        if cat == "giftsets" and getattr(p, 'gs', None):
            prices = [g.discounted_price or g.price for g in p.gs if g.price]
            originals = [g.original_price for g in p.gs if g.original_price]
        else:
            prices = [v.price for v in getattr(p, 'vars', []) if v.price]
            originals = [v.original_price for v in getattr(p, 'vars', []) if v.original_price]

        # Skip products without price
        if not prices:
            continue

        mn, mx = min(prices), max(prices)
        price_display = f"₹{mn}" if mn == mx else f"₹{mn} - ₹{mx}"

        if originals:
            om, ox = min(originals), max(originals)
            original_price_display = f"₹{om}" if om == ox else f"₹{om} - ₹{ox}"
        else:
            original_price_display = "N/A"

        # ----- RATINGS -----
        ratings = [r.rating for r in getattr(p, 'revs', []) if r.rating]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
        rating_percentage = round((avg_rating / 5) * 100, 1)

        # ----- FINAL OUTPUT -----
        results.append({
            "id": p.id,
            "name": p.name,
            "image": p.image1.url if p.image1 else "",
            "description": (p.description or "")[:100],
            "url": f"/product/{p.id}/",
            "price_display": price_display,
            "original_price_display": original_price_display,
            "average_rating": avg_rating,
            "rating_percentage": rating_percentage,
        })

    return JsonResponse({
        "results": results,
        "categories": all_categories,
    })

from django.db.models import Min, Max, Avg, Prefetch


from django.db.models import Min, Max, Avg, Count, Q

def viewall_products(request, section):
    title = ""
    seo_title=""
    seo_description=""
    base_products = Product.objects.none()

    # -------- SECTION FILTER --------
    if section == "new-arrival":
        base_products = Product.objects.filter(is_new_arrival=True, is_active=True)
        title = "New Arrivals"
        seo_title= "New Arrivals Perfumes & Attars in India"
        seo_description="Explore latest perfume & attar new arrivals at Perfume Valley World in Mehdipatnam, Tolichowki and Shaikpet, Hyderabad. Discover premium fragrances for men and women with online shopping available."
    elif section == "trending":
        base_products = Product.objects.filter(is_trending=True, is_active=True)
        title = "Trending Products"
        seo_title="Trending Premium Perfumes & Attars in India"
        seo_description="Best trending perfume & attar new arrivals at Perfume Valley World in Mehdipatnam, Tolichowki and Shaikpet, Hyderabad. Discover premium fragrances for men and women with online shopping available."
    elif section == "best-seller":
        base_products = Product.objects.filter(is_best_seller=True, is_active=True)
        title = "Best Selling Products"
        seo_title ="Best Sellers Premium Perfumes & Attars in India"
        seo_description ="Discover best selling premium perfumes and attars at Perfume Valley World in Mehdipatnam, Tolichowki and Shaikpet, Hyderabad. Shop luxury fragrances online from top choices for men and women in India."
    elif section == "shopbyocassions":
        base_products = Product.objects.filter(is_shop_by_occassion=True, is_active=True)
        title = "Shop By Occasions"

    # --------------------------------------------------------
    # FIX: Cast price & original_price to Integer for accuracy
    # --------------------------------------------------------
    base_products = base_products.annotate(
        min_price=Min(Cast('variants__price', IntegerField())),
        max_price=Max(Cast('variants__price', IntegerField())),
        min_original_price=Min(Cast('variants__original_price', IntegerField())),
        max_original_price=Max(Cast('variants__original_price', IntegerField())),
        average_rating=Avg('reviews__rating'),
        review_count=Count('reviews'),
    )

    # -------- GIFTSET AGGREGATION WITH CAST --------
    giftset_prices = GiftSet.objects.filter(product__in=base_products).annotate(
        num_price=Cast('price', IntegerField()),
        num_original=Cast('original_price', IntegerField())
    ).values('product').annotate(
        min_price=Min('num_price'),
        max_price=Max('num_price'),
        min_original_price=Min('num_original'),
        max_original_price=Max('num_original'),
    )

    giftset_price_map = {g['product']: g for g in giftset_prices}
    giftset_product_ids = set(giftset_price_map.keys())

    # -------- WISHLIST --------
    
    guest_id = get_guest_id(request)

    wishlist_product_ids = list(
    Wishlist.objects.filter(guest_id=guest_id)
    .values_list('product_id', flat=True)
)


    

    combined_items = []

    # -------- LOOP --------
    for product in base_products:

        # WISHLIST CHECK
        is_in_wishlist = product.id in wishlist_product_ids

        # RATINGS
        average_rating = product.average_rating or 0
        review_count = product.review_count or 0

        # GIFTSET OVERRIDE
        if product.id in giftset_product_ids:
            price_data = giftset_price_map[product.id]

            combined_items.append({
                'type': 'giftset',
                'product': product,
                'min_price': price_data['min_price'],
                'max_price': price_data['max_price'],
                'min_original_price': price_data['min_original_price'],
                'max_original_price': price_data['max_original_price'],
                'is_in_wishlist': is_in_wishlist,
                'average_rating': round(average_rating, 1),
                'review_count': review_count
            })

        # REGULAR PRODUCT
        else:
            combined_items.append({
                'type': 'product',
                'product': product,
                'min_price': product.min_price,
                'max_price': product.max_price,
                'min_original_price': product.min_original_price,
                'max_original_price': product.max_original_price,
                'is_in_wishlist': is_in_wishlist,
                'average_rating': round(average_rating, 1),
                'review_count': review_count
            })

    banner = Banner.objects.filter(section=section).first()

    return render(request, 'user_panel/best_products.html', {
        'combined_items': combined_items,
        'title': title,
        'banner': banner,
        'seo_title': seo_title,
        'seo_description':seo_description,
        'wishlist_product_ids': wishlist_product_ids,
    })



def international_order(request):
    if request.method == 'POST':
        form = InternationalOrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('international_order_success')  # redirect after success
    else:
        form = InternationalOrderForm()

    return render(request, 'user_panel/international_order.html', {'form': form})


def international_order_success(request):
    return render(request, 'user_panel/international_order_success.html')


def disclaimer(request):
    return render(request, 'user_panel/disclaimer.html')


def user_address(request):
    guest_id = get_guest_id(request)

    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.guest_id = guest_id   # 🔥 ALWAYS
            address.save()

            request.session["selected_address_id"] = address.id
            return redirect(request.POST.get("next") or "view_cart")
        else:
            print("FORM ERRORS:", form.errors)
    else:
        form = AddressForm()

    return render(request, "user_panel/add_address.html", {"form": form})


def update_address(request, address_id):
    guest_id = get_guest_id(request)

    address = AddressModel.objects.filter(
        id=address_id,
        guest_id=guest_id
    ).first()

    if not address:
        return HttpResponse("Address not found")

    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.guest_id = guest_id   # 🔥 FORCE IT AGAIN
            updated.save()

            request.session["selected_address_id"] = updated.id
            return redirect("view_cart")
        else:
            print(form.errors)
    else:
        form = AddressForm(instance=address)

    return render(request, "user_panel/add_address.html", {"form": form})

    
    
#user_profile vie

def fetch_shiprocket_tracking(awb_code):
    """
    Fetch the latest tracking info from Shiprocket API for a given AWB code.
    Returns a dictionary with status, events, and estimated delivery.
    """
    if not awb_code:
        return {}

    token = get_shiprocket_token()
    headers = {"Authorization": f"Bearer {token}"}

    try:
        url = f"https://apiv2.shiprocket.in/v1/external/courier/track/awb/{awb_code}"
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            tracking_data = data.get("tracking_data", {})
            shipment_tracks = tracking_data.get("shipment_track", [])

            if isinstance(shipment_tracks, dict):
                shipment_tracks = [shipment_tracks]
            elif not isinstance(shipment_tracks, list):
                shipment_tracks = []

            current_status = shipment_tracks[-1].get("current_status") if shipment_tracks else ""
            etd = tracking_data.get("etd", "")

            return {
                "current_status": current_status,
                "shipment_tracks": shipment_tracks,
                "estimated_delivery": etd
            }
        else:
            return {"error": f"API error {response.status_code}"}

    except Exception as e:
        return {"error": str(e)}
    

def user_profile(request):
    guest_id=get_guest_id(request)
    print("guest_id",guest_id)
    # name = request.user.username.split('@')[0]
    profile, _ = UserProfile.objects.get_or_create(guest_id=guest_id)

    orders = (
        Order.objects
        .filter(guest_id=guest_id)
        .order_by('-created_at')
        .prefetch_related('items__product', 'items__product_variant')  # Prefetch nested items
    )

    for order in orders:
        for item in order.items.all():
            if item.selected_flavours:
               flavour_ids = [int(fid) for fid in item.selected_flavours.split(',') if fid.isdigit()]
               flavours_qs = Flavour.objects.filter(id__in=flavour_ids)
               item.flavour_names = ', '.join(f.name for f in flavours_qs)
            else:
               item.flavour_names = ''
        # Fetch live Shiprocket tracking
        if order.shiprocket_awb_code:
            tracking_info = fetch_shiprocket_tracking(order.shiprocket_awb_code)
            order.shiprocket_tracking_info = tracking_info
            order.shipment_activities = tracking_info.get("shipment_tracks", [])
            order.shiprocket_tracking_status = tracking_info.get("current_status", "")
            order.shiprocket_estimated_delivery = tracking_info.get("estimated_delivery", "")
            order.tracking_url = f"https://shiprocket.co/tracking/{order.shiprocket_awb_code}"
        else:
            order.shipment_activities = []
            order.tracking_url = None

    wishlist = Wishlist.objects.filter(guest_id=guest_id).select_related('product').prefetch_related(Prefetch('product__variants', queryset=ProductVariant.objects.filter(stock__gt=0)))

    for item in wishlist:
        cheapest_variant = (
        item.product.variants
        .filter(stock__gt=0)
        .order_by('price')
        .first()
    )
        if cheapest_variant:
           item.variant_price = cheapest_variant.price
           item.variant_original_price = cheapest_variant.original_price
           item.variant_size = cheapest_variant.size
           item.variant_bottle = cheapest_variant.bottle_type
        else:
           item.variant_price = None

    addresses = AddressModel.objects.filter(guest_id=guest_id).order_by('-created_at')
    help_queries = HelpQuery.objects.filter(guest_id=guest_id).order_by('-created_at')



    default_address = addresses.first()

    ordered_product_ids = OrderItem.objects.filter(order__guest_id=guest_id).values_list('product_id', flat=True)
    product_reviews = Review.objects.filter(product_id__in=ordered_product_ids)

    avg_rating_dict = {
        item['product_id']: {
            'rating': round(item['avg_rating'], 1),
            'percentage': round((item['avg_rating'] / 5) * 100, 2)
        }
        for item in product_reviews.values('product_id').annotate(avg_rating=Avg('rating'))
    }

    reviewed_product_ids = list(
        product_reviews.filter(guest_id=guest_id).values_list('product_id', flat=True)
    )

    tracking_stages = ["AWB Assigned","RTO Delivered", "Pickup Generated", "Out for Pickup", "Delivered"]

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'user_panel/user_profile2.html', {
        'profile': profile,
        'guest_id':guest_id,
        'orders': orders,
        'wishlist': wishlist,
        'addresses': addresses,
        'help_queries': help_queries,
        'form': form,
        'avg_rating_dict': avg_rating_dict,
        'reviewed_product_ids': reviewed_product_ids,
        'tracking_stages': tracking_stages,
        # 'display_name': name,
        'default_address': default_address,
    })
# def user_profile(request):
#     guest_id = get_guest_id(request)
#     profile, _ = UserProfile.objects.get_or_create(guest_id=guest_id)

#     # -------- ORDERS --------
#     orders = (
#         Order.objects
#         .filter(guest_id=guest_id)
#         .order_by("-created_at")
#         .prefetch_related("items__product", "items__product_variant")
#     )

#     for order in orders:
#         for item in order.items.all():
#             if item.selected_flavours:
#                 flavour_ids = [
#                     int(fid) for fid in item.selected_flavours.split(",")
#                     if fid.isdigit()
#                 ]
#                 item.flavour_names = ", ".join(
#                     Flavour.objects.filter(id__in=flavour_ids)
#                     .values_list("name", flat=True)
#                 )
#             else:
#                 item.flavour_names = ""

#         # ✅ READ TRACKING FROM DB ONLY
#         if order.shiprocket_awb_code:
#             order.shipment_activities = order.shiprocket_tracking_events or []
#             order.shiprocket_tracking_status = (
#                 order.shiprocket_tracking_status or "AWB Assigned"
#             )
#             order.tracking_url = f"https://shiprocket.co/tracking/{order.shiprocket_awb_code}"
#         else:
#             order.shipment_activities = []
#             order.shiprocket_tracking_status = "Order Placed"
#             order.tracking_url = None

#     # -------- WISHLIST --------
#     wishlist = (
#         Wishlist.objects
#         .filter(guest_id=guest_id)
#         .select_related("product")
#         .prefetch_related(
#             Prefetch(
#                 "product__variants",
#                 queryset=ProductVariant.objects.filter(stock__gt=0)
#             )
#         )
#     )

#     for item in wishlist:
#         variant = (
#             item.product.variants
#             .filter(stock__gt=0)
#             .order_by("price")
#             .first()
#         )
#         if variant:
#             item.variant_price = variant.price
#             item.variant_original_price = variant.original_price
#             item.variant_size = variant.size
#             item.variant_bottle = variant.bottle_type
#         else:
#             item.variant_price = None

#     addresses = AddressModel.objects.filter(guest_id=guest_id)
#     help_queries = HelpQuery.objects.filter(guest_id=guest_id)

#     return render(request, "user_panel/user_profile2.html", {
#         "profile": profile,
#         "guest_id": guest_id,
#         "orders": orders,
#         "wishlist": wishlist,
#         "addresses": addresses,
#         "help_queries": help_queries,
#         "default_address": addresses.first(),
#     })



    
def edit_address(request, address_id):
    address = get_object_or_404(AddressModel, id=address_id, guest_id=get_guest_id(request))
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully!")
            return redirect('user_profile')
    else:
        form = AddressForm(instance=address)
    return render(request, 'user_panel/edit_address.html', {'form': form, 'address': address})

def delete_address(request, address_id):
    address = get_object_or_404(AddressModel, id=address_id, guest_id=get_guest_id(request))
    if request.method == 'POST':
        address.delete()
        messages.success(request, "Address deleted successfully!")
        return redirect('user_profile')
    return render(request, 'user_panel/confirm_delete.html', {'address': address})

def submit_help_query(request):
    if request.method == 'POST':
        form = HelpQueryForm(request.POST)
        if form.is_valid():
            query = form.save(commit=False)
            query.guest_id = get_guest_id(request)
            query.save()
            messages.success(request, "Your query has been submitted successfully!")
            notify_admins(f"A new query has been submitted by {query.guest_id}. Query: {query.message}",category='queries')
            return redirect('user_profile')
    else:
        form = HelpQueryForm()
    return render(request, 'user_panel/submit_query.html', {'form': form})



def user_help_chat(request, query_id):
    query = get_object_or_404(HelpQuery, id=query_id, guest_id=get_guest_id(request))

    return render(request, 'help_query_chat.html', {
        'query': query,
        'messages': query.messages.all(),
        'is_admin': False
    })

import os
import uuid

@csrf_exempt
def update_profile_picture(request):
    guest_id=get_guest_id(request)
    if request.method == 'POST':
        try:
            profile = UserProfile.objects.get(guest_id=guest_id)
            
            if 'profile_image' not in request.FILES:
                return JsonResponse({'success': False, 'error': 'No image provided'})
            
            uploaded_file = request.FILES['profile_image']
            
            # Delete old image if exists
            if profile.profile_image:
                try:
                    os.remove(profile.profile_image.path)
                except Exception as e:
                    print(f"Error deleting old image: {e}")
            
            # Generate unique filename with timestamp
            ext = uploaded_file.name.split('.')[-1]
            filename = f"{guest_id}_{uuid.uuid4().hex[:8]}_{int(time.time())}.{ext}"
            
            # Save new image
            profile.profile_image.save(filename, uploaded_file)
            profile.save()
            
            # Return the new image URL with cache busting
            return JsonResponse({
                'success': True,
                'image_url': profile.profile_image.url,
                'timestamp': int(time.time())  # Add timestamp for cache busting
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def product_list(request):
    guest_id=get_guest_id(request)
    products = Product.objects.all()
    wishlist_product_ids = Wishlist.objects.filter(guest_id=guest_id).values_list('product_id', flat=True)
    return render(request, 'home3.html', {
        'products': products,
        'wishlist_product_ids': list(wishlist_product_ids)
    })



@csrf_exempt
def update_dob(request):
    if request.method == 'POST':
        guest_id=get_guest_id(request)
        data = json.loads(request.body)
        dob_str = data.get('dob')
        try:
            dob = datetime.strptime(dob_str, "%d-%m-%Y").date()
            profile = UserProfile.objects.get(guest_id=guest_id)
            profile.dob = dob
            profile.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

#shipping ===================================
from admin_panel.models import Order, OrderItem  # update if your models are named differently
from admin_panel.utils import fetch_shiprocket_tracking,get_shiprocket_token
def shiprocket_order_result_view(request):
    guest_id=get_guest_id(request)
    # Example: assume latest order by logged-in user
    try:
        guest_id=guest_id
        order = Order.objects.filter(guest_id=guest_id).latest('created_at')  # adjust field if needed
        address = AddressModel.objects.filter(guest_id=guest_id).latest('created_at')  # Or order.address if you store it
        order_items = OrderItem.objects.filter(order=order)

        result = create_shiprocket_order(order, address, order_items)
        return render(request, 'user_panel/home.html', {'result': result})

    except Order.DoesNotExist:
        return render(request, 'user_panel/home.html', {
            'result': {
                'status': 'error',
                'status_code': 404,
                'shiprocket_response': {'message': 'No order found for this user.'},
                'sent_payload': {}
            }
        })

def order_tracking_view(request, order_id):
    guest_id=get_guest_id(request)
    order = get_object_or_404(Order, id=order_id, guest_id=guest_id)
    tracking = order.shiprocket_tracking_info
    print(tracking,"tracking")

    if isinstance(tracking, str):
        try:
            tracking = json.loads(tracking)
        except json.JSONDecodeError:
            tracking = {}

    shipment_tracks = tracking.get("shipment_tracks") or tracking.get("shipment_track") or []

   
    first_track = shipment_tracks[0] if shipment_tracks else {}
    shipment_activities = tracking.get("shipment_track_activities", [])

    tracking_stages = [
        "Order Confirmed",
        "AWB Assigned",
        "Pickup Generated",
        "In Transit",
        "REACHED AT DESTINATION HUB",
        "Delivered",
        # "Pick up Exception",
        # "Canceled"

    ]

    current_status = first_track.get("current_status", "")
    current_stage_index = tracking_stages.index(current_status) if current_status in tracking_stages else -1

    return render(request, 'user_panel/tracking.html', {
        'order': order,
        'courier': first_track.get('courier_name', ''),
        'awb_code': first_track.get('awb_code', ''),
        'current_status': current_status,
        'origin': first_track.get('origin', ''),
        'destination': first_track.get('destination', ''),
        'est_delivery': tracking.get('etd', '')[:10],
        'track_url': tracking.get('track_url', ''),
        'history': shipment_tracks,
        'tracking_stages': tracking_stages,
        'current_stage_index': current_stage_index,
        'shipment_activities': shipment_activities,
    })



def download_invoices(request, order_id):
    guest_id=get_guest_id(request)
    order = get_object_or_404(Order, id=order_id, guest_id=guest_id)
    token = get_shiprocket_token()
    url = "https://apiv2.shiprocket.in/v1/external/orders/print/invoice"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "ids": [order.shiprocket_order_id]
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    if response.status_code == 200 and data.get("invoice_url"):
        return HttpResponseRedirect(data["invoice_url"])
    return JsonResponse(data, status=response.status_code)


from django.core.mail import EmailMessage
import requests
from django.conf import settings

def send_invoice_email(order):
    """
    Sends invoice PDF via email to the guest's address email.
    """
    recipient_email = getattr(order.address, 'email', None)

    if not recipient_email:
        # No email available, skip sending
        print(f"⚠️ No email found for order {order.id}, invoice not sent.")
        return

    try:
        # Get Shiprocket token
        token = get_shiprocket_token()
        url = "https://apiv2.shiprocket.in/v1/external/orders/print/invoice"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {"ids": [order.shiprocket_order_id]}
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if response.status_code == 200 and data.get("invoice_url"):
            invoice_url = data["invoice_url"]

            # Download invoice PDF
            invoice_response = requests.get(invoice_url)
            if invoice_response.status_code == 200:
                email = EmailMessage(
                    subject='Your Order Invoice',
                    body='Thank you for your order. Please find your invoice attached.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient_email],
                )
                email.attach(f'invoice_{order.id}.pdf', invoice_response.content, 'application/pdf')
                email.send()
                print(f"✅ Invoice sent for order {order.id} to {recipient_email}")
            else:
                print(f"⚠️ Failed to download invoice PDF for order {order.id}")
        else:
            print(f"⚠️ Failed to generate invoice for order {order.id}: {data}")

    except Exception as e:
        print(f"⚠️ Error sending invoice for order {order.id}: {str(e)}")

from django.core.mail import EmailMultiAlternatives
from admin_panel.forms import SubscriptionForm
from user_panel.forms import ContactForm
from django.http import JsonResponse


def subscription_add(request):
    if request.method == 'POST':
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            subscription = form.save()
            
            # --------------- Send Welcome Email ---------------
            subject = "Welcome to Perfumavalley! 🌸"
            
            # Plain text fallback
            text_content = (
                f"Hi {subscription.name or subscription.email},\n\n"
                "Thank you for subscribing to Perfumavalley! 🌸✨\n"
                "You'll receive exclusive offers and updates.\n\n"
                "Stay fragrant,\nTeam Perfumavalley"
            )
            
            # HTML email
            html_content = f"""
            <html>
               <body style="font-family: Arial, sans-serif; background:#f9f9f9; padding:20px;">
                <div style="max-width:600px; margin:auto; background:#fff; border-radius:10px; box-shadow:0 4px 8px rgba(0,0,0,0.1); padding:20px;">
                  <p>Hi <b>{subscription.name or subscription.email}</b>,</p>

<p>Welcome to <span style="color:#d63384;">Perfumevalley</span>! 🌸</p>

<p>As a special thank-you for subscribing, we're giving you an exclusive discount on your first purchase.</p>

<div style="background:#fff0f6; border:2px dashed #d63384; padding:15px; text-align:center; border-radius:8px; margin:20px 0;">
  <p style="margin:0; font-size:16px;">Use Coupon Code</p>
  <h2 style="margin:5px 0; color:#d63384; letter-spacing:2px;">PREMIUM10</h2>
  <p style="margin:0; font-size:14px;">Apply this coupon at checkout and enjoy <b>10% OFF</b> on your order.</p>
</div>

<p>Don't miss out — explore our premium fragrance collection and find your perfect scent today.</p><br>
<a href="https://www.instagram.com/perfumevalley.store/" 
   style="color:#d63384; text-decoration:none; font-weight:bold;">
Instagram
</a>
<a href="https://www.facebook.com/PerfumeValleyWorld/" 
   style="color:#d63384; text-decoration:none; font-weight:bold;">
Facebook
</a>
                </div>
              </body>
            </html>
            """
            
            try:
                msg = EmailMultiAlternatives(
                    subject,
                    text_content,
                    settings.DEFAULT_FROM_EMAIL,
                    [subscription.email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send()
            except Exception as e:
                # If email fails, we still return success to the user
                print("Email sending failed:", e)
            # ---------------------------------------------------

            # AJAX request
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Successfully Subscribed!'})

            # Regular request
            return redirect(request.META.get('HTTP_REFERER', '/'))

        else:
            print(form.errors.as_json())
            # Validation errors
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                errors = {}
                for field, err_list in form.errors.items():
                    errors[field] = err_list[0]   # take first error message

                return JsonResponse({
                   'success': False,
                     'errors': errors
            })
            

    return redirect('/')





def store_locator(request):
    stores = Location_Store.objects.all()
    return render(request, 'user_panel/locator.html', {'stores': stores})
def about_us(request):
    return render(request, 'user_panel/about.html')

def terms_and_conditions(request):
    return render(request,'user_panel/terms_and_conditions.html') 

def privacy_policy(request):
    return render(request,'user_panel/privacy_policy.html')

def contact_us(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you! Your message has been submitted.")
            return redirect('contact')  # avoid resubmission on refresh
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ContactForm()
    
    return render(request, 'user_panel/contact_us.html', {'form': form})



from admin_panel.models import Product, Review
from admin_panel.forms import ReviewForm


from django.http import HttpResponseForbidden



def write_review(request, product_id):
    guest_id=get_guest_id(request)
    product = get_object_or_404(Product, id=product_id)

    # ✅ Ensure user purchased the product
    has_purchased = OrderItem.objects.filter(
        order__guest_id=guest_id,
        product=product
    ).exists()

    if not has_purchased:
        return HttpResponseForbidden("You can only review products you've purchased.")

    # ✅ Check if already reviewed this product
    already_reviewed = Review.objects.filter(guest_id=guest_id, product=product).exists()
    if already_reviewed:
        messages.error(request, "You've already reviewed this product.")
        return redirect('product_detail', product_id=product.id)

    # ✅ Handle for submission
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.guest_id = guest_id
            review.product = product
            review.save()
            messages.success(request, "Thank you for reviewing this product!")
            return redirect('product_detail', product_id=product.id)
    else:
        form = ReviewForm()

    return render(request, 'user_panel/user_profile2.html', {
        'form': form,
        'product': product,
    })
