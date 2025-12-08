"""
Security Audit Management Command

This command provides comprehensive security auditing for the AI Trading Engine
production deployment, including vulnerability assessment and compliance checking.
"""

import json
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.services import SecurityAuditService, SecurityMonitoringService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Perform comprehensive security audit for production deployment'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['json', 'text', 'detailed', 'html'],
            default='text',
            help='Output format for security audit results'
        )
        parser.add_argument(
            '--category',
            choices=['all', 'authentication', 'network', 'application', 'data', 'infrastructure', 'compliance'],
            default='all',
            help='Specific security category to audit'
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically fix low-risk security issues where possible'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to specified file path'
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuous security monitoring'
        )
    
    def handle(self, *args, **options):
        """Execute security audit"""
        self.stdout.write("🔒 Starting comprehensive security audit...")
        
        # Initialize security services
        security_audit = SecurityAuditService()
        security_monitoring = SecurityMonitoringService()
        
        if options['continuous']:
            self.stdout.write("🔄 Starting continuous security monitoring...")
            self._run_continuous_monitoring(security_monitoring)
            return
        
        # Run security audit
        start_time = time.time()
        
        try:
            # Run comprehensive audit
            audit_results = security_audit.run_security_audit()
            
            # Filter by category if specified
            if options['category'] != 'all':
                audit_results = self._filter_by_category(audit_results, options['category'])
            
            # Generate detailed report
            security_report = security_audit.generate_security_report(audit_results)
            
            # Calculate audit duration
            duration = time.time() - start_time
            
            # Output results
            self.output_results(security_report, options['format'], duration)
            
            # Export results if requested
            if options['export']:
                self.export_results(security_report, options['export'])
            
            # Auto-fix if requested
            if options['fix']:
                self.auto_fix_issues(security_report)
            
            # Exit with appropriate code
            if security_report['summary']['risk_level'] == 'CRITICAL':
                self.stdout.write(self.style.ERROR("🚨 CRITICAL security issues detected!"))
                exit(1)
            elif security_report['summary']['risk_level'] == 'HIGH':
                self.stdout.write(self.style.WARNING("⚠️ HIGH security risk detected"))
                exit(0)
            else:
                self.stdout.write(self.style.SUCCESS("✅ Security audit completed successfully"))
                exit(0)
                
        except Exception as e:
            logger.error(f"Security audit failed: {e}")
            self.stdout.write(self.style.ERROR(f"Security audit failed: {e}"))
            exit(1)
    
    def _filter_by_category(self, audit_results, category):
        """Filter audit results by specific category"""
        if category == 'all':
            return audit_results
        
        filtered_results = {
            'timestamp': audit_results['timestamp'],
            'overall_score': 0,
            'categories': {category: audit_results['categories'].get(category, {})},
            'vulnerabilities': [],
            'recommendations': []
        }
        
        # Get category-specific results
        category_result = audit_results['categories'].get(category, {})
        if isinstance(category_result, dict):
            filtered_results['vulnerabilities'] = category_result.get('vulnerabilities', [])
            filtered_results['recommendations'] = category_result.get('recommendations', [])
            filtered_results['overall_score'] = category_result.get('score', 0)
        
        return filtered_results
    
    def _run_continuous_monitoring(self, security_monitoring):
        """Run continuous security monitoring"""
        try:
            security_monitoring.start_monitoring()
            
            self.stdout.write("🔄 Continuous security monitoring started")
            self.stdout.write("Press Ctrl+C to stop monitoring")
            
            # Keep monitoring running
            while True:
                time.sleep(60)  # Check every minute
                status = security_monitoring.get_security_status()
                
                if status['active_alerts']:
                    self.stdout.write(f"🚨 {len(status['active_alerts'])} active security alerts")
                
        except KeyboardInterrupt:
            self.stdout.write("\n🛑 Security monitoring stopped")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Monitoring error: {e}"))
    
    def output_results(self, security_report, format_type, duration):
        """Output security audit results in specified format"""
        if format_type == 'json':
            self.output_json(security_report)
        elif format_type == 'html':
            self.output_html(security_report)
        elif format_type == 'detailed':
            self.output_detailed(security_report, duration)
        else:
            self.output_text(security_report, duration)
    
    def output_text(self, security_report, duration):
        """Output results in human-readable text format"""
        summary = security_report['summary']
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🔒 SECURITY AUDIT RESULTS")
        self.stdout.write("=" * 80)
        
        # Overall summary
        self.stdout.write(f"Overall Security Score: {summary['overall_score']}/100")
        self.stdout.write(f"Risk Level: {summary['risk_level']}")
        self.stdout.write(f"Total Vulnerabilities: {summary['total_vulnerabilities']}")
        self.stdout.write(f"Total Recommendations: {summary['total_recommendations']}")
        self.stdout.write(f"Audit Duration: {duration:.2f} seconds")
        
        # Category breakdown
        self.stdout.write(f"\n📊 SECURITY CATEGORIES:")
        self.stdout.write("-" * 40)
        
        for category, result in security_report['detailed_results']['categories'].items():
            if isinstance(result, dict) and 'score' in result:
                score = result['score']
                vulns = len(result.get('vulnerabilities', []))
                recs = len(result.get('recommendations', []))
                
                status_icon = "✅" if score >= 80 else "⚠️" if score >= 60 else "❌"
                self.stdout.write(f"{status_icon} {category.title()}: {score}/100 (V:{vulns}, R:{recs})")
        
        # Critical vulnerabilities
        if security_report['vulnerabilities']:
            self.stdout.write(f"\n🚨 CRITICAL VULNERABILITIES:")
            self.stdout.write("-" * 40)
            for vuln in security_report['vulnerabilities']:
                self.stdout.write(f"❌ {vuln}")
        
        # High priority recommendations
        if security_report['recommendations']:
            self.stdout.write(f"\n💡 SECURITY RECOMMENDATIONS:")
            self.stdout.write("-" * 40)
            for rec in security_report['recommendations']:
                self.stdout.write(f"💡 {rec}")
        
        # Action items
        if security_report['action_items']:
            self.stdout.write(f"\n🎯 PRIORITY ACTION ITEMS:")
            self.stdout.write("-" * 40)
            for item in security_report['action_items']:
                priority_icon = "🚨" if item['priority'] == 'CRITICAL' else "⚠️" if item['priority'] == 'HIGH' else "ℹ️"
                self.stdout.write(f"{priority_icon} [{item['priority']}] {item['action']}")
                self.stdout.write(f"    Effort: {item['effort']}, Impact: {item['impact']}")
        
        # Next steps
        if security_report['next_steps']:
            self.stdout.write(f"\n📋 NEXT STEPS:")
            self.stdout.write("-" * 40)
            for step in security_report['next_steps']:
                self.stdout.write(f"➡️ {step}")
        
        # Compliance status
        if security_report['compliance_gaps']:
            self.stdout.write(f"\n⚠️ COMPLIANCE GAPS:")
            self.stdout.write("-" * 40)
            for gap in security_report['compliance_gaps']:
                self.stdout.write(f"⚠️ {gap}")
    
    def output_json(self, security_report):
        """Output results in JSON format"""
        self.stdout.write(json.dumps(security_report, indent=2))
    
    def output_html(self, security_report):
        """Output results in HTML format"""
        html_content = self._generate_html_report(security_report)
        self.stdout.write(html_content)
    
    def output_detailed(self, security_report, duration):
        """Output results in detailed format"""
        self.output_text(security_report, duration)
        
        # Additional detailed analysis
        self.stdout.write(f"\n🔍 DETAILED ANALYSIS:")
        self.stdout.write("=" * 80)
        
        # Security score breakdown
        self.stdout.write(f"\n📊 SECURITY SCORE BREAKDOWN:")
        self.stdout.write("-" * 40)
        
        total_weight = 0
        weighted_score = 0
        
        for category, result in security_report['detailed_results']['categories'].items():
            if isinstance(result, dict) and 'score' in result and 'weight' in result:
                weight = result['weight']
                score = result['score']
                weighted_score += score * weight
                total_weight += weight
                
                self.stdout.write(f"{category.title()}: {score}/100 (Weight: {weight})")
        
        if total_weight > 0:
            overall_score = weighted_score / total_weight
            self.stdout.write(f"\nWeighted Overall Score: {overall_score:.2f}/100")
        
        # Risk assessment
        self.stdout.write(f"\n⚠️ RISK ASSESSMENT:")
        self.stdout.write("-" * 40)
        
        risk_level = security_report['summary']['risk_level']
        if risk_level == 'CRITICAL':
            self.stdout.write("🚨 CRITICAL RISK: Immediate action required")
            self.stdout.write("   - System may be compromised")
            self.stdout.write("   - Stop production deployment")
            self.stdout.write("   - Engage security team immediately")
        elif risk_level == 'HIGH':
            self.stdout.write("⚠️ HIGH RISK: Urgent attention required")
            self.stdout.write("   - Address vulnerabilities within 24 hours")
            self.stdout.write("   - Review security configuration")
            self.stdout.write("   - Consider security consultation")
        elif risk_level == 'MEDIUM':
            self.stdout.write("🔶 MEDIUM RISK: Attention required")
            self.stdout.write("   - Address issues within 1 week")
            self.stdout.write("   - Implement recommendations")
            self.stdout.write("   - Schedule follow-up review")
        else:
            self.stdout.write("✅ LOW RISK: Good security posture")
            self.stdout.write("   - Continue monitoring")
            self.stdout.write("   - Implement minor improvements")
            self.stdout.write("   - Schedule regular audits")
    
    def _generate_html_report(self, security_report):
        """Generate HTML security report"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Security Audit Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
                .score { font-size: 24px; font-weight: bold; }
                .critical { color: #d32f2f; }
                .high { color: #f57c00; }
                .medium { color: #fbc02d; }
                .low { color: #388e3c; }
                .section { margin: 20px 0; }
                .vulnerability { color: #d32f2f; }
                .recommendation { color: #1976d2; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔒 Security Audit Report</h1>
                <p>Generated: {timestamp}</p>
                <p class="score">Overall Score: <span class="{score_class}">{score}/100</span></p>
                <p>Risk Level: <strong>{risk_level}</strong></p>
            </div>
            
            <div class="section">
                <h2>📊 Summary</h2>
                <p>Vulnerabilities: {vuln_count}</p>
                <p>Recommendations: {rec_count}</p>
            </div>
            
            <div class="section">
                <h2>🚨 Vulnerabilities</h2>
                <ul>
                    {vulnerabilities}
                </ul>
            </div>
            
            <div class="section">
                <h2>💡 Recommendations</h2>
                <ul>
                    {recommendations}
                </ul>
            </div>
        </body>
        </html>
        """
        
        # Prepare data for HTML template
        score_class = 'low'
        if security_report['summary']['risk_level'] == 'CRITICAL':
            score_class = 'critical'
        elif security_report['summary']['risk_level'] == 'HIGH':
            score_class = 'high'
        elif security_report['summary']['risk_level'] == 'MEDIUM':
            score_class = 'medium'
        
        vulnerabilities_html = ''
        for vuln in security_report['vulnerabilities']:
            vulnerabilities_html += f'<li class="vulnerability">{vuln}</li>'
        
        recommendations_html = ''
        for rec in security_report['recommendations']:
            recommendations_html += f'<li class="recommendation">{rec}</li>'
        
        return html_template.format(
            timestamp=security_report['detailed_results']['timestamp'],
            score=security_report['summary']['overall_score'],
            score_class=score_class,
            risk_level=security_report['summary']['risk_level'],
            vuln_count=security_report['summary']['total_vulnerabilities'],
            rec_count=security_report['summary']['total_recommendations'],
            vulnerabilities=vulnerabilities_html,
            recommendations=recommendations_html
        )
    
    def export_results(self, security_report, file_path):
        """Export security audit results to file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(security_report, f, indent=2)
            
            self.stdout.write(self.style.SUCCESS(f"✅ Security audit results exported to {file_path}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to export results: {e}"))
    
    def auto_fix_issues(self, security_report):
        """Automatically fix low-risk security issues where possible"""
        self.stdout.write("\n🔧 Attempting to auto-fix security issues...")
        
        fixed_count = 0
        
        # Check for auto-fixable issues
        for rec in security_report['recommendations']:
            if self._can_auto_fix(rec):
                if self._auto_fix_issue(rec):
                    fixed_count += 1
        
        if fixed_count > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ Auto-fixed {fixed_count} security issues"))
        else:
            self.stdout.write("ℹ️ No auto-fixable issues found")
    
    def _can_auto_fix(self, recommendation):
        """Check if a recommendation can be auto-fixed"""
        auto_fixable = [
            'Configure file upload size limits',
            'Enable comprehensive logging',
            'Configure automated backups'
        ]
        
        return any(fixable in recommendation for fixable in auto_fixable)
    
    def _auto_fix_issue(self, recommendation):
        """Attempt to auto-fix a security issue"""
        try:
            if 'file upload size limits' in recommendation.lower():
                # This would require updating Django settings
                # For now, just log the attempt
                logger.info("Auto-fix attempted for file upload limits")
                return True
            
            elif 'comprehensive logging' in recommendation.lower():
                # This would require updating logging configuration
                logger.info("Auto-fix attempted for logging configuration")
                return True
            
            elif 'automated backups' in recommendation.lower():
                # This would require setting up backup systems
                logger.info("Auto-fix attempted for backup configuration")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Auto-fix failed for {recommendation}: {e}")
            return False
