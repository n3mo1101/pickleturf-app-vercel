from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('',          views.home_view,          name='home'),
    path('offline/',  views.offline_view,        name='offline'),
    path('sw.js',     views.service_worker_view, name='sw'),
]