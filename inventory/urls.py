# inventory/urls.py

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Customer
    path('shop/',                          views.shop_view,                name='shop'),

    # Admin — POS & Sales
    path('admin/pos/',                     views.admin_pos_view,           name='admin_pos'),
    path('admin/sales/',                   views.admin_sale_list_view,     name='admin_sale_list'),
    path('admin/sales/<int:pk>/',          views.admin_sale_detail_view,   name='admin_sale_detail'),

    # Admin — Items
    path('admin/',                         views.admin_item_list_view,     name='admin_list'),
    path('admin/new/',                     views.admin_item_create_view,   name='admin_create'),
    path('admin/<int:pk>/',               views.admin_item_detail_view,   name='admin_detail'),
    path('admin/<int:pk>/edit/',          views.admin_item_edit_view,     name='admin_edit'),
    path('admin/<int:pk>/delete/',        views.admin_item_delete_view,   name='admin_delete'),
    path('admin/<int:pk>/stock/',         views.admin_stock_adjust_view,  name='admin_stock'),

    # Admin — Rentals
    path('admin/rentals/',                  views.admin_rental_list_view,   name='admin_rental_list'),
    path('admin/rentals/new/',              views.admin_rental_pos_view,    name='admin_rental_pos'),
    path('admin/rentals/<int:pk>/return/',  views.admin_rental_return_view, name='admin_return'),

    # Admin — Categories
    path('admin/categories/',             views.admin_category_list_view,   name='admin_categories'),
    path('admin/categories/new/',         views.admin_category_create_view, name='admin_category_create'),
    path('admin/categories/<int:pk>/edit/', views.admin_category_edit_view, name='admin_category_edit'),
]