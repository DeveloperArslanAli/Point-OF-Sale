#!/bin/bash
# Deploy to staging environment
# Usage: ./deploy-staging.sh [image-tag]

set -euo pipefail

# Configuration
ENVIRONMENT="staging"
NAMESPACE="retail-pos-staging"
DEPLOYMENT_NAME="retail-pos-api"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-retail/pos-phython}"
IMAGE_TAG="${1:-latest}"
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Validate prerequisites
validate_prerequisites() {
    log_info "Validating prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check KUBECONFIG."
        exit 1
    fi
    
    log_info "Prerequisites validated."
}

# Create namespace if it doesn't exist
ensure_namespace() {
    log_info "Ensuring namespace exists: $NAMESPACE"
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
}

# Deploy application
deploy_application() {
    log_info "Deploying $DEPLOYMENT_NAME with image: $IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    
    # Update deployment image
    kubectl set image deployment/"$DEPLOYMENT_NAME" \
        api="$IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG" \
        -n "$NAMESPACE" 2>/dev/null || {
        log_warn "Deployment not found, creating from manifest..."
        kubectl apply -f "$(dirname "$0")/kubernetes/staging/" -n "$NAMESPACE"
    }
    
    log_info "Waiting for rollout to complete..."
    kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=300s
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    kubectl exec -n "$NAMESPACE" \
        "$(kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME" -o jsonpath='{.items[0].metadata.name}')" \
        -- alembic upgrade head
    
    log_info "Migrations completed."
}

# Run smoke tests
run_smoke_tests() {
    log_info "Running smoke tests..."
    
    # Get service URL
    SERVICE_URL=$(kubectl get svc "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "localhost")
    
    # Health check
    if curl -sf "http://$SERVICE_URL/health" > /dev/null; then
        log_info "✅ Health check passed"
    else
        log_error "❌ Health check failed"
        exit 1
    fi
    
    # API readiness check
    if curl -sf "http://$SERVICE_URL/api/v1/health" > /dev/null; then
        log_info "✅ API readiness check passed"
    else
        log_error "❌ API readiness check failed"
        exit 1
    fi
    
    log_info "Smoke tests passed."
}

# Main deployment flow
main() {
    log_info "=========================================="
    log_info "  Deploying to $ENVIRONMENT environment"
    log_info "  Image: $IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    log_info "=========================================="
    
    validate_prerequisites
    ensure_namespace
    deploy_application
    run_migrations
    run_smoke_tests
    
    log_info "=========================================="
    log_info "  ✅ Deployment to $ENVIRONMENT complete!"
    log_info "=========================================="
}

main "$@"
