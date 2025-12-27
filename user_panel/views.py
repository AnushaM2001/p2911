import random
import string
import json
import time
import traceback
from io import BytesIO

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
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.apps import apps
from django.db.models.functions import Cast, Lower, Greatest

# Redis client
r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)

def progress(request):
    return render(request, 'user_panel/progress.html')


def a(req):
    return render(req,'user_panel/home3.html')

def generate_otp():
    return ''.join(random.choices(string.digits, k=4))


def send_otp(email, otp_code):
    subject = 'Your OTP Code'
    message = f'Your OTP code is: {otp_code}'
    from_email = settings.DEFAULT_FROM_EMAIL
    try:
        send_mail(subject, message, from_email, [email])
        print("✅ OTP sent to:", email)
    except Exception as e:
        print("❌ Email sending failed:", e)
    # send_mail(subject, message, from_email, [email])


@csrf_exempt
def send_otp_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            otp_code = generate_otp()
            OTP.objects.create(
                email=email,
                otp=otp_code,
                expires_at=timezone.now() + timezone.timedelta(minutes=5)
            )
            send_otp(email, otp_code)
            print(otp_code)
            request.session['email'] = email
            return redirect('verify_email_otp')
    return render(request, 'user_panel/login.html')



@csrf_exempt
def verify_otp_view(request):
    email = request.session.get('email')

    if request.method == 'POST':
        if 'resend_otp' in request.POST:
            otp_code = generate_otp()
            OTP.objects.create(
                email=email,
                otp=otp_code,
                expires_at=timezone.now() + timezone.timedelta(minutes=5)
            )
            send_otp(email, otp_code)
            print("resend:", otp_code)
            return render(request, 'user_panel/verify_otp.html', {
                'email': email,
                'message': 'OTP resent successfully.'
            })

        # OTP submission
        otp = request.POST.get('otp')
        if otp:
            try:
                otp_entry = OTP.objects.filter(
                    email=email,
                    otp=otp,
                    expires_at__gte=timezone.now()
                ).latest('created_at')

                # ✅ Get or create user
                user, created = User.objects.get_or_create(username=email, defaults={'email': email})
                if not user.is_active:
                        return render(request, 'user_panel/verify_otp.html', {
                                'email': email,
                                'error': 'Your account is blocked. Please contact support.'
                            })

                # ✅ Log the user in
                login(request, user)

                request.session['emailSucessLogin'] = True
                return redirect('home')

            except OTP.DoesNotExist:
                return render(request, 'user_panel/verify_otp.html', {
                    'error': 'Invalid or expired OTP',
                    'email': email
                })

    return render(request, 'user_panel/verify_otp.html', {'email': email})

def blocked_user_view(request):
    return render(request, 'user_panel/blocked_user.html')


 # 15 minutes
# def home1(request):
#     products = Product.objects.all().annotate(
#     average_rating=Avg('reviews__rating'),  # average out of 5
#     review_count=Count('reviews')           # total number of reviews
# )
#     current_time = timezone.now()
#     wishlist_product_ids = []
    
#     # Fetch festival offer
#     festival_offer = PremiumFestiveOffer.objects.filter(
#         premium_festival='Festival',
#         start_date__lte=current_time,
#         end_date__gt=current_time
#     ).order_by('-created_at').first()

#     offer_percentage = None
#     startdatetime = None
#     enddatetime = None
#     offername = None
#     if festival_offer:
#         offer_percentage = festival_offer.percentage
#         startdatetime = festival_offer.start_date
#         enddatetime = festival_offer.end_date
#         offername = festival_offer.offer_name
#     else:
#         print("No Festival offer found")
#     print("festival offers",festival_offer)

#     # Fetch banners, categories, and subcategories
#     banners = Banner.objects.all().order_by('created_at')
#     first_banner_no_section = None
#     other_banners = []
#     for banner in banners:
#         if not banner.section and not first_banner_no_section:
#             first_banner_no_section = banner
#         else:
#             other_banners.append(banner)
#     categories = Category.objects.all().order_by('-created_at')[:4]
#     subcategories = Subcategory.objects.annotate(
#         name_lower=Lower('name')
#     ).filter(
#         name_lower__in=['french perfumes', 'arabic perfumes', 'french attars', 'arabic attars']
#     ).order_by('-created_at')[:4]

#     # Fetch products with min and max prices
#     ScrollBar = Product.objects.filter(~Q(scroll_bar=""), ~Q(scroll_bar=None)).order_by('-created_at').first()

#     best_selling = Product.objects.filter(is_best_seller=True).annotate(
#     min_price=Min('variants__price'),
#     max_price=Max('variants__price'),
#     s_price=Min(Cast('variants__original_price', IntegerField())),
#     e_price=Max(Cast('variants__original_price', IntegerField()))-Value(100),
#     average_rating=Avg('reviews__rating'),      # 👈 avg rating
#     review_count=Count('reviews')               # 👈 number of reviews
#       ).order_by('-created_at')[:12]
    
#     new_arrival = Product.objects.filter(is_new_arrival=True).annotate(
#         min_price=Min('variants__price'),
#         max_price=Max('variants__price'),
#         s_price=Min(Cast('variants__original_price', IntegerField())),
#         e_price=Max(Cast('variants__original_price', IntegerField()))-Value(100),
#         average_rating=Avg('reviews__rating'),      # 👈 avg rating
#     review_count=Count('reviews') 
#     ).order_by('-created_at')[:12]
#     trending = Product.objects.filter(is_trending=True).annotate(
#         min_price=Min('variants__price'),
#         max_price=Max('variants__price'),
#         s_price=Min(Cast('variants__original_price', IntegerField())),
#         e_price=Max(Cast('variants__original_price', IntegerField()))-Value(100),
#         average_rating=Avg('reviews__rating'),      # 👈 avg rating
#     review_count=Count('reviews') 
#     ).order_by('-created_at')[:12]

#     occasions = Subcategory.objects.annotate(
#         name_lower=Lower('name')
#     ).filter(
#         name_lower__in=['sports', 'office', 'party', 'travel']
#     ).order_by('-created_at')[:4]

#     if request.user.is_authenticated:
#         wishlist_product_ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))

