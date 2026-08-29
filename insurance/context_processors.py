"""Template context processors shared across the site."""


def notifications(request):
    """Expose the current user's unread notifications to every template.

    Populated once the notification feature is available; returns empty
    values otherwise so templates can rely on the keys existing.
    """
    unread = []
    count = 0
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        try:
            from insurance.models import Notification

            qs = Notification.objects.filter(user=user, is_read=False)
            count = qs.count()
            unread = list(qs[:10])
        except Exception:
            # Model/table not migrated yet — fail safe.
            unread, count = [], 0
    return {"unread_notifications": unread, "unread_notification_count": count}
