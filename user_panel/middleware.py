# user_panel/middleware.py

from django.contrib.auth import logout
from django.shortcuts import redirect

class BlockedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            if not user.is_active:  # Or use user.userprofile.is_blocked if applicable
                logout(request)
                return redirect('blocked_user')  # Make sure this URL exists
        return self.get_response(request)


from user_panel.models import Cart

def sanitize_cart(user):
    if not user or not user.is_authenticated:
        return
    Cart.objects.filter(user=user, product__isnull=True).delete()


class CartCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        user = request.user

        # Run only for logged-in users
        if user.is_authenticated:
            sanitize_cart(user)

        return self.get_response(request)
