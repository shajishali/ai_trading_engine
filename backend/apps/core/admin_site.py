"""
Custom Admin Site Configuration
Provides branded admin interface with enhanced features
"""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.db.models import Count, Q, Sum
from django.utils import timezone
from datetime import timedelta

from apps.subscription.models import UserProfile, Payment, SubscriptionPlan
from apps.signals.models import TradingSignal, SignalAlert
from apps.trading.models import Symbol


class CustomAdminSite(admin.AdminSite):
    """Custom admin site with enhanced features"""
    
    site_header = "AI Trading Signal Engine"
    site_title = "CryptAI Admin"
    index_title = "Dashboard"
    
    def get_urls(self):
        """Add custom URLs for dashboard and reports"""
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='admin_dashboard'),
            path('reports/', self.admin_view(self.reports_view), name='admin_reports'),
            path('reports/generate/', self.admin_view(self.generate_report_view), name='admin_generate_report'),
            path('reports/export/', self.admin_view(self.export_report_view), name='admin_export_report'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Custom dashboard view with statistics"""
        context = {
            **self.each_context(request),
            'title': 'Admin Dashboard',
            'stats': self.get_dashboard_statistics(),
            'recent_activity': self.get_recent_activity(),
        }
        return TemplateResponse(request, 'admin/dashboard.html', context)
    
    def get_dashboard_statistics(self):
        """Get dashboard statistics"""
        now = timezone.now()
        
        # User statistics
        total_users = UserProfile.objects.count()
        users_today = UserProfile.objects.filter(
            created_at__date=now.date()
        ).count()
        users_this_week = UserProfile.objects.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        users_this_month = UserProfile.objects.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()
        
        # Subscription statistics
        active_subscriptions = UserProfile.objects.filter(
            Q(subscription_status='active', subscription_end_date__gt=now) |
            Q(subscription_status='trial', trial_end_date__gt=now)
        ).count()
        trial_users = UserProfile.objects.filter(
            subscription_status='trial',
            trial_end_date__gt=now
        ).count()
        
        # Payment statistics
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_revenue = Payment.objects.filter(
            status='completed',
            created_at__gte=now - timedelta(days=30)
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Signal statistics
        total_signals = TradingSignal.objects.count()
        signals_today = TradingSignal.objects.filter(
            created_at__date=now.date()
        ).count()
        signals_this_week = TradingSignal.objects.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        active_signals = TradingSignal.objects.filter(is_valid=True).count()
        
        # Alerts
        unread_alerts = SignalAlert.objects.filter(is_read=False).count()
        
        return {
            'users': {
                'total': total_users,
                'today': users_today,
                'this_week': users_this_week,
                'this_month': users_this_month,
                'growth': self._calculate_growth(users_this_week, users_this_month),
            },
            'subscriptions': {
                'active': active_subscriptions,
                'trial': trial_users,
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': float(monthly_revenue),
            },
            'signals': {
                'total': total_signals,
                'today': signals_today,
                'this_week': signals_this_week,
                'active': active_signals,
            },
            'alerts': {
                'unread': unread_alerts,
            }
        }
    
    def _calculate_growth(self, current, previous):
        """Calculate growth percentage"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100
    
    def get_recent_activity(self):
        """Get recent activity feed"""
        now = timezone.now()
        
        activities = []
        
        # Recent user registrations
        recent_users = UserProfile.objects.select_related('user').order_by('-created_at')[:5]
        for profile in recent_users:
            activities.append({
                'type': 'user_registration',
                'message': f"New user registered: {profile.user.email}",
                'time': profile.created_at,
                'url': reverse('admin:auth_user_change', args=[profile.user.id]),
            })
        
        # Recent subscription changes
        from apps.subscription.models import SubscriptionHistory
        recent_subscriptions = SubscriptionHistory.objects.select_related(
            'user', 'old_plan', 'new_plan'
        ).order_by('-created_at')[:5]
        for sub in recent_subscriptions:
            activities.append({
                'type': 'subscription_change',
                'message': f"{sub.user.email} {sub.action} subscription",
                'time': sub.created_at,
                'url': reverse('admin:subscription_userprofile_changelist') + f'?user__id__exact={sub.user.id}',
            })
        
        # Recent signals
        recent_signals = TradingSignal.objects.select_related('symbol', 'signal_type').order_by('-created_at')[:5]
        for signal in recent_signals:
            activities.append({
                'type': 'signal_generated',
                'message': f"New {signal.signal_type.name} signal for {signal.symbol.symbol}",
                'time': signal.created_at,
                'url': reverse('admin:signals_tradingsignal_change', args=[signal.id]),
            })
        
        # Sort by time and return top 10
        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:10]
    
    def reports_view(self, request):
        """Display reports page"""
        from apps.core.admin_reports import ReportService
        available_reports = ReportService.get_available_reports()
        
        context = {
            **self.each_context(request),
            'title': 'Generate Reports',
            'available_reports': available_reports,
        }
        
        return TemplateResponse(request, 'admin/reports/index.html', context)
    
    def generate_report_view(self, request):
        """Generate a report"""
        from django.http import JsonResponse
        from apps.core.admin_reports import ReportService
        
        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)
        
        report_type = request.POST.get('report_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if not report_type:
            return JsonResponse({'error': 'Report type is required'}, status=400)
        
        try:
            # Parse dates
            start = None
            end = None
            if start_date:
                start = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                start = timezone.make_aware(start)
            if end_date:
                end = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                end = timezone.make_aware(end)
            
            # Generate report
            report = ReportService.generate_report(
                report_type=report_type,
                start_date=start,
                end_date=end
            )
            
            return JsonResponse({
                'success': True,
                'report': report
            }, default=str)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def export_report_view(self, request):
        """Export a report to various formats"""
        from django.http import JsonResponse, HttpResponse
        from apps.core.admin_reports import ReportService
        import json
        
        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)
        
        report_type = request.POST.get('report_type')
        format_type = request.POST.get('format', 'json')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if not report_type:
            return JsonResponse({'error': 'Report type is required'}, status=400)
        
        try:
            # Parse dates
            start = None
            end = None
            if start_date:
                start = timezone.datetime.strptime(start_date, '%Y-%m-%d')
                start = timezone.make_aware(start)
            if end_date:
                end = timezone.datetime.strptime(end_date, '%Y-%m-%d')
                end = timezone.make_aware(end)
            
            # Generate report
            report = ReportService.generate_report(
                report_type=report_type,
                start_date=start,
                end_date=end
            )
            
            # Export based on format
            if format_type == 'json':
                response = HttpResponse(
                    content_type='application/json',
                    content=json.dumps(report, indent=2, default=str)
                )
                filename = f"{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Export format {format_type} not yet implemented for reports'
                }, status=400)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


# Create custom admin site instance
custom_admin_site = CustomAdminSite(name='custom_admin')

