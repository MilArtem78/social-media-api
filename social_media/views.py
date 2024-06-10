from django.db.models import Count, OuterRef, Exists, Q
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from social_media.models import Profile, FollowingRelationships
from social_media.serializers import ProfileListSerializer, ProfileSerializer


class CurrentUserProfileView(RetrieveUpdateDestroyAPIView):
    serializer_class = ProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Profile.objects.filter(user=self.request.user)
            .select_related("user")
            .prefetch_related("following", "followers")
            .annotate(
                followers_count=Count("followers"), following_count=Count("following")
            )
        )

    def get_object(self):
        return get_object_or_404(self.get_queryset())

    def destroy(self, request, *args, **kwargs):
        profile = self.get_object()
        user = profile.user
        response = super().destroy(request, *args, **kwargs)
        user.delete()
        return response


class ProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileListSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset

        username = self.request.query_params.get("username")
        first_name = self.request.query_params.get("first_name")
        last_name = self.request.query_params.get("last_name")

        if username:
            queryset = queryset.filter(username__icontains=username)

        if first_name:
            queryset = queryset.filter(first_name__icontains=first_name)

        if last_name:
            queryset = queryset.filter(last_name__icontains=last_name)

        return queryset
