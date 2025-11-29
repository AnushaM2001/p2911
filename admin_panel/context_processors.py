from .models import AdminUser

def admin_context(request):
    admin = None
    if request.session.get('admin_id'):
        try:
            admin = AdminUser.objects.get(id=request.session['admin_id'])
        except AdminUser.DoesNotExist:
            pass
    return {'logged_in_admin': admin}
