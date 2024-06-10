from django.contrib import admin
from social_media.models import Post, Profile, Comment, Like, FollowingRelationships

admin.site.register(Profile)
admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Like)
admin.site.register(FollowingRelationships)
