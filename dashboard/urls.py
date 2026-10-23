from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',         views.index,     name='index'),
    path('export/',  views.export_csv, name='export_csv'),
]