from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from django.conf import settings
from django.conf.urls.static import static


schema_view = get_schema_view(
    openapi.Info(
        title="Suthar Backend API",
        default_version='v1',
        description="API documentation for admin and user",
        contact=openapi.Contact(email="support@example.com"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [

    # ✅ DEFAULT ROOT → REDIRECT TO SWAGGER
    path('', RedirectView.as_view(url='/swagger/', permanent=False)),

    # Admin
    path('admin/', admin.site.urls),

    # APIs
    path('api/users/', include('users.urls')),
    path('api/auth/', include('authapp.urls')),
    path('api/profiles/', include('profiles.urls')),
    path('api/community/', include('community.urls')),
    path('api/members/', include('members.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/home/', include('dashboard.urls')),

    # ✅ FIXED SWAGGER URL
    path(r'swagger(?P<format>\.json|\.yaml)', 
         schema_view.without_ui(cache_timeout=0), 
         name='schema-json'),

    path('swagger/', 
         schema_view.with_ui('swagger', cache_timeout=0), 
         name='schema-swagger-ui'),

    path('redoc/', 
         schema_view.with_ui('redoc', cache_timeout=0), 
         name='schema-redoc'),
]


# ✅ MEDIA FILES (LOCAL)
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )