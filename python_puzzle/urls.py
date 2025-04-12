"""
URL configuration for python_puzzle project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from puzzle.admin import custom_admin_site

urlpatterns = [
    # Default Django Admin
    path('admin/', admin.site.urls),

    # Custom Admin Panel
    path('custom-admin/', custom_admin_site.urls),

    # Puzzle App URLs
    path('', include('puzzle.urls')),

    # Authentication URLs
    path('accounts/', include('django.contrib.auth.urls')),
]

# Serving media files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
