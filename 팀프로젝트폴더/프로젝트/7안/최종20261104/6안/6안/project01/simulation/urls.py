from django.urls import path

from . import views

app_name = "simulation"

urlpatterns = [
    path(
        "<uuid:run_id>/replay/",
        views.replay,
        name="replay",
    ),
]