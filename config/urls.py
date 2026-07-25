from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health, name="health"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.catalog.urls")),
]