#     # Fetch multiple videos to display
#     videos = ProductVideo.objects.all().order_by('-created_at')[:10]  # Fetch the latest 10 videos
#     out_reviews=Client_review.objects.all()
#     # Render the template with context
#     return render(request, 'user_panel/home1.html', {
#         'offername': offername,
#         'categories': categories,
#         'banners': banners,
#         'subcategories': subcategories,
#         'best_selling': best_selling,
#         'new_arrival': new_arrival,
#         'trending': trending,
#         'ScrollBar': ScrollBar,
#         'offer_percentage': offer_percentage,
#         'startdatetime': startdatetime,
#         'enddatetime': enddatetime,
#         'occasions': occasions,
#         'videos': videos,  # Pass multiple videos to the template
#         'first_banner_no_section': first_banner_no_section,
#         'wishlist_product_ids': wishlist_product_ids,
#     'other_banners': other_banners,
#     'festival_offer':festival_offer,
#     'out_reviews':out_reviews
#     })




def home1(request):
    current_time = timezone.now()

    # --------------------------------------------------
    # 🔹 Common product annotations (REUSED everywhere)
    # --------------------------------------------------
    product_annotations = {
        "min_price": Min("variants__price"),
        "max_price": Max("variants__price")-Value(100),
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
    # 🔹 Wishlist (only IDs)
    # --------------------------------------------------
    wishlist_product_ids = []
    if request.user.is_authenticated:
        wishlist_product_ids = list(
            Wishlist.objects
            .filter(user=request.user)
            .values_list("product_id", flat=True)
        )

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
        "wishlist_product_ids": wishlist_product_ids,
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




@login_required(login_url='email_login')
def toggle_wishlist(request):
    if request.method == "POST":
        product_id = request.POST.get("product_id")
        product = get_object_or_404(Product, id=product_id)

        try:
            with transaction.atomic():
                wishlist_item, created = Wishlist.objects.get_or_create(
                    user=request.user,
                    product=product
                )
        except IntegrityError:
            # If duplicate happens, fetch the existing one
            wishlist_item = Wishlist.objects.get(user=request.user, product=product)
            created = False

        if created:
            status = "added"
        else:
            wishlist_item.delete()
            status = "removed"

        return JsonResponse({"status": status})

    return JsonResponse({"error": "Invalid request"}, status=400)


from django.db.models import Min, Max, Avg, FloatField
from django.db.models.functions import Cast
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal

from django.db.models import Q, Avg, Min, Max,FloatField
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache

# import your models (update this line)
# from yourapp.models import ProductVariant, Product, GiftSet, Category, Subcategory, Wishlist, PremiumFestiveOffer

from django.db.models import Min, Max, Avg, Count, Q, Prefetch, Window, F
from django.db.models.functions import Cast, RowNumber
from django.db.models import FloatField
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.core.cache import cache
import time
import json
import hashlib

# ============================================================
# 1) HTML TEMPLATE VIEW (filtered_products)
# ============================================================
from django.db.models import Min, Max, Avg, Count, Q, Prefetch
from django.db.models.functions import Cast
from django.db.models import FloatField
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.core.cache import cache
import time
import json
import hashlib

# ============================================================
# 1) HTML TEMPLATE VIEW (filtered_products) - FIXED
# ============================================================
def filtered_products(request, category_id=None, subcategory_id=None):
    """HTML template view - FIXED for your model structure"""
    start_time = time.time()
    
    # Create cache key
    params_dict = {
        'category_id': category_id,
        'subcategory_id': subcategory_id,
        'categories': request.GET.get('categories', ''),
        'subcategories': request.GET.get('subcategories', ''),
        'path': request.path
    }
    cache_key = f"html_filter_{hashlib.md5(json.dumps(params_dict, sort_keys=True).encode()).hexdigest()}"
    
    # Check cache
    cached_context = cache.get(cache_key)
    if cached_context:
        cached_context['cache_hit'] = True
        cached_context['execution_time'] = round(time.time() - start_time, 3)
        return render(request, 'user_panel/filtered_products.html', cached_context)
    
    # ========== GET CATEGORY/SUBCATEGORY ==========
    category = None
    subcategory = None
    
    if category_id:
        category = Category.objects.filter(id=category_id).first()
    
    if subcategory_id:
        subcategory = Subcategory.objects.filter(id=subcategory_id).first()
    
    # Parse filter parameters from URL (e.g., /products/?category=23)
    category_ids = []
    if request.GET.get('category'):
        try:
            category_ids = [int(request.GET.get('category'))]
        except:
            category_ids = []
    
    # Also check for comma-separated categories
    if request.GET.get('categories'):
        try:
            category_ids = [int(i) for i in request.GET.get('categories').split(',') if i]
        except:
            category_ids = []
    
    subcategory_ids = []
    if request.GET.get('subcategories'):
        try:
            subcategory_ids = [int(i) for i in request.GET.get('subcategories').split(',') if i]
        except:
            subcategory_ids = []
    
    # Check if giftset
    is_giftset = False
    if category:
        # Check for giftset in category name
        is_giftset = any(word in category.name.lower() for word in ['giftset', 'gift set', 'gift-set', 'gift'])
    
    # ========== PROCESS PRODUCTS ==========
    product_list = []
    
    if is_giftset and category:
        # GIFTSETS - Use Product model with category filter
        giftsets_products = Product.objects.filter(
            category=category
        ).prefetch_related(
            'giftset_set__flavours'
        )
        
        # Get active offers
        now = timezone.now()
        active_offers = PremiumFestiveOffer.objects.filter(
            Q(premium_festival__in=['Welcome', 'Premium']) |
            Q(start_date__lte=now, end_date__gte=now)
        )
        
        for product in giftsets_products:
            # Get gift set for this product
            giftset = product.giftset_set.first()
            if not giftset:
                continue
                
            # Apply offers
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
                'price': float(giftset.price) if giftset.price else 0,
                'discounted_price': float(discounted_price) if discounted_price else None,
                'original_price': float(product.original_price) if product.original_price else 0,
                'offer_code': offer_code,
                'flavours': list(giftset.flavours.values_list('name', flat=True)) if hasattr(giftset, 'flavours') else [],
                'image': product.image1.url if product.image1 else '',
                'average_rating': 0,  # Calculate if you have reviews
                'is_giftset': True,
            })
        
        context_products = product_list
        
    else:
        # REGULAR PRODUCTS
        base_qs = Product.objects.all()
        
        # Apply filters
        if category_ids:
            base_qs = base_qs.filter(category_id__in=category_ids)
        elif category_id:
            base_qs = base_qs.filter(category_id=category_id)
        
        if subcategory_ids:
            base_qs = base_qs.filter(subcategory_id__in=subcategory_ids)
        elif subcategory_id:
            base_qs = base_qs.filter(subcategory_id=subcategory_id)
        
        # Annotate with prices and ratings
        products_qs = base_qs.annotate(
            min_price=Min('variants__price'),
            average_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        ).prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.all())
        )
        
        # Get active offers
        now = timezone.now()
        active_offers = PremiumFestiveOffer.objects.filter(
            Q(premium_festival__in=['Welcome', 'Premium']) |
            Q(start_date__lte=now, end_date__gte=now)
        )
        
        for product in products_qs:
            # Get cheapest variant for offers
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
                'price': float(product.min_price) if product.min_price else 0,
                'discounted_price': float(discounted_price) if discounted_price else None,
                'original_price': float(product.original_price) if product.original_price else 0,
                'offer_code': offer_code,
                'image': product.image1.url if product.image1 else '',
                'average_rating': float(product.average_rating) if product.average_rating else 0,
                'review_count': product.review_count or 0,
                'is_giftset': False,
            })
        
        context_products = product_list
    
    # ========== SIDEBAR DATA ==========
    sidebar_cache_key = 'filter_sidebar_data'
    sidebar_data = cache.get(sidebar_cache_key)
    
    if not sidebar_data:
        # Get price range - only from active products if you have is_active field
        try:
            # Try with is_active filter if Product has it
            price_range = ProductVariant.objects.filter(
                product__is_active=True
            ).aggregate(
                min_price=Min('price'),
                max_price=Max('price')
            )
        except:
            # Fallback to all products
            price_range = ProductVariant.objects.all().aggregate(
                min_price=Min('price'),
                max_price=Max('price')
            )
        
        sidebar_data = {
            # No is_active filter for Category/Subcategory
            'categories': list(Category.objects.all().values('id', 'name')),
            'subcategories': list(Subcategory.objects.all().values('id', 'name', 'category_id')),
            'sizes': list(ProductVariant.objects.values_list('size', flat=True).distinct()),
            'min_price': int(price_range['min_price'] or 0),
            'max_price': int(price_range['max_price'] or 1000)
        }
        cache.set(sidebar_cache_key, sidebar_data, 3600)
    
    # ========== PREPARE CONTEXT ==========
    context = {
        'category': category,
        'subcategory': subcategory,
        'categories': sidebar_data['categories'],
        'subcategories': sidebar_data['subcategories'],
        'sizes': sidebar_data['sizes'],
        'min_price': sidebar_data['min_price'],
        'max_price': sidebar_data['max_price'],
        'products': context_products,
        'category_banner_url': category.banner.url if category and category.banner else None,
        'subcategory_banner_url': subcategory.banner.url if subcategory and subcategory.banner else None,
        'is_giftset': is_giftset,
        'cache_key': cache_key,
        'execution_time': round(time.time() - start_time, 3),
        'cache_hit': False,
    }
    
    if is_giftset:
        context['giftsets'] = product_list
    
    # Cache the context
    cache.set(cache_key, context, 300)
    
    return render(request, 'user_panel/filtered_products.html', context)
