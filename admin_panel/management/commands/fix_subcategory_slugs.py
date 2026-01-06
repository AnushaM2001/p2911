# admin_panel/management/commands/fix_all_slugs.py

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from admin_panel.models import Category, Subcategory
from django.conf import settings

class Command(BaseCommand):
    help = "Fix all category and subcategory slugs with SEO suffix"

    def handle(self, *args, **options):
        SEO_SUFFIX = "store-for-men-and-women-in-india"
        updated_categories = 0
        updated_subcategories = 0

        # --------- UPDATE CATEGORIES ----------
        categories = Category.objects.all()
        for cat in categories:
            base_slug = slugify(cat.name)
            slug = f"{base_slug}-{SEO_SUFFIX}"
            counter = 1

            while Category.objects.filter(slug=slug).exclude(id=cat.id).exists():
                slug = f"{base_slug}-{counter}-{SEO_SUFFIX}"
                counter += 1

            cat.slug = slug
            cat.save()
            updated_categories += 1

        # --------- UPDATE SUBCATEGORIES ----------
        subcategories = Subcategory.objects.all()
        for sub in subcategories:
            base_slug = slugify(sub.name)
            slug = f"{base_slug}-{SEO_SUFFIX}"
            counter = 1

            while Subcategory.objects.filter(slug=slug).exclude(id=sub.id).exists():
                slug = f"{base_slug}-{counter}-{SEO_SUFFIX}"
                counter += 1

            sub.slug = slug
            sub.save()
            updated_subcategories += 1

        self.stdout.write(self.style.SUCCESS(
            f"Updated {updated_categories} category slugs and {updated_subcategories} subcategory slugs"
        ))
