"""Views package for Super Admin Portal."""
from views.login_v2 import LoginView
from views.dashboard_v2 import DashboardView
from views.tenants import TenantsView
from views.plans import PlansView
from views.monitoring import MonitoringView
from views.compliance import ComplianceView
from views.analytics import AnalyticsView
from views.integrations import IntegrationsView
from views.settings import SettingsView

__all__ = [
    "LoginView",
    "DashboardView",
    "TenantsView",
    "PlansView",
    "MonitoringView",
    "ComplianceView",
    "AnalyticsView",
    "IntegrationsView",
    "SettingsView",
]