# ============================================================
# 2) AJAX API VIEW (ajax_filter_products) - FIXED VERSION
# ============================================================
def ajax_filter_products(request):
    """Optimized AJAX API with caching - FIXED with correct original price calculations"""
    start_time = time.time()
    
    # Create cache key
    params_str = json.dumps(dict(request.GET), sort_keys=True)
    user_id = request.user.id if request.user.is_authenticated else 'anon'
    cache_key = f"api_filter_{hashlib.md5(f'{params_str}_{user_id}'.encode()).hexdigest()}"
    
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
            giftsets_flag = 'giftset' in category_name.lower()
    
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
    wishlist_product_ids = set()
    if request.user.is_authenticated:
        wishlist_cache_key = f'user_wishlist_{request.user.id}'
        wishlist_product_ids = cache.get(wishlist_cache_key)
        if wishlist_product_ids is None:
            wishlist_product_ids = set(
                Wishlist.objects.filter(user=request.user)
                .values_list('product_id', flat=True)
            )
            cache.set(wishlist_cache_key, wishlist_product_ids, 300)
    
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
        
        # Apply category filters
        if category_ids:
            products_qs = products_qs.filter(category_id__in=category_ids)
        
        # Apply subcategory filters  
        if subcategory_ids:
            products_qs = products_qs.filter(subcategory_id__in=subcategory_ids)
        
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
            variants_by_product = {}
            for var in variants_qs.order_by('product_id', 'price'):
                if var.product_id not in variants_by_product:
                    variants_by_product[var.product_id] = var
            
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
            for product_id, var in variants_by_product.items():
                product = products_dict.get(product_id)
                if not product:
                    continue
                
                # Apply offers
                base_price = float(var.price) if var.price else 0
                discounted_price = None
                offer_applied = None
                
                for offer in active_offers:
                    discounted = offer.apply_offer(var)
                    if discounted:
                        discounted_price = float(discounted)
                        offer_applied = offer
                        break
                
                # ========== GET PRICE RANGES ==========
                price_info = price_ranges.get(product_id, {})
                
                # Product's original price from Product model
                product_original = float(product.original_price) if product.original_price else 0
                
                # Variant's original price
                try:
                    var_original = float(var.original_price) if var.original_price else 0
                except (ValueError, TypeError):
                    var_original = product_original
                
                # ========== GET REVIEW DATA ==========
                review_info = reviews.get(product_id, {'avg_rating': 0, 'review_count': 0})
                
                # ========== BUILD PRODUCT DATA ==========
                combined_products.append({
                    "id": product_id,
                    "name": product.name,
                    "price": base_price,
                    "original_price": product_original,  # From Product model
                    "min_price": float(price_info.get('min_price', base_price)),
                    "max_price": float(price_info.get('max_price', base_price)),
                    "min_original_price": float(price_info.get('min_original', var_original)),
                    "max_original_price": float(price_info.get('max_original', var_original)),
                    "discounted_price": discounted_price,
                    "is_offer_active": bool(offer_applied),
                    "offer_code": offer_applied.code if offer_applied else None,
                    "offer_start_time": offer_applied.start_date if offer_applied else None,
                    "offer_end_time": offer_applied.end_date if offer_applied else None,
                    "size": var.size,
                    "stock": var.stock,
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
    
@login_required(login_url='email_login')    
def product_detail(request, product_id):
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
    in_cart = Cart.objects.filter(user=request.user, product=product).exists()
    cart_item = Cart.objects.filter(user=request.user, product=product).first()

    is_giftset = product.category.name.lower().replace(' ', '').replace('-', '') == 'giftsets'
    flavours = Flavour.objects.all()
    gift_sets = GiftSet.objects.filter(product=product).select_related('product').prefetch_related('flavours')

    offers = PremiumFestiveOffer.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
    enhanced_reviews = []
    for r in reviews:
        enhanced_reviews.append({
        'username': r.user.username if r.user else 'Anonymous',
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


@login_required(login_url='email_login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    try:
        quantity = int(request.POST.get('quantity', 1))
        action = request.POST.get('action')
        variant_id = request.POST.get('variant_id')
        gift_set_id = request.POST.get('gift_set_id')
        selected_price = request.POST.get('selected_price')
        selected_flavours = request.POST.get('selected-flavours', '')

        if quantity < 1:
            raise ValueError("Quantity must be at least 1")
        if not variant_id and not gift_set_id:
            raise ValueError("Please select a product variant or gift set")

        cart_key = f"cart:{request.user.id}"

        if gift_set_id:
            item_key = f"giftset:{gift_set_id}"
            gift_set = get_object_or_404(GiftSet, id=gift_set_id)
            price = float(selected_price) if selected_price else float(gift_set.price)
        elif variant_id:
            item_key = f"variant:{variant_id}"
            variant = get_object_or_404(ProductVariant, id=variant_id)
            price = float(variant.price)
        else:
            item_key = f"product:{product_id}"
            price = float(product.price)

        cart_filter = {
            'user': request.user,
            'product': product,
            'product_variant_id': variant_id if variant_id else None,
            'gift_set_id': gift_set_id if gift_set_id else None
        }

        if selected_flavours:
            cart_filter['selected_flavours'] = selected_flavours

        cart_item = Cart.objects.filter(**cart_filter).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.price = price
            if selected_flavours:
                cart_item.selected_flavours = selected_flavours
            cart_item.save()
        else:
            cart_item = Cart.objects.create(
                user=request.user,
                product=product,
                product_variant_id=variant_id if variant_id else None,
                gift_set_id=gift_set_id if gift_set_id else None,
                quantity=quantity,
                price=price,
                selected_flavours=selected_flavours or ''
            )

        current_item = r.hget(cart_key, item_key)
        current_quantity = json.loads(current_item)['quantity'] if current_item else 0
        new_quantity = current_quantity + quantity

        item_data = {
            'product_id': product_id,
            'variant_id': variant_id,
            'gift_set_id': gift_set_id,
            'quantity': new_quantity,
            'price': price,
            'selected_flavours': selected_flavours or '',
            'updated_at': time.time()
        }

        r.hset(cart_key, item_key, json.dumps(item_data))
        r.publish(
            f"cart_updates:{request.user.id}",
            json.dumps({
                'action': 'update',
                'item_key': item_key,
                'quantity': new_quantity,
                'cart_count': r.hlen(cart_key)
            })
        )

        # 🟩 NEW — Build complete sidebar data
        cart_items_db = Cart.objects.filter(user=request.user)

        cart_items_list = []
        subtotal = 0

        for item in cart_items_db:
            item_total = item.price * item.quantity
            subtotal += item_total

            cart_items_list.append({
                "id": item.id,
                "name": item.product.name,
                "price": float(item.price),
                "quantity": item.quantity,
                "image": item.product.image1.url if item.product.image1 else "",
                "offer": f"{item.product.offer.percentage}% Off" if hasattr(item.product, "offer") else ""
            })

        delivery_charge = item.product.delivery_charges if subtotal > 0 else 0
        platform_fee = item.product.platform_fee if subtotal > 0 else 0
        total = subtotal + delivery_charge + platform_fee

        # 🟩 NEW — Return full JSON needed for sidebar
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message': 'Item added to cart successfully!',
                'cart_count': r.hlen(cart_key),

                'cart_items': cart_items_list,
                'order_summary': {
                    "subtotal": subtotal,
                    "delivery": delivery_charge,
                    "platform_fee": platform_fee,
                    "total": total
                }
            })

        return redirect('view_cart')

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
from decimal import Decimal
from django.db.models import Sum

@require_POST
def update_cart_item(request, item_id):
    try:
        print(f"\n=== Starting update for item {item_id} ===")
        print(f"User: {request.user}")
        print(f"Action: {request.POST.get('action')}")

        # Get cart item
        cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
        print(f"Current quantity: {cart_item.quantity}")

        # Update quantity
        action = request.POST.get('action')
        if action == 'increase':
            cart_item.quantity += 1
        elif action == 'decrease' and cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            print(f"Invalid action or quantity: {action}, {cart_item.quantity}")

        cart_item.save()
        print(f"New quantity: {cart_item.quantity}")

        # Fetch all cart items
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        print(f"Total cart items: {cart_items.count()}")

        # Calculate base prices using Decimal for precision
        subtotal = sum(Decimal(item.price) * item.quantity for item in cart_items)
        delivery = sum(Decimal(item.product.delivery_charges or 0) for item in cart_items)
        platform_fee = sum(Decimal(item.product.platform_fee or 0) for item in cart_items)

        total_items = cart_items.aggregate(Sum('quantity'))['quantity__sum'] or 0
        print(f"Subtotal: {subtotal}")
        print(f"Delivery: {delivery}")
        print(f"Platform fee: {platform_fee}")

        # Get discounts and extras
        coupon_discount = Decimal(request.session.get('coupon_discount', 0))
        gift_wrap = request.session.get('gift_wrap', False)
        gift_wrap_cost = Decimal(150) if gift_wrap else Decimal(0)

        # Calculate total price
        total_price = subtotal + delivery + platform_fee - coupon_discount + gift_wrap_cost
        print(f"Coupon discount: {coupon_discount}")
        print(f"Gift wrap cost: {gift_wrap_cost}")
        print(f"Final total price: {total_price}")

        # Prepare response
        response_data = {
            'status': 'success',
            'new_quantity': cart_item.quantity,
            'cart_count': total_items,
            'item_count': total_items,
            'prices': {
                'subtotal': float(subtotal),
                'delivery': float(delivery),
                'platform_fee': float(platform_fee),
                'discount': float(coupon_discount),
                'gift_wrap': float(gift_wrap_cost),
                'total_price': float(total_price)
            }
        }

        print("=== Response Data ===")
        print(response_data)

        return JsonResponse(response_data)

    except Exception as e:
        print(f"\n!!! ERROR in update_cart_item !!!")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")

        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import redis, json
from decimal import Decimal


def calculate_cart_totals(request):
    cart_items = Cart.objects.filter(user=request.user)
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

    coupon_discount = Decimal(request.session.get('applied_coupon_discount', 0))

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
    }

@login_required
def sync_redis_cart(request):
    if request.method != "POST":
        return JsonResponse({"status": "error"}, status=405)

    try:
        totals = calculate_cart_totals(request)

        cart_items = Cart.objects.filter(user=request.user).values("id", "quantity")

        quantities = {
            str(item["id"]): item["quantity"]
            for item in cart_items
        }

        return JsonResponse({
            "status": "success",
            "order_summary": {
                "subtotal": float(totals["products_total"]),
                "delivery": float(totals["delivery"]),
                "platform_fee": float(totals["platform_fee"]),
                "gift_wrap": float(totals["gift_wrap"]),
                "discount": float(totals["coupon_discount"]),
                "premium_discount": float(totals["premium_discount"]),
                "total": float(totals["final_total"]),
            },
            "cart_count": totals["cart_count"],
            "quantities": quantities   # ✅ IMPORTANT
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


# @login_required
# def sync_redis_cart(request):
#     if request.method != "POST":
#         return JsonResponse({"status": "error", "message": "POST only allowed"}, status=405)

#     try:
#         r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
#         redis_key = f"cart:{request.user.id}"
#         body = json.loads(request.body)

#         item_key = body.get("key")
#         new_qty = int(body.get("quantity", 1))

#         existing = r.hget(redis_key, item_key)
#         if existing:
#             data = json.loads(existing)
#             data["quantity"] = new_qty
#             r.hset(redis_key, item_key, json.dumps(data))
#         else:
#             # if item missing create minimal entry
#             r.hset(redis_key, item_key, json.dumps({"quantity": new_qty, "product_id": item_key}))
        
#         # ✅ Forces Redis to respond updated values so removed items don't affect total
#         r.save()

#         # ✅ Return updated totals so UI summary is accurate and doesn't flash original values
#         cart_items = Cart.objects.filter(user=request.user)
#         subtotal = sum(Decimal(i.price) * i.quantity for i in cart_items)
#         delivery = sum(Decimal(i.product.delivery_charges or 0) for i in cart_items)
#         platform_fee = sum(Decimal(i.product.platform_fee or 0) for i in cart_items)
#         total_items = cart_items.aggregate(total=Sum('quantity'))['total'] or 0

#         return JsonResponse({
#             "status": "success",
#             "cart_items": list(cart_items.values()),
#             "order_summary": {
#                 "subtotal": float(subtotal),
#                 "delivery": float(delivery),
#                 "platform_fee": float(platform_fee),
#                 "total": float(subtotal + delivery + platform_fee)
#             },
#             "cart_count": total_items,
#             "item_count": total_items
#         })

#     except Exception as e:
#         return JsonResponse({"status":"error","message":str(e)}, status=400)




from django.views.decorators.http import require_POST
from django.http import JsonResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import redis
import json


import logging

logger = logging.getLogger(__name__)

@require_POST
@login_required
def remove_cart_item(request, item_id):
    try:
        # Initialize Redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
        redis_key = f"cart:{request.user.id}"
        
        # Get cart item first to determine its type
        cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
        
        # Use the SAME key format as in add_to_cart
        if cart_item.gift_set:
            item_key = f"giftset:{cart_item.gift_set.id}"
        elif cart_item.product_variant:
            item_key = f"variant:{cart_item.product_variant.id}"
        else:
            item_key = f"product:{cart_item.product.id}"
        
        # Delete from database FIRST
        cart_item.delete()
        
        # Then delete from Redis
        deleted = r.hdel(redis_key, item_key)
        logger.debug(f"Deleted {deleted} items from Redis")
        
        # Force immediate Redis sync
        r.save()
        
        # Get accurate count from BOTH sources
        db_items = Cart.objects.filter(user=request.user)
        db_count = db_items.count()
        db_total = db_items.aggregate(total=Sum('quantity'))['total'] or 0
        
        redis_items = r.hgetall(redis_key)
        redis_count = len(redis_items)
        redis_total = sum(
            json.loads(item_data).get('quantity', 1)
            for item_data in redis_items.values()
        ) if redis_items else 0
        
        # Final count should be from database only since we're using it as source of truth
        final_count = db_total
        
        # Clean up Redis if database is empty but Redis has items
        if db_count == 0 and redis_count > 0:
            r.delete(redis_key)
            logger.warning("Cleared Redis cart due to database mismatch")
            final_count = 0
        
        # Broadcast via WebSocket
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{request.user.id}_cart",
                {
                    "type": "cart.update",
                    "action": "remove",
                    "item_id": item_id,
                    "cart_count": final_count,
                    "is_empty": final_count == 0
                }
            )
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item removed successfully',
            'cart_count': final_count,
            'is_empty': final_count == 0
        })
        
    except Exception as e:
        logger.error(f"Error in remove_cart_item: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'cart_count': 0,
            'is_empty': True
        }, status=400)

