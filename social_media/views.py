from django.db.models import Count, OuterRef, Exists, Q, Subquery
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import (
    get_object_or_404,
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from social_media.models import Profile, FollowingRelationships, Post, Like, Comment
from social_media.permissions import IsAuthorOrReadOnly
from social_media.serializers import (
    ProfileListSerializer,
    ProfileSerializer,
    ProfileDetailSerializer,
    FollowerRelationshipSerializer,
    FollowingRelationshipSerializer,
    PostListSerializer,
    PostDetailSerializer,
    PostImageSerializer,
    PostSerializer,
    CommentSerializer,
)


class CurrentUserProfileView(RetrieveUpdateDestroyAPIView):
    serializer_class = ProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Profile.objects.filter(user=self.request.user)
            .select_related("user")
            .annotate(
                followers_count=Count("followers", distinct=True),
                following_count=Count("following", distinct=True),
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

    def get_serializer_class(self):
        if self.action == "list":
            return ProfileListSerializer
        if self.action == "retrieve":
            return ProfileDetailSerializer
        return ProfileListSerializer

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

    @action(
        detail=True,
        methods=["POST"],
        url_path="follow",
        permission_classes=[IsAuthenticated],
        authentication_classes=[JWTAuthentication],
    )
    def follow(self, request, pk=None):
        follower = get_object_or_404(Profile, user=request.user)
        following = get_object_or_404(Profile, pk=pk)

        if follower == following:
            return Response(
                {"detail": "You cannot follow yourself."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if FollowingRelationships.objects.filter(
            follower=follower, following=following
        ).exists():
            return Response(
                {"detail": "You are already following this user."},
                status=status.HTTP_409_CONFLICT,
            )

        FollowingRelationships.objects.create(follower=follower, following=following)
        return Response(
            {"detail": "You started following this user."},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["POST"],
        url_path="unfollow",
        permission_classes=[IsAuthenticated],
        authentication_classes=[JWTAuthentication],
    )
    def unfollow(self, request, pk=None):
        follower = get_object_or_404(Profile, user=request.user)
        following = get_object_or_404(Profile, pk=pk)

        try:
            relation = FollowingRelationships.objects.get(
                Q(follower=follower) & Q(following=following)
            )
            relation.delete()
            return Response(
                {"detail": "You have unfollowed this user."},
                status=status.HTTP_204_NO_CONTENT,
            )
        except FollowingRelationships.DoesNotExist:
            return Response(
                {"detail": "You are not following this user."},
                status=status.HTTP_404_NOT_FOUND,
            )


class ProfileFollowersView(ListAPIView):
    serializer_class = FollowerRelationshipSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return user.profile.followers.all()


class ProfileFollowingView(ListAPIView):
    serializer_class = FollowingRelationshipSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return user.profile.following.all()


class PostViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.action == "list":
            return PostListSerializer
        if self.action == "retrieve":
            return PostDetailSerializer
        if self.action == "upload_image":
            return PostImageSerializer
        return PostSerializer

    def get_queryset(self):
        user_profile = self.request.user.profile
        queryset = Post.objects.select_related("author").annotate(
            liked_by_user=Exists(
                Like.objects.filter(profile=user_profile, post=OuterRef("pk"))
            ),
        )

        content = self.request.query_params.get("content")
        author_username = self.request.query_params.get("author_username")

        if author_username is not None:
            queryset = queryset.filter(author__username__icontains=author_username)

        if content is not None:
            queryset = queryset.filter(content__icontains=content)

        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user.profile)

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-image",
    )
    def upload_image(self, request, pk=None):
        """Endpoint to upload an image to a post"""
        post = self.get_object()
        serializer = self.get_serializer(post, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Image uploaded successfully."},
            status=status.HTTP_200_OK,
        )

    @action(
        methods=["POST"],
        detail=True,
        url_path="like",
    )
    def like(self, request, pk=None):
        """Endpoint to like a post"""
        post = get_object_or_404(Post, pk=pk)
        user_profile = request.user.profile

        if post.author == user_profile:
            return Response(
                {"detail": "You cannot like your post."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Like.objects.filter(profile=user_profile, post=post).exists():
            return Response(
                {"detail": "You have already liked this post."},
                status=status.HTTP_409_CONFLICT,
            )
        Like.objects.create(profile=user_profile, post=post)
        return Response({"detail": "You liked this post."}, status=status.HTTP_200_OK)

    @action(
        methods=["POST"],
        detail=True,
        url_path="unlike",
    )
    def unlike(self, request, pk=None):
        """Endpoint to unlike a post"""
        post = get_object_or_404(Post, pk=pk)
        user_profile = request.user.profile
        try:
            like = Like.objects.get(profile=user_profile, post=post)
            like.delete()
            return Response(
                {"detail": "You unliked this post."},
                status=status.HTTP_200_OK,
            )
        except Like.DoesNotExist:
            return Response(
                {"detail": "You have not liked this post."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(
        methods=["GET"],
        detail=False,
        url_path="my-posts",
    )
    def my_posts(self, request):
        """Endpoint to get all posts from the user"""
        user_profile = request.user.profile
        queryset = self.get_queryset().filter(author=user_profile)
        serializer = PostListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        methods=["GET"],
        detail=False,
        url_path="feed",
    )
    def feed(self, request):
        """Endpoint to get all posts from followed users"""
        user_profile = request.user.profile
        followed_profiles = user_profile.following.values_list("following", flat=True)
        queryset = self.get_queryset().filter(author__in=followed_profiles)
        serializer = PostListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        methods=["GET"],
        detail=False,
        url_path="liked",
    )
    def liked(self, request):
        """Endpoint to get all posts liked by the user"""
        user_profile = request.user.profile
        queryset = self.get_queryset().filter(likes__profile=user_profile)
        serializer = PostListSerializer(queryset, many=True)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]

    def get_queryset(self):
        queryset = Comment.objects.select_related("author", "post").filter(
            post_id=self.kwargs["post_id"]
        )
        return queryset

    def perform_create(self, serializer):
        post = get_object_or_404(Post, id=self.kwargs.get("post_id"))
        serializer.save(author=self.request.user.profile, post=post)
