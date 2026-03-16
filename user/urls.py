from django.urls import path
from . import views

app_name = 'user'

urlpatterns = [
    path('list/', views.UserListView.as_view(), name='user_list'),
    path('create/', views.UserCreateView.as_view(), name='user_create'),
    path('<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('<uuid:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('<uuid:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('company/license/', views.CompanyLicenseView.as_view(), name='company_license'),
]