@require_GET
def cart_count(request):
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0, 'status': 'unauthenticated'})

    try:
        # Use database as source of truth
        db_items = Cart.objects.filter(user=request.user)
        db_count = db_items.count()
        db_total = db_items.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Edge case: items exist but quantities sum to 0
        if db_total == 0 and db_count > 0:
            db_total = db_count
        
        # Clean up Redis if out of sync
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
        redis_key = f"cart:{request.user.id}"
        
        if db_total == 0 and r.exists(redis_key):
            r.delete(redis_key)
            logger.debug("Cleared Redis cart due to empty database")
        
        return JsonResponse({
            'count': db_total,
            'status': 'success',
            'source': 'database'  # Always use database as source of truth
        })

    except Exception as e:
        logger.error(f"Error in cart_count: {e}")
        return JsonResponse({
            'count': 0,
            'status': 'error',
            'message': str(e)
        })


# @require_POST
# @login_required(login_url='email_login')
# def apply_coupon(request):
#     code = request.POST.get('code')

#     try:
#         coupon = Coupon.objects.get(code=code, is_active=True)

#         if CouponUsage.objects.filter(user=request.user, coupon=coupon).exists():
#             return JsonResponse({
#                 "status": "error",
#                 "message": "Coupon already used"
#             })

#         request.session['applied_coupon'] = coupon.code
#         request.session['applied_coupon_discount'] = float(coupon.discount)

