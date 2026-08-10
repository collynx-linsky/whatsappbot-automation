from django.apps import AppConfig


class MessagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.messages"
    # NOTE: must NOT be "messages" — that label already belongs to
    # django.contrib.messages (installed for the admin/messages framework).
    # Using the same label would crash app-registry population at startup.
    label = "messaging"
    verbose_name = "Messages"
