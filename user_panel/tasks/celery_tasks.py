# user_panel/tasks/celery_tasks.py
from celery import shared_task
from user_panel.tasks.snapshots import build_snapshot_for_category

@shared_task
def rebuild_snapshot_task(cat_id):
    build_snapshot_for_category(cat_id)
    return True

@shared_task
def rebuild_all_categories_task():
    from user_panel.models import Category
    build_snapshot_for_category(None)
    for cid in Category.objects.values_list("id", flat=True):
        build_snapshot_for_category(cid)
    return True
