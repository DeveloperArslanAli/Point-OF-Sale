"""
Celery application configuration for async task processing.

This module sets up the Celery app with Redis as broker and result backend.
Tasks are defined in separate modules and auto-discovered.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue
from app.core.settings import get_settings

settings = get_settings()

# Check if Celery is enabled (Redis available)
CELERY_ENABLED = bool(settings.CELERY_BROKER_URL)

celery_app = Celery(
    "retail_pos",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.infrastructure.tasks.product_import_tasks",
        "app.infrastructure.tasks.report_tasks",
        "app.infrastructure.tasks.email_tasks",
        "app.infrastructure.tasks.scheduled_tasks",
        "app.infrastructure.tasks.inventory_tasks",
        "app.infrastructure.tasks.webhook_tasks",
        "app.infrastructure.tasks.ml_data_pipeline",
        "app.infrastructure.tasks.ml_model_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task queues
    task_queues=[
        Queue("imports", routing_key="imports"),
        Queue("reports", routing_key="reports"),
        Queue("emails", routing_key="emails"),
        Queue("webhooks", routing_key="webhooks"),
        Queue("default", routing_key="default"),
    ],
    task_default_queue="default",
    task_default_routing_key="default",
    
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard limit
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit (warning)
    
    # Worker optimization
    worker_prefetch_multiplier=4,  # Fetch 4 tasks per worker at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={"master_name": "mymaster"},
    
    # Task routing (optional)
    task_routes={
        "app.infrastructure.tasks.product_import_tasks.*": {"queue": "imports"},
        "app.infrastructure.tasks.report_tasks.*": {"queue": "reports"},
        "app.infrastructure.tasks.email_tasks.*": {"queue": "emails"},
        "app.infrastructure.tasks.webhook_tasks.*": {"queue": "webhooks"},
    },
)

# Scheduled tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens-hourly": {
        "task": "cleanup_expired_tokens",
        "schedule": 3600.0,  # Every hour
    },
    "generate-daily-reports": {
        "task": "generate_daily_reports",
        "schedule": crontab(hour=23, minute=0),  # 11 PM daily
    },
    "refresh-inventory-forecast-every-6h": {
        "task": "refresh_inventory_forecast",
        "schedule": 6 * 3600.0,  # Every 6 hours to keep forecasts warm
    },
    "recompute-forecast-model-nightly": {
        "task": "recompute_forecast_model",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
        "kwargs": {
            "smoothing_alpha": 0.3,
            "seasonality": True,  # Enable day-of-week seasonality
            "lookback_days": 90,
            "lead_time_days": 7,
            "safety_stock_days": 3,
            "broadcast_alerts": True,  # Send WebSocket alerts for critical items
        },
    },
    "check-low-stock-morning": {
        "task": "check_low_stock_alerts",
        "schedule": crontab(hour=8, minute=0),  # 8 AM daily
        "kwargs": {
            "threshold_days": 7,
            "email_recipients": [],  # Configure in settings
            "enable_sms": False,
        },
    },
    "check-low-stock-afternoon": {
        "task": "check_low_stock_alerts",
        "schedule": crontab(hour=16, minute=0),  # 4 PM daily
        "kwargs": {
            "threshold_days": 7,
            "email_recipients": [],
            "enable_sms": False,
        },
    },
    "dead-stock-weekly-report": {
        "task": "check_dead_stock_alerts",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Monday 9 AM
        "kwargs": {
            "days_inactive": 90,
            "email_recipients": [],
        },
    },
    "retry-failed-webhooks-every-5min": {
        "task": "retry_failed_webhooks",
        "schedule": 5 * 60.0,  # Every 5 minutes
    },
    "cleanup-old-webhook-deliveries-daily": {
        "task": "cleanup_old_webhook_deliveries",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
        "kwargs": {
            "retention_days": 30,
        },
    },
    # ========== ML Data Pipeline Tasks ==========
    "extract-customer-features-daily": {
        "task": "extract_customer_features",
        "schedule": crontab(hour=4, minute=0),  # 4 AM daily
        "kwargs": {
            "lookback_days": 365,
            "churn_threshold_days": 60,
        },
    },
    "extract-product-features-daily": {
        "task": "extract_product_features",
        "schedule": crontab(hour=4, minute=30),  # 4:30 AM daily
        "kwargs": {
            "lookback_days": 90,
        },
    },
    "extract-sales-training-data-weekly": {
        "task": "extract_sales_training_data",
        "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sunday 5 AM
        "kwargs": {
            "start_date": None,  # Last 90 days
            "end_date": None,
            "output_format": "json",
        },
    },
    # ========== ML Model Training Tasks (Phase 23) ==========
    "train-churn-model-weekly": {
        "task": "train_churn_model",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3 AM
        "kwargs": {
            "lookback_days": 365,
            "churn_threshold_days": 60,
        },
    },
    "train-fraud-model-weekly": {
        "task": "train_fraud_model",
        "schedule": crontab(hour=3, minute=30, day_of_week=0),  # Sunday 3:30 AM
        "kwargs": {
            "lookback_days": 90,
            "contamination": 0.01,
        },
    },
    "train-recommendation-model-weekly": {
        "task": "train_recommendation_model",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
        "kwargs": {
            "lookback_days": 180,
            "min_support": 0.01,
        },
    },
    "churn-risk-report-weekly": {
        "task": "predict_churn",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),  # Monday 8 AM
        "kwargs": {
            "customer_ids": None,  # All customers
            "risk_threshold": 0.6,  # High risk only
        },
    },
}

# Optional: Add error handlers
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    print(f"Request: {self.request!r}")
