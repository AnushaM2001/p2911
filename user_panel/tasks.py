from celery import shared_task

@shared_task
def test_task(name):
    print(f"Hello {name} from Celery!")
    return f"Task completed for {name}"
