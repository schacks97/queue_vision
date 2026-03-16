from django.urls import path
from . import views

app_name = 'detecter'

urlpatterns = [
    path('', views.UploadView.as_view(), name='upload'),
    path('roi/<uuid:job_id>/', views.SelectROIView.as_view(), name='select_roi'),
    path('start/<uuid:job_id>/', views.StartProcessingView.as_view(), name='start_processing'),
    path('status/<uuid:job_id>/', views.StatusView.as_view(), name='status'),
    path('status/<uuid:job_id>/api/', views.JobStatusAPIView.as_view(), name='job_status_api'),
    path('stream/<uuid:job_id>/', views.stream_inference, name='stream'),
    path('results/<uuid:job_id>/', views.ResultsView.as_view(), name='results'),
]
