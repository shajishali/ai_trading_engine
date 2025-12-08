from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard-signals/', views.signals_view, name='signals'),  # Changed from signals/ to dashboard-signals/
    path('settings/', views.settings_view, name='settings'),
    path('api/stats/', views.api_dashboard_stats, name='api_stats'),
]
