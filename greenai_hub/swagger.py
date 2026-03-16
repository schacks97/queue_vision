from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.urls import path, include

schema_view = get_schema_view(
    openapi.Info(
        title="QueueVision API",
        default_version='v1',
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url='https://sandbox.e-n.live',
    patterns=[
        # path('api/v1/payments/', include('api.payments.urls'))
    ],
)