#         totals = calculate_cart_totals(request)

#         return JsonResponse({
#             "status": "success",
#             "message": "Coupon applied",
#             "totals": totals
#         })

#     except Coupon.DoesNotExist:
#         return JsonResponse({
#             "status": "error",
#             "message": "Invalid coupon"
#         })
# @require_POST
# @login_required(login_url='email_login')
# def remove_coupon(request):
#     request.session.pop('applied_coupon', None)
#     request.session.pop('applied_coupon_discount', None)

#     totals = calculate_cart_totals(request)

#     return JsonResponse({
#         "status": "success",
#         "message": "Coupon removed",
#         "totals": totals
#     })

@require_POST
@login_required(login_url='email_login')
def apply_coupon(request):
    code = request.POST.get('code', '').strip()

    try:
        coupon = Coupon.objects.get(code=code, is_active=True)

        # ❌ Already used
        if CouponUsage.objects.filter(user=request.user, coupon=coupon).exists():
            return JsonResponse({
                "status": "error",
                "message": "Coupon already used"
            })

        # ✅ Check minimum cart value
        totals_before = calculate_cart_totals(request)
        if totals_before["products_total"] < coupon.required_amount:
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
@login_required(login_url='email_login')
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



@login_required(login_url='email_login')
def apply_premium_offer(request):
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
            user=request.user,
            offer_code=offer.code
        ).exists():
            return JsonResponse({'status': 'error', 'message': "Offer already used."})

        # save session
        request.session['premium_offer_code'] = offer.code
        request.session['premium_offer_percentage'] = float(offer.percentage)

        PremiumOfferUsage.objects.create(
            user=request.user,
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


@login_required(login_url='email_login')
def remove_premium_offer(request):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': "Invalid request."})

    code = request.session.get('premium_offer_code')

    if not code:
        return JsonResponse({'status': 'error', 'message': "No premium offer applied."})

    PremiumOfferUsage.objects.filter(user=request.user, offer_code=code).delete()

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

@require_POST
@login_required(login_url='email_login')
def toggle_gift_wrap(request):
    gift_wrap_status = request.session.get('gift_wrap', False)
    new_status = not gift_wrap_status

    # Update session
    request.session['gift_wrap'] = new_status
    request.session.modified = True

    # Update all cart items for the logged-in user
    Cart.objects.filter(user=request.user).update(gift_wrap=new_status)

    return redirect(request.META.get('HTTP_REFERER', '/'))


import hashlib
import razorpay

@login_required(login_url='email_login')
def view_cart(request):
    from_video = request.GET.get('from_video')

    all_messages = messages.get_messages(request)
    error_messages = []
    success_messages = []
    applied_successfully = False
    premium_offer_removed = False

    cart_items = Cart.objects.filter(user=request.user).order_by('-created_at')
    selected_address_id = request.session.get('selected_address_id')
  
    address = None
    if selected_address_id:
        address = AddressModel.objects.filter(id=selected_address_id, user=request.user).first()
        print("address",address)
    else:
        address = AddressModel.objects.filter(user=request.user).last()


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
    used_coupons = CouponUsage.objects.filter(user=request.user).values_list('coupon__id', flat=True)
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

    total_price = current_cart_total + gift_wrap_display - discount
    print("Total price after coupon:", total_price)

    # Premium offer
    premium_discount = Decimal('0.00')
    premium_offer_visible = False
    welcome_offer_visible = False

    premium_offer_code = request.session.get('premium_offer_code')
    premium_offer_percentage = request.session.get('premium_offer_percentage')

    premium_base_amount = current_cart_total + gift_wrap_display - discount
    welcome_offer = PremiumFestiveOffer.objects.filter(
        is_active=True,
        premium_festival="Welcome").exists()
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


    total_price = premium_base_amount - premium_discount
    total_price = max(total_price, Decimal('0.00'))

    # Razorpay
    cart_hash_data = f"{request.user.id}_{total_items}_{float(total_price)}"
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

@csrf_exempt
@login_required(login_url="email_login")
def order_success(request):
    if request.method == "POST":
        user = request.user
        total_price = float(request.POST.get("total_price", 0))
        razorpay_payment_id = request.POST.get("razorpay_payment_id")
        razorpay_order_id = request.POST.get("razorpay_order_id")
        razorpay_signature = request.POST.get("razorpay_signature")
        selected_address_id = request.session.get("selected_address_id")

        # ✅ Fetch address
        address = AddressModel.objects.filter(
            id=selected_address_id, user=user
        ).first() if selected_address_id else AddressModel.objects.filter(user=user).last()

        # ✅ Prevent duplicate orders (same user + same price in last 5 mins)
        existing_order = Order.objects.filter(
            user=user,
            total_price=total_price,
            status="Completed",
            created_at__gte=timezone.now() - timedelta(minutes=5),
        ).first()

        if existing_order:
            order = existing_order
            print("⚠️ Using existing order to prevent duplicate:", order.id)
        else:
            try:
                # ✅ Verify Razorpay signature
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))
                client.utility.verify_payment_signature({
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature,
                })

                with transaction.atomic():
                    # ✅ Create order
                    order = Order.objects.create(
                        user=user,
                        address=address,
                        total_price=total_price,
                        status="Completed",
                    )

                    Payment.objects.create(
                        order=order,
                        payment_method="Razorpay",
                        status="Completed",
                        transaction_id=razorpay_payment_id,
                        price=total_price,
                    )

                    # ✅ Move cart → order items
                    cart_items = Cart.objects.filter(user=user)
                    cart_total_before_discount = sum(item.price * item.quantity for item in cart_items)

                    coupon_discount = Decimal(request.session.get("applied_coupon_discount", 0.00))
                    premium_discount_percentage = Decimal(request.session.get("premium_offer_percentage", 0.00))

                    for item in cart_items:
                        quantity = item.quantity
                        original_total = item.price * quantity
                        discounted_total = item.price * quantity if item.price else original_total

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

                        # ✅ Decrease stock
                        if item.product_variant:
                            item.product_variant.stock = max(item.product_variant.stock - item.quantity, 0)
                            item.product_variant.save()
                        elif item.gift_set:
                            item.gift_set.stock = max(item.gift_set.stock - item.quantity, 0)
                            item.gift_set.save()
                        elif item.product:
                            item.product.stock = max(item.product.stock - item.quantity, 0)
                            item.product.save()

                    cart_items.delete()

                    # ✅ Fire Celery tasks *after commit*
                    transaction.on_commit(lambda: create_shiprocket_order_task.delay(order.id))
                    transaction.on_commit(lambda: send_invoice_email_task.delay(user.id, order.id))
                    transaction.on_commit(lambda: notify_low_stock_task.delay(order.id))

            except razorpay.errors.SignatureVerificationError:
                return render(request, "user_panel/payment_failed.html", {"error": "Signature verification failed"})

        # ✅ Handle coupon usage
        coupon_code = request.session.pop("applied_coupon", None)
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                CouponUsage.objects.create(user=user, coupon=coupon)
            except Coupon.DoesNotExist:
                pass

        # ✅ Handle premium offer usage
        premium_offer_code = request.session.pop("premium_offer_code", None)
        if premium_offer_code:
            offer = PremiumFestiveOffer.objects.filter(code=premium_offer_code).first()
            if offer:
                PremiumOfferUsage.objects.create(user=user, offer_code=offer.code)
            request.session.pop("premium_offer_percentage", None)
            request.session.pop(f"premium_offer_used_{premium_offer_code}", None)

        # ✅ Clear unused session keys
        for key in ["gift_wrap", "razorpay_order_id", "razorpay_cart_hash"]:
            request.session.pop(key, None)

        messages.success(request, "🎉 Your order has been placed successfully!")

        return render(request, "user_panel/order_success.html", {"order": order})

    return redirect("view_cart")


