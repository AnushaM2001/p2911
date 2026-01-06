from django.core.management.base import BaseCommand
from django.utils.text import slugify
from admin_panel.models import Subcategory

class Command(BaseCommand):
    help = "Fix NULL slugs in Subcategory"

    def handle(self, *args, **options):
        subs = Subcategory.objects.filter(slug__isnull=True)
        updated = 0

        for sub in subs:
            base_slug = slugify(sub.name)
            slug = base_slug
            counter = 1

            while Subcategory.objects.filter(slug=slug).exclude(id=sub.id).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            Subcategory.objects.filter(id=sub.id).update(slug=slug)
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} subcategory slugs"))
