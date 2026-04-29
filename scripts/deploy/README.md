# Retail POS Deployment Scripts

This directory contains deployment scripts and Kubernetes manifests for deploying the Retail POS system to staging and production environments.

## Directory Structure

```
deploy/
├── README.md               # This file
├── deploy-staging.sh       # Staging deployment script
├── deploy-production.sh    # Production deployment script
└── kubernetes/
    ├── staging/           # Staging K8s manifests
    │   └── deployment.yaml
    └── production/        # Production K8s manifests
        └── deployment.yaml
```

## Prerequisites

1. **kubectl** configured with cluster access
2. **Docker** for building images
3. **GitHub Container Registry** access (ghcr.io)

## Environment Setup

### Create Kubernetes Secrets

Before deploying, create the required secrets in each namespace:

```bash
# Staging
kubectl create namespace retail-pos-staging
kubectl create secret generic retail-pos-secrets \
  --namespace=retail-pos-staging \
  --from-literal=database-url='postgresql+asyncpg://user:pass@host:5432/db' \
  --from-literal=redis-url='redis://redis:6379/0' \
  --from-literal=jwt-secret='your-staging-jwt-secret' \
  --from-literal=celery-broker-url='redis://redis:6379/0'

# Production
kubectl create namespace retail-pos-production
kubectl create secret generic retail-pos-secrets \
  --namespace=retail-pos-production \
  --from-literal=database-url='postgresql+asyncpg://user:pass@host:5432/db' \
  --from-literal=redis-url='redis://redis:6379/0' \
  --from-literal=jwt-secret='your-production-jwt-secret' \
  --from-literal=celery-broker-url='redis://redis:6379/0' \
  --from-literal=sentry-dsn='your-sentry-dsn'
```

## Deployment

### Deploy to Staging

```bash
# Deploy latest develop branch
./deploy-staging.sh

# Deploy specific image tag
./deploy-staging.sh develop-abc1234
```

### Deploy to Production

```bash
# Deploy with confirmation prompt
./deploy-production.sh main-abc1234

# Deploy without confirmation (CI/CD)
SKIP_CONFIRMATION=true ./deploy-production.sh main-abc1234

# Deploy with git tag creation
CREATE_GIT_TAG=true ./deploy-production.sh main-abc1234
```

## CI/CD Integration

The deployment scripts are designed to work with the GitHub Actions workflow in `.github/workflows/ci-cd.yml`.

### Automatic Deployments

- **Staging**: Automatically deploys when code is pushed to `develop` branch
- **Production**: Automatically deploys when code is pushed to `main` branch (requires approval)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `IMAGE_REGISTRY` | Container registry | `ghcr.io` |
| `IMAGE_NAME` | Image name | `retail/pos-phython` |
| `KUBECONFIG` | Kubeconfig path | `$HOME/.kube/config` |
| `SKIP_CONFIRMATION` | Skip production confirmation | `false` |
| `ROLLBACK_ON_FAILURE` | Auto-rollback on failure | `true` |
| `CREATE_GIT_TAG` | Create git tag on success | `false` |

## Rollback

### Manual Rollback

```bash
# Rollback to previous revision
kubectl rollout undo deployment/retail-pos-api -n retail-pos-production

# Rollback to specific revision
kubectl rollout undo deployment/retail-pos-api -n retail-pos-production --to-revision=3

# Check rollout history
kubectl rollout history deployment/retail-pos-api -n retail-pos-production
```

## Monitoring

The deployments include Prometheus annotations for metrics scraping:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### Health Checks

- **Liveness**: `/health` - Kubernetes uses this to restart unhealthy pods
- **Readiness**: `/health` - Kubernetes uses this to route traffic

### Grafana Dashboards

Import the dashboard from `backend/docker/grafana/retail-pos-dashboard.json` into your Grafana instance.

## Security

- Pods run as non-root user (UID 1000)
- Read-only root filesystem (uses `/tmp` emptyDir for temp files)
- Network policies should be configured per environment
- Secrets are managed via Kubernetes Secrets (consider using Sealed Secrets or external secrets operator)

## Scaling

### Staging
- Min replicas: 2
- Max replicas: 5
- Scale on: CPU (70%), Memory (80%)

### Production
- Min replicas: 3
- Max replicas: 10
- Pod disruption budget: minAvailable 2
- Scale-down stabilization: 5 minutes
- Pod anti-affinity: Spread across nodes
