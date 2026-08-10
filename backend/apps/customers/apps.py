from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.customers"
    label = "customers"
    verbose_name = "Customers (CRM)"

    def ready(self):
        import apps.customers.signals  # noqa: F401
