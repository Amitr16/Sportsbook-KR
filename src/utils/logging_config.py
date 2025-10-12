"""
Structured logging configuration with correlation IDs
"""

import logging
import json
import time
import uuid
from typing import Dict, Any, Optional
from flask import g, request, has_request_context
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add correlation ID if in request context
        if has_request_context():
            log_entry.update({
                'correlation_id': getattr(g, 'correlation_id', None),
                'request_id': getattr(g, 'request_id', None),
                'tenant': getattr(g, 'tenant', None),
                'user_id': getattr(g, 'user_id', None),
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
            })
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'message']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)

class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records"""
    
    def filter(self, record):
        # Add correlation ID only if in request context
        if has_request_context():
            record.correlation_id = getattr(g, 'correlation_id', 'N/A')
            record.request_id = getattr(g, 'request_id', 'N/A')
            record.tenant = getattr(g, 'tenant', 'N/A')
            record.user_id = getattr(g, 'user_id', 'N/A')
        else:
            # Outside request context, set defaults
            record.correlation_id = 'N/A'
            record.request_id = 'N/A'
            record.tenant = 'N/A'
            record.user_id = 'N/A'
        return True

def setup_structured_logging():
    """Setup structured logging configuration"""
    
    # Create formatters
    json_formatter = StructuredFormatter()
    # Use standard console format (correlation_id added via filter)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (development)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(CorrelationFilter())
    root_logger.addHandler(console_handler)
    
    # JSON handler for production
    if os.getenv('ENVIRONMENT') == 'production':
        # In production, you might want to send logs to a service like CloudWatch, etc.
        # For now, we'll use a file handler with JSON format
        file_handler = logging.FileHandler('/tmp/app.log')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(json_formatter)
        file_handler.addFilter(CorrelationFilter())
        root_logger.addHandler(file_handler)
    
    # Set specific loggers
    logging.getLogger('src').setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return root_logger

def get_correlation_id() -> str:
    """Get or create correlation ID for current request"""
    if not has_request_context():
        return str(uuid.uuid4())
    
    if not hasattr(g, 'correlation_id'):
        g.correlation_id = str(uuid.uuid4())
        g.request_id = str(uuid.uuid4())
        g.request_start_time = time.time()
    
    return g.correlation_id

def get_request_id() -> str:
    """Get or create request ID for current request"""
    if not has_request_context():
        return str(uuid.uuid4())
    
    if not hasattr(g, 'request_id'):
        get_correlation_id()  # This will create both IDs
    
    return g.request_id

def set_tenant_context(tenant: str):
    """Set tenant context for logging"""
    if has_request_context():
        g.tenant = tenant

def set_user_context(user_id: int):
    """Set user context for logging"""
    if has_request_context():
        g.user_id = user_id

def log_performance(operation: str, duration_ms: float, **kwargs):
    """Log performance metrics with correlation ID"""
    logger = logging.getLogger('performance')
    logger.info(
        f"Performance: {operation}",
        extra={
            'operation': operation,
            'duration_ms': duration_ms,
            'performance_metric': True,
            **kwargs
        }
    )

def log_business_event(event_type: str, **kwargs):
    """Log business events with structured data"""
    logger = logging.getLogger('business')
    logger.info(
        f"Business Event: {event_type}",
        extra={
            'event_type': event_type,
            'business_event': True,
            **kwargs
        }
    )

def log_security_event(event_type: str, severity: str = 'info', **kwargs):
    """Log security events with structured data"""
    logger = logging.getLogger('security')
    level = logging.INFO if severity == 'info' else logging.WARNING
    logger.log(
        level,
        f"Security Event: {event_type}",
        extra={
            'event_type': event_type,
            'security_event': True,
            'severity': severity,
            **kwargs
        }
    )

# Initialize logging on import
import os
setup_structured_logging()