def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect('email_login')

from django.db.models import Min, Max, Avg, Prefetch, Q
from django.views.decorators.http import require_GET
from django.http import JsonResponse

from django.db.models import Min, Max, Avg, Prefetch, Q
from django.views.decorators.http import require_GET
from django.http import JsonResponse

from django.db.models import Q, Min, Max, Avg
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Prefetch

@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()

    # Limit results for ultra-fast response time
    RESULT_LIMIT = 20

    # Preload category list (cached recommended)
    all_categories = list(
        Category.objects.only('id', 'name').values('id', 'name')
    )

    # Prefetch only minimal required fields
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

    # Search filter
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(sku__icontains=query)
        )

    # Category filter
    if category_id:
        products = products.filter(category_id=category_id)

    # LIMIT for fast search
    products = products[:RESULT_LIMIT]

    results = []

    for p in products:
        cat = p.category.name.lower().replace(" ", "").replace("-", "")

        # ===== PRICE HANDLING =====
        if cat == "giftsets" and p.gs:
            prices = [g.discounted_price or g.price for g in p.gs if g.price]
            originals = [g.original_price for g in p.gs if g.original_price]

        else:
            prices = [v.price for v in p.vars if v.price]
            originals = [v.original_price for v in p.vars if v.original_price]

        # Selling price formatting
        if prices:
            mn = min(prices)
            mx = max(prices)
            price_display = f"₹{mn}" if mn == mx else f"₹{mn} - ₹{mx}"
        else:
            price_display = "Price not available"

        # Original price formatting
        if originals:
            mn = min(originals)
            mx = max(originals)
            original_price_display = f"₹{mn}" if mn == mx else f"₹{mn} - ₹{mx}"
        else:
            original_price_display = "N/A"

        # ===== RATINGS =====
        ratings = [r.rating for r in p.revs if r.rating]
        avg_rating = round(sum(ratings)/len(ratings), 1) if ratings else 0.0
        rating_percentage = round((avg_rating / 5) * 100, 1)

        # ===== FINAL OUTPUT =====
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
    base_products = Product.objects.none()

    # -------- SECTION FILTER --------
    if section == "new-arrival":
        base_products = Product.objects.filter(is_new_arrival=True, is_active=True)
        title = "New Arrivals"
    elif section == "trending":
        base_products = Product.objects.filter(is_trending=True, is_active=True)
        title = "Trending Products"
    elif section == "best-seller":
        base_products = Product.objects.filter(is_best_seller=True, is_active=True)
        title = "Best Selling Products"
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
    wishlist_product_ids = []
    if request.user.is_authenticated:
        wishlist_product_ids = list(
            Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
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
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            
            # Save selected address ID for both billing and shipping
            request.session['selected_address_id'] = address.id
            request.session['billing_address_id'] = address.id
            request.session['shipping_address_id'] = address.id

            messages.success(request, "Address saved successfully!")
            return redirect('view_cart')
        else:
            print('jjjjjjj',form.errors)
    else:
        form = AddressForm()

    return render(request, 'user_panel/add_address.html', {'form': form})

def update_address(request, address_id):
    # item_id = request.GET.get('item_id')  

    try:
        address = AddressModel.objects.get(id=address_id, user=request.user)  # Get the address to update
    except AddressModel.DoesNotExist:
        # Handle case where address doesn't exist
        return HttpResponse('No Adreess Found')  
    
    if request.method == 'POST':
        if 'reset' in request.POST:
            form = AddressForm()
        form = AddressForm(request.POST, instance=address)  
        if form.is_valid():
            form.save()  
            request.session['selected_address_id'] = address.id  # or updated_address.id
            messages.success(request, "Address updated successfully!")

            return redirect('view_cart')  # Redirect back to the cart page
        else:
            print(form.errors)
    else:
        form = AddressForm(instance=address)  

    return render(request, 'user_panel/add_address.html', {'form': form,})

    
    
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
    

@login_required(login_url='email_login')
def user_profile(request):
    user = request.user
    name = request.user.username.split('@')[0]
    profile, _ = UserProfile.objects.get_or_create(user=user)

    orders = (
        Order.objects
        .filter(user=user)
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

    wishlist = Wishlist.objects.filter(user=user).select_related('product').prefetch_related(Prefetch('product__variants', queryset=ProductVariant.objects.filter(stock__gt=0)))

    for item in wishlist:
        variants = item.product.variants.all()

        if variants:
            cheapest_variant = min(
            variants,
            key=lambda v: v.price if v.price else float('inf')
        )
            item.variant_price = cheapest_variant.price
            item.variant_original_price = cheapest_variant.original_price
            item.variant_size = cheapest_variant.size
            item.variant_bottle = cheapest_variant.bottle_type
        else:
            item.variant_price = None

    addresses = AddressModel.objects.filter(user=user).order_by('-created_at')
    help_queries = HelpQuery.objects.filter(user=user).order_by('-created_at')



    default_address = addresses.first()

    ordered_product_ids = OrderItem.objects.filter(order__user=user).values_list('product_id', flat=True)
    product_reviews = Review.objects.filter(product_id__in=ordered_product_ids)

    avg_rating_dict = {
        item['product_id']: {
            'rating': round(item['avg_rating'], 1),
            'percentage': round((item['avg_rating'] / 5) * 100, 2)
        }
        for item in product_reviews.values('product_id').annotate(avg_rating=Avg('rating'))
    }

    reviewed_product_ids = list(
        product_reviews.filter(user=user).values_list('product_id', flat=True)
    )

    tracking_stages = ["AWB Assigned", "Pickup Generated", "Out for Pickup", "Delivered"]

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
        'user': user,
        'orders': orders,
        'wishlist': wishlist,
        'addresses': addresses,
        'help_queries': help_queries,
        'form': form,
        'avg_rating_dict': avg_rating_dict,
        'reviewed_product_ids': reviewed_product_ids,
        'tracking_stages': tracking_stages,
        'display_name': name,
        'default_address': default_address,
    })


