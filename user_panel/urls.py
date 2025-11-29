from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
        path('a/',views.a,name='a'),
        path('products/<str:section>/', views.viewall_products, name='viewall_products'),
    # path('category/<int:category_id>/', views.subcategories, name='subcategories'),
    # path('subcategory/<int:subcategory_id>/', views.products, name='products'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
   

    path('order/success/', views.order_success, name='order_success'),
    path('toggle-gift-wrap/', views.toggle_gift_wrap, name='toggle_gift_wrap'),
      # path("order/success/<int:order_id>/", views.order_success_page, name="order_success_page"),



    # path('register/', views.register, name='register'),
    # path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('login/', views.send_otp_view, name='email_login'),
    path('verify/', views.verify_otp_view, name='verify_email_otp'),
    path('blocked/', views.blocked_user_view, name='blocked_user'),
    path('sub_add',views.subscription_add,name='sub_add'),

    path('products/', views.filtered_products, name='products_list'),
    path('products/category/<int:category_id>/', views.filtered_products, name='category_products'),
    path('products/subcategory/<int:subcategory_id>/', views.filtered_products, name='subcategory_products'),
    path('products/category/<int:category_id>/subcategory/<int:subcategory_id>/', views.filtered_products, name='category_subcategory_products'),
    path('viewall/<str:section>/', views.viewall_products, name='viewall_products'),
    path("toggle-wishlist/", views.toggle_wishlist, name="toggle_wishlist"),


    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('international-order/', views.international_order, name='international_order'),
    path('international-order/success/', views.international_order_success, name='international_order_success'),

    
    path('cart/', views.view_cart, name='view_cart'),
    path('update-cart-item/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('remove-cart-item/<int:item_id>/', views.remove_cart_item, name='remove_cart_item'),
    path('ajax/search/', views.search_suggestions, name='search_suggestions'),
    path('disclaimer/',views.disclaimer,name="disclaimer"),

    path('home/',views.home1,name='home'),
    path('',views.progress,name='progress'),

    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),

    path('add_address/',views.user_address,name='add_address'),

    path('update-address/<int:address_id>/', views.update_address, name='update_address'),
        # path('save-card/', views.save_card, name='save_card'),

#  path('products/', views.product_list, name='product_list'),
    path('ajax/filter-products/', views.ajax_filter_products, name='ajax_filter_products'),
   path('remove-coupon/', views.remove_coupon, name='remove_coupon'),

    path('apply-premium-coupon/', views.apply_premium_offer, name='apply_premium_coupon'),
    path('remove-premium-coupon/', views.remove_premium_offer, name='remove_premium_offer'),

    path('video/<int:video_id>/', views.video_detail, name='video_detail'),


    
    path('user-profile/', views.user_profile, name='user_profile'),
    path('address/add/', views.add_address, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('address/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    path('help/submit/', views.submit_help_query, name='submit_help_query'),
    path('help/query/<int:query_id>/', views.view_help_query, name='view_help_query'),
    path('profile/update-picture/', views.update_profile_picture, name='update_profile_picture'),
    path('wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    path('profile/update-dob/', views.update_dob, name='update_dob'),
    #shipping==============================
    path('shiprocket_order_result_view/',views.shiprocket_order_result_view,name='shiprocket_order_result_view'),
    # urls.py
    path('order/<int:order_id>/tracking/', views.order_tracking_view, name='order_tracking'),
    path('order/<int:order_id>/download-invoice/', views.download_invoice, name='download_invoice'),

    path('stores/', views.store_locator, name='store_locator'),
    path('about/', views.about_us, name='about'),
    path('terms_and_conditions/',views.terms_and_conditions,name='terms_and_conditions'),
    path('contact/',views.contact_us,name='contact'),

    path('privacy_policy/',views.privacy_policy,name='privacy_policy'),
    path('all_view/',views.all_view,name='all_view'),

    path('product/<int:product_id>/ratings/', views.write_review, name='write_review'),

   path('api/cart/count/', views.cart_count, name='cart_count'),

  path('help/send-message/<int:query_id>/', views.send_help_query_message, name='send_help_query_message'),




]
if settings.DEBUG: 

         urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

