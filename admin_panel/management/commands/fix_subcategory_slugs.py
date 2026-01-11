# from django.utils.text import slugify
# from user_panel.models import Category, Subcategory

# # ---------- FIX CATEGORY SLUGS ----------
# for c in Category.objects.filter(slug__isnull=True):
#     base = slugify(c.name)
#     slug = base
#     i = 1
#     while Category.objects.filter(slug=slug).exclude(id=c.id).exists():
#         slug = f"{base}-{i}"
#         i += 1
#     c.slug = slug
#     c.save(update_fields=["slug"])

# # ---------- FIX SUBCATEGORY SLUGS ----------
# for s in Subcategory.objects.filter(slug__isnull=True):
#     base = slugify(s.name)
#     slug = base
#     i = 1
#     while Subcategory.objects.filter(slug=slug).exclude(id=s.id).exists():
#         slug = f"{base}-{i}"
#         i += 1
#     s.slug = slug
#     s.save(update_fields=["slug"])

# print("✅ All NULL slugs fixed")
