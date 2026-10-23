from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    path('',                          views.transaction_list_view, name='list'),
    path('<int:pk>/pay/',             views.mark_paid_view,        name='mark_paid'),
    path('<int:pk>/pay-online/',      views.checkout_view,         name='pay_online'),
    path('<int:pk>/result/<str:outcome>/', views.payment_result_view, name='payment_result'),
    path('webhook/paymongo/',         views.webhook_view,          name='webhook'),
]