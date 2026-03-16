from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
    path('save-config/', views.SaveConfigView.as_view(), name='save_config'),
    path('model-optimization/', views.ModelOptimizationView.as_view(), name='model_optimization'),
    path('model-optimization/convert/', views.StartConversionView.as_view(), name='start_conversion'),
    path('model-optimization/status/<int:pk>/', views.ArtifactStatusView.as_view(), name='artifact_status'),
]
