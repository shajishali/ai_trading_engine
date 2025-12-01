from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    path('api/symbols/', views.get_symbols, name='get_symbols'),
]