@login_required(login_url='email_login')
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "Address added successfully!")
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url) 
            return redirect('view_cart')
    else:
        form = AddressForm()
    return render(request, 'user_panel/add_address.html', {'form': form})

@login_required(login_url='email_login')
def edit_address(request, address_id):
    address = get_object_or_404(AddressModel, id=address_id, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully!")
            return redirect('user_profile')
    else:
        form = AddressForm(instance=address)
    return render(request, 'user_panel/edit_address.html', {'form': form, 'address': address})

@login_required(login_url='email_login')
def delete_address(request, address_id):
    address = get_object_or_404(AddressModel, id=address_id, user=request.user)
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
            query.user = request.user
            query.save()
            messages.success(request, "Your query has been submitted successfully!")
            notify_admins(f"A new query has been submitted by {query.user.email}. Query: {query.message}",category='queries')
            return redirect('user_profile')
    else:
        form = HelpQueryForm()
    return render(request, 'user_panel/submit_query.html', {'form': form})



@login_required(login_url='email_login')
def user_help_chat(request, query_id):
    query = get_object_or_404(HelpQuery, id=query_id, user=request.user)

    return render(request, 'help_query_chat.html', {
        'query': query,
        'messages': query.messages.all(),
        'is_admin': False
    })

import os
import uuid

@csrf_exempt
@login_required(login_url='email_login')
def update_profile_picture(request):
    if request.method == 'POST':
        try:
            profile = UserProfile.objects.get(user=request.user)
            
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
            filename = f"{request.user.username}_{uuid.uuid4().hex[:8]}_{int(time.time())}.{ext}"
            
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

@login_required(login_url='email_login')
def product_list(request):
    products = Product.objects.all()
    wishlist_product_ids = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
    return render(request, 'home3.html', {
        'products': products,
        'wishlist_product_ids': list(wishlist_product_ids)
    })



@require_POST
@login_required(login_url='email_login')
def add_to_wishlist(request):
    product_id = request.POST.get('product_id')
    product = Product.objects.get(id=product_id)
    Wishlist.objects.get_or_create(user=request.user, product=product)

    # update count in DB + Redis
    count = Wishlist.objects.filter(user=request.user).count()
    cache.set(f"wishlist_count_{request.user.id}", count, timeout=None)

    # notify via Channels (pub/sub)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"wishlist_{request.user.id}",
        {"type": "wishlist_update", "count": count}
    )

    return JsonResponse({'success': True, 'count': count})

