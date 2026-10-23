from django.urls import path
from . import views

app_name = 'announcements'

urlpatterns = [
    path('admin/',                  views.admin_list_view,     name='admin_list'),
    path('admin/new/',              views.admin_create_view,   name='admin_create'),
    path('admin/<int:pk>/edit/',    views.admin_edit_view,     name='admin_edit'),
    path('admin/<int:pk>/takedown/', views.admin_takedown_view, name='admin_takedown'),
    path('admin/<int:pk>/delete/',       views.admin_delete_view,  name='admin_delete'),
]