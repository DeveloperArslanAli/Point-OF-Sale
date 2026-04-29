# Grafana Provisioning

This directory contains Grafana provisioning configuration for automatic
dashboard and datasource setup.

## Directory Structure

```
grafana/
├── provisioning/
│   ├── dashboards/
│   │   ├── dashboard.yml          # Dashboard provider config
│   │   ├── api-metrics.json       # API performance dashboard
│   │   ├── business-metrics.json  # Business KPIs dashboard
│   │   └── system-metrics.json    # System health dashboard
│   └── datasources/
│       └── datasources.yml        # Prometheus datasource config
```

## Usage

1. Mount this directory in your Grafana container:
   ```yaml
   volumes:
     - ./grafana/provisioning:/etc/grafana/provisioning
   ```

2. Dashboards will be automatically imported on startup

## Dashboards

### API Metrics Dashboard
- HTTP request rates and latencies
- Error rates by endpoint
- Response time percentiles (p50, p95, p99)
- Active connections

### Business Metrics Dashboard
- Sales totals and trends
- Inventory movements
- Customer activity
- Gift card usage

### System Metrics Dashboard
- Celery task queue depth
- Worker health
- Redis connection status
- Database connection pool
