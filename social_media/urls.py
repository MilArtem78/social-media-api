from django.urls import path, include
from rest_framework.routers import DefaultRouter
from social_media.views import (
    ProfileViewSet,
    CurrentUserProfileView,
)

router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profiles")


urlpatterns = [
    path("", include(router.urls)),
    path("me/", CurrentUserProfileView.as_view(), name="me"),
]

app_name = "social_media"
