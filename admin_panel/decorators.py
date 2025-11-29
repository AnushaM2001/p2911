from django.shortcuts import redirect

def admin_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_id'):
            return redirect('admin_login')  # your named URL
        return view_func(request, *args, **kwargs)
    return wrapper
