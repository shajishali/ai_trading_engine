"""
Admin Views for Report Generation
"""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_http_methods

from apps.core.admin_reports import ReportService
from apps.core.admin_exports import export_queryset, JSONExporter


class ReportGenerationMixin:
    """Mixin for report generation views"""
    
    def get_urls(self):
        """Add custom URLs for report generation"""
        urls = super().get_urls()
        custom_urls = [
            path('reports/', self.admin_site.admin_view(self.reports_view), name='admin_reports'),
            path('reports/generate/', self.admin_site.admin_view(self.generate_report_view), name='admin_generate_report'),
            path('reports/export/', self.admin_site.admin_view(self.export_report_view), name='admin_export_report'),
        ]
        return custom_urls + urls
    
    def reports_view(self, request):
        """Display reports page"""
        available_reports = ReportService.get_available_reports()
        
        context = {
            **self.each_context(request),
            'title': 'Generate Reports',
            'available_reports': available_reports,
        }
        
        return TemplateResponse(request, 'admin/reports/index.html', context)
    
    def generate_report_view(self, request):
        """Generate a report"""
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
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def export_report_view(self, request):
        """Export a report to various formats"""
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
                    content=JSONExporter([report], ['report']).export().content
                )
                filename = f"{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                # For other formats, convert report to queryset-like structure
                # This is a simplified implementation
                return JsonResponse({
                    'success': False,
                    'error': f'Export format {format_type} not yet implemented for reports'
                }, status=400)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

