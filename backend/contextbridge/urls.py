from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from contextbridge_app.views import health

urlpatterns = [
    path('health/', health, name='health'),
    path('admin/', admin.site.urls),
    path('api/', include('contextbridge_app.urls')),
]

# Uploaded documents are private (served only via authenticated API),
# so media is exposed only for local debugging.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
