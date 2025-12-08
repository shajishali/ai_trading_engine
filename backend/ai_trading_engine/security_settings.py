"""
Security Settings for AI Trading Engine

This file contains comprehensive security configurations including:
- Rate limiting settings
- Security headers configuration
- IP filtering and blacklisting
- Request validation rules
- Audit logging configuration
- CSRF and session security
"""

# Rate Limiting Configuration
RATE_LIMITS = {
    'default': {
        'requests': 100,      # 100 requests per hour
        'window': 3600,       # 1 hour window
        'burst': 20,          # Allow burst of 20 requests
        'nodelay': False      # Apply delay for burst requests
    },
    'api': {
        'requests': 500,      # 500 API requests per hour
        'window': 3600,       # 1 hour window
        'burst': 50,          # Allow burst of 50 requests
        'nodelay': False
    },
    'login': {
        'requests': 5,        # 5 login attempts per 5 minutes
        'window': 300,        # 5 minute window
        'burst': 2,           # Allow burst of 2 requests
        'nodelay': False
    },
    'signup': {
        'requests': 3,        # 3 signup attempts per hour
        'window': 3600,       # 1 hour window
        'burst': 1,           # No burst allowed
        'nodelay': False
    },
    'trading': {
        'requests': 1000,     # 1000 trading requests per hour
        'window': 3600,       # 1 hour window
        'burst': 100,         # Allow burst of 100 requests
        'nodelay': False
    },
    'admin': {
        'requests': 200,      # 200 admin requests per hour
        'window': 3600,       # 1 hour window
        'burst': 10,          # Allow burst of 10 requests
        'nodelay': False
    }
}

# Security Headers Configuration
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    'Cross-Origin-Embedder-Policy': 'require-corp',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Cross-Origin-Resource-Policy': 'same-origin'
}

# Content Security Policy
CSP_POLICY = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", "data:", "https:"],
    'font-src': ["'self'", "data:"],
    'connect-src': ["'self'", "wss:"],
    'frame-ancestors': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'upgrade-insecure-requests': True
}

# IP Filtering Configuration
IP_SECURITY = {
    'WHITELIST_ENABLED': False,  # Set to True to enable IP whitelisting
    'WHITELISTED_IPS': [
        # Add your whitelisted IPs here
        # '192.168.1.0/24',  # Example: Local network
        # '10.0.0.0/8',      # Example: Private network
    ],
    'BLACKLIST_ENABLED': True,
    'AUTO_BLACKLIST_THRESHOLD': 5,  # Auto-blacklist after 5 suspicious activities
    'BLACKLIST_DURATION': 86400,     # 24 hours in seconds
    'SUSPICIOUS_ACTIVITY_TIMEOUT': 3600,  # 1 hour in seconds
}

# Request Validation Configuration
REQUEST_VALIDATION = {
    'MAX_POST_SIZE': 10 * 1024 * 1024,  # 10MB
    'MAX_HEADER_SIZE': 8192,            # 8KB
    'BLOCKED_USER_AGENTS': [
        'sqlmap', 'nikto', 'nmap', 'scanner', 'bot', 'crawler',
        'spider', 'harvester', 'grabber', 'wget', 'curl'
    ],
    'ALLOWED_CONTENT_TYPES': [
        'application/json',
        'application/x-www-form-urlencoded',
        'multipart/form-data',
        'text/plain'
    ],
    'BLOCKED_EXTENSIONS': [
        '.php', '.asp', '.aspx', '.jsp', '.exe', '.bat', '.cmd',
        '.com', '.pif', '.scr', '.vbs', '.js', '.jar'
    ]
}

# Session Security Configuration
SESSION_SECURITY = {
    'SESSION_COOKIE_SECURE': True,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'SESSION_COOKIE_AGE': 3600,        # 1 hour
    'SESSION_EXPIRE_AT_BROWSER_CLOSE': True,
    'SESSION_SAVE_EVERY_REQUEST': False,
    'SESSION_SERIALIZER': 'django.contrib.sessions.serializers.JSONSerializer'
}

# CSRF Security Configuration
CSRF_SECURITY = {
    'CSRF_COOKIE_SECURE': True,
    'CSRF_COOKIE_HTTPONLY': False,  # Must be False for AJAX requests
    'CSRF_COOKIE_SAMESITE': 'Lax',
    'CSRF_COOKIE_AGE': 31449600,    # 1 year
    'CSRF_FAILURE_VIEW': 'apps.core.views.csrf_failure',
    'CSRF_TRUSTED_ORIGINS': [
        # Add your trusted domains here
        # 'https://yourdomain.com',
        # 'https://www.yourdomain.com'
    ]
}

