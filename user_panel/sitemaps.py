# user_panel/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from admin_panel.models import Product, Category, Subcategory

# 1️⃣ Static Pages
class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ['home', 'all_view','user_profile','privacy_policy','contact','privacy_policy','terms_and_conditions','about','store_locator','view_cart']  # names from urls.py

    def location(self, item):
        return reverse(item)

class ViewAllSitemap(Sitemap):
    priority = 0.8
    changefreq = "daily"

    def items(self):
        return ['best-seller', 'new-arrival', 'trending','shopbyocassions']  # all your sections

    def location(self, item):
        return reverse('viewall_products', kwargs={'section': item})


# 2️⃣ Category Pages
class CategorySitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()

# 3️⃣ Subcategory Pages
class SubcategorySitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Subcategory.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()

# 4️⃣ Product Pages
class ProductSitemap(Sitemap):
    priority = 0.9
    changefreq = "daily"

    def items(self):
        return Product.objects.all()

    def location(self, obj):
        return f"/product/{obj.id}/"
