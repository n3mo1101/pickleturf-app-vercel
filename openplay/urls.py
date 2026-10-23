from django.urls import path
from . import views

app_name = 'openplay'

urlpatterns = [
    # Customer
    path('',                    views.session_list_view,   name='list'),
    path('<int:pk>/',           views.session_detail_view, name='detail'),
    path('<int:pk>/join/',      views.join_session_view,   name='join'),
    path('<int:pk>/leave/',     views.leave_session_view,  name='leave'),

    # Admin
    path('admin/',                              views.admin_session_list_view,    name='admin_list'),
    path('admin/new/',                          views.admin_session_create_view,  name='admin_create'),
    path('admin/<int:pk>/',                     views.admin_session_detail_view,  name='admin_detail'),
    path('admin/<int:pk>/edit/',                views.admin_session_edit_view,    name='admin_edit'),
    path('admin/<int:pk>/complete/',            views.admin_session_complete_view,name='admin_complete'),
    path('admin/<int:pk>/cancel/',              views.admin_session_cancel_view,  name='admin_cancel'),
    path('admin/<int:pk>/add/',                 views.admin_add_participant_view, name='admin_add'),
    path('admin/<int:pk>/approve/<int:participant_id>/', views.admin_approve_view, name='admin_approve'),
    path('admin/<int:pk>/reject/<int:participant_id>/',  views.admin_reject_view,  name='admin_reject'),
]