from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
@require_POST
@login_required(login_url='email_login')
def remove_from_wishlist(request):
    product_id = request.POST.get('product_id')
    product = Product.objects.get(id=product_id)
    Wishlist.objects.filter(user=request.user, product=product).delete()

    count = Wishlist.objects.filter(user=request.user).count()
    cache.set(f"wishlist_count_{request.user.id}", count, timeout=None)

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"wishlist_{request.user.id}",
        {"type": "wishlist_update", "count": count}
    )

    return JsonResponse({'success': True, 'count': count})



@csrf_exempt
@login_required(login_url='email_login')
def update_dob(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        dob_str = data.get('dob')
        try:
            dob = datetime.strptime(dob_str, "%d-%m-%Y").date()
            profile = UserProfile.objects.get(user=request.user)
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
    # Example: assume latest order by logged-in user
    try:
        user = request.user
        order = Order.objects.filter(user=user).latest('created_at')  # adjust field if needed
        address = AddressModel.objects.filter(user=user).latest('created_at')  # Or order.address if you store it
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

@login_required(login_url='email_login')
def order_tracking_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
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





@login_required(login_url='email_login')
def download_invoices(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
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


def send_invoice_email(user, order):
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
        invoice_url = data["invoice_url"]

        # Download the invoice PDF
        invoice_response = requests.get(invoice_url)
        if invoice_response.status_code == 200:
            email = EmailMessage(
                subject='Your Order Invoice',
                body='Thank you for your order. Please find your invoice attached.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach(f'invoice_{order.id}.pdf', invoice_response.content, 'application/pdf')
            email.send()


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
                  <h2 style="color:#d63384; text-align:center;">Welcome to Perfumavalley 🌸</h2>
                  <p>Hi <b>{subscription.name or subscription.email}</b>,</p>
                  <p>Thank you for subscribing to <span style="color:#d63384;">Perfumavalley</span>! ✨</p>
                  <p>You'll now receive exclusive updates, special offers, and the latest fragrances straight to your inbox.</p>
                  <div style="text-align:center; margin:20px 0;">
                    <a href="https://perfumevalleyworld.com/"
                       style="background:#d63384; color:#fff; padding:12px 24px; text-decoration:none; font-size:16px; border-radius:6px;">
                      Explore Collection
                    </a>
                  </div>
                  <p style="font-size:14px; color:#777; text-align:center;">
                    Stay connected with us 💖<br>
                    <a href="https://www.instagram.com/perfumevalley.store/" style="color:#d63384; text-decoration:none;">Instagram</a> |
                    <a href="https://www.facebook.com/Perfumevalley.store/" style="color:#d63384; text-decoration:none;">Facebook</a>
                  </p>
                  <hr style="margin:20px 0; border:0; border-top:1px solid #eee;">
                  <p style="font-size:12px; color:#aaa; text-align:center;">
                    © 2025 Perfumavalley. All rights reserved.
                  </p>
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



@login_required(login_url='email_login')
def write_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # ✅ Ensure user purchased the product
    has_purchased = OrderItem.objects.filter(
        order__user=request.user,
        product=product
    ).exists()

    if not has_purchased:
        return HttpResponseForbidden("You can only review products you've purchased.")

    # ✅ Check if already reviewed this product
    already_reviewed = Review.objects.filter(user=request.user, product=product).exists()
    if already_reviewed:
        messages.error(request, "You've already reviewed this product.")
        return redirect('product_detail', product_id=product.id)

    # ✅ Handle form submission
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
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