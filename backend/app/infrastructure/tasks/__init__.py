"""Celery tasks package for background job processing."""

from app.infrastructure.tasks.celery_app import celery_app

__all__ = ["celery_app"]
