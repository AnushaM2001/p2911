# in some utils.py or decorators.py file
from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from admin_panel.models import Review, Order

def require_last_order_review(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            last_order = Order.objects.filter(user=request.user).order_by('-created_at').first()
            if last_order:
                for item in last_order.items.all():
                    has_review = Review.objects.filter(user=request.user, product=item.product).exists()
                    if not has_review:
                        review_url = reverse("write_review", args=[item.product.id])
                        
                        # Handle AJAX calls
                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            return JsonResponse({
                                "status": "review_required",
                                "message": f"Please review your last purchased product ({item.product.name}) before adding new items.",
                                'open_modal': True
                            }, status=403)
                        
                        # Normal request → redirect
                        return redirect(review_url)

        # If everything fine → proceed
        return view_func(request, *args, **kwargs)
    return wrapper