# Password Security Configuration
PASSWORD_SECURITY = {
    'PASSWORD_MIN_LENGTH': 12,
    'PASSWORD_MAX_LENGTH': 128,
    'PASSWORD_REQUIRE_UPPERCASE': True,
    'PASSWORD_REQUIRE_LOWERCASE': True,
    'PASSWORD_REQUIRE_DIGITS': True,
    'PASSWORD_REQUIRE_SYMBOLS': True,
    'PASSWORD_HISTORY_COUNT': 5,      # Remember last 5 passwords
    'PASSWORD_EXPIRY_DAYS': 90,      # Force password change every 90 days
    'PASSWORD_LOCKOUT_ATTEMPTS': 5,   # Lock account after 5 failed attempts
    'PASSWORD_LOCKOUT_DURATION': 900, # Lock for 15 minutes
}

# Authentication Security Configuration
AUTH_SECURITY = {
    'LOGIN_TIMEOUT': 300,             # 5 minutes
    'LOGIN_MAX_ATTEMPTS': 5,          # Maximum login attempts
    'LOGIN_LOCKOUT_DURATION': 900,    # 15 minutes lockout
    'LOGIN_REQUIRE_2FA': False,       # Enable 2FA requirement
    'LOGIN_SESSION_TIMEOUT': 3600,    # 1 hour session timeout
    'LOGIN_REMEMBER_ME_DURATION': 2592000,  # 30 days
    'LOGIN_IP_VALIDATION': True,      # Validate login IP
    'LOGIN_DEVICE_FINGERPRINTING': True,  # Device fingerprinting
}

# Audit Logging Configuration
AUDIT_LOGGING = {
    'ENABLED': True,
    'LOG_LEVEL': 'INFO',
    'LOG_FILE': 'logs/audit.log',
    'LOG_FORMAT': 'JSON',
    'LOG_RETENTION_DAYS': 90,
    'LOG_SENSITIVE_FIELDS': [
        'password', 'token', 'secret', 'key', 'credential'
    ],
    'LOG_EVENTS': [
        'AUTH_ATTEMPT',
        'AUTH_SUCCESS',
        'AUTH_FAILURE',
        'USER_CREATE',
        'USER_UPDATE',
        'USER_DELETE',
        'LOGIN',
        'LOGOUT',
        'PASSWORD_CHANGE',
        'PASSWORD_RESET',
        'TRADING_OPERATION',
        'PORTFOLIO_ACCESS',
        'ADMIN_ACTION',
        'API_ACCESS',
        'FILE_UPLOAD',
        'FILE_DOWNLOAD'
    ]
}

# API Security Configuration
API_SECURITY = {
    'REQUIRE_AUTHENTICATION': True,
    'REQUIRE_HTTPS': True,
    'ALLOW_ANONYMOUS_ACCESS': False,
    'API_KEY_REQUIRED': True,
    'API_KEY_HEADER': 'X-API-Key',
    'API_KEY_LENGTH': 64,
    'API_RATE_LIMIT_ENABLED': True,
    'API_VERSIONING_ENABLED': True,
    'API_DEPRECATION_WARNING_DAYS': 30,
    'API_DOCUMENTATION_ENABLED': True,
    'API_MONITORING_ENABLED': True
}

