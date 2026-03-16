from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.AnalyticsOverviewView.as_view(), name='overview'),
    path('video/<uuid:job_id>/', views.VideoDetailAnalyticsView.as_view(), name='detail'),
    path('csv/<uuid:job_id>/', views.DownloadCSVView.as_view(), name='download_csv'),
]