# File Upload Security Configuration
FILE_UPLOAD_SECURITY = {
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'ALLOWED_EXTENSIONS': [
        '.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt',
        '.csv', '.xlsx', '.xls', '.doc', '.docx'
    ],
    'ALLOWED_MIME_TYPES': [
        'image/jpeg', 'image/png', 'image/gif',
        'application/pdf', 'text/plain', 'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ],
    'SCAN_FOR_VIRUSES': True,
    'VALIDATE_FILE_CONTENT': True,
    'UPLOAD_DIRECTORY': 'uploads/',
    'UPLOAD_PERMISSIONS': 0o644
}

# Database Security Configuration
DATABASE_SECURITY = {
    'CONNECTION_ENCRYPTION': True,
    'SSL_MODE': 'require',
    'CONNECTION_TIMEOUT': 30,
    'QUERY_TIMEOUT': 60,
    'MAX_CONNECTIONS': 20,
    'CONNECTION_POOLING': True,
    'QUERY_LOGGING': False,  # Disable in production for security
    'SENSITIVE_DATA_MASKING': True,
    'BACKUP_ENCRYPTION': True,
    'BACKUP_RETENTION_DAYS': 30
}

# Redis Security Configuration
REDIS_SECURITY = {
    'REQUIRE_AUTHENTICATION': True,
    'PASSWORD_COMPLEXITY': True,
    'SSL_ENABLED': True,
    'NETWORK_ACCESS': '127.0.0.1',  # Only local access
    'MAX_MEMORY': '256mb',
    'MAX_MEMORY_POLICY': 'allkeys-lru',
    'KEY_EXPIRATION': True,
    'KEY_PREFIX': 'ai_trading_engine:',
    'CONNECTION_POOL_SIZE': 10,
    'CONNECTION_TIMEOUT': 5
}

# Email Security Configuration
EMAIL_SECURITY = {
    'REQUIRE_TLS': True,
    'REQUIRE_SSL': True,
    'VERIFY_CERTIFICATES': True,
    'ALLOWED_SMTP_SERVERS': [
        'smtp.gmail.com',
        'smtp.office365.com',
        'smtp.sendgrid.net'
    ],
    'BLOCKED_ATTACHMENTS': [
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',
        '.vbs', '.js', '.jar', '.msi', '.dll'
    ],
    'MAX_ATTACHMENT_SIZE': 5 * 1024 * 1024,  # 5MB
    'SPAM_FILTERING': True,
    'PHISHING_PROTECTION': True
}

# Monitoring and Alerting Configuration
SECURITY_MONITORING = {
    'ENABLED': True,
    'CHECK_INTERVAL': 60,  # 1 minute
    'ALERT_THRESHOLD': 0.8,  # 80% security score
    'ALERT_CHANNELS': ['email', 'slack', 'webhook'],
    'SECURITY_SCORE_CALCULATION': True,
    'VULNERABILITY_SCANNING': True,
    'PENETRATION_TESTING': False,  # Enable for security audits
    'INCIDENT_RESPONSE_PLAN': True,
    'FORENSIC_LOGGING': True,
    'THREAT_INTELLIGENCE': True
}

# Compliance and Regulatory Configuration
COMPLIANCE = {
    'GDPR_COMPLIANCE': True,
    'CCPA_COMPLIANCE': True,
    'SOX_COMPLIANCE': False,  # Enable if required
    'PCI_DSS_COMPLIANCE': False,  # Enable if handling payment data
    'HIPAA_COMPLIANCE': False,  # Enable if handling health data
    'DATA_RETENTION_POLICY': True,
    'DATA_DELETION_POLICY': True,
    'PRIVACY_POLICY_ENFORCEMENT': True,
    'CONSENT_MANAGEMENT': True,
    'DATA_PORTABILITY': True
}

# Backup and Recovery Security Configuration
BACKUP_SECURITY = {
    'ENCRYPTION_ENABLED': True,
    'ENCRYPTION_ALGORITHM': 'AES-256',
    'COMPRESSION_ENABLED': True,
    'VERIFICATION_ENABLED': True,
    'OFFSITE_BACKUP': True,
    'BACKUP_RETENTION_DAYS': 90,
    'BACKUP_FREQUENCY': 'daily',
    'BACKUP_MONITORING': True,
    'DISASTER_RECOVERY_PLAN': True,
    'BACKUP_TESTING': True
}

# Network Security Configuration
NETWORK_SECURITY = {
    'FIREWALL_ENABLED': True,
    'INTRUSION_DETECTION': True,
    'INTRUSION_PREVENTION': True,
    'DDoS_PROTECTION': True,
    'VPN_REQUIRED': False,  # Enable if required
    'NETWORK_SEGMENTATION': True,
    'VLAN_ISOLATION': True,
    'ACCESS_CONTROL_LISTS': True,
    'NETWORK_MONITORING': True,
    'BANDWIDTH_LIMITING': True
}

# Application Security Configuration
APPLICATION_SECURITY = {
    'INPUT_VALIDATION': True,
    'OUTPUT_ENCODING': True,
    'SQL_INJECTION_PROTECTION': True,
    'XSS_PROTECTION': True,
    'CSRF_PROTECTION': True,
    'CLICKJACKING_PROTECTION': True,
    'MIME_SNIFFING_PROTECTION': True,
    'HSTS_ENABLED': True,
    'SECURE_COOKIES': True,
    'SECURE_HEADERS': True
}

# Development and Testing Security Configuration
DEV_SECURITY = {
    'DEBUG_MODE_SECURITY': False,  # Disable debug in production
    'TESTING_ENVIRONMENT': False,
    'MOCK_SERVICES': False,
    'FAKE_DATA_GENERATION': False,
    'DEVELOPMENT_TOOLS': False,
    'PROFILING_ENABLED': False,
    'LOG_VERBOSITY': 'INFO',
    'ERROR_DETAILS': False,  # Don't expose error details in production
    'STACK_TRACES': False,   # Don't expose stack traces in production
    'SOURCE_CODE_EXPOSURE': False
}
