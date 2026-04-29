#!/bin/bash
# Deploy to production environment
# Usage: ./deploy-production.sh [image-tag]
# 
# IMPORTANT: This script requires manual approval before deployment.
# Ensure all staging tests have passed before deploying to production.

set -euo pipefail

# Configuration
ENVIRONMENT="production"
NAMESPACE="retail-pos-production"
DEPLOYMENT_NAME="retail-pos-api"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-retail/pos-phython}"
IMAGE_TAG="${1:-latest}"
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
ROLLBACK_ON_FAILURE="${ROLLBACK_ON_FAILURE:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Validate prerequisites
validate_prerequisites() {
    log_step "1/7 Validating prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check KUBECONFIG."
        exit 1
    fi
    
    # Verify namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Production namespace $NAMESPACE does not exist. Please create it first."
        exit 1
    fi
    
    log_info "Prerequisites validated."
}

# Confirm deployment
confirm_deployment() {
    log_step "2/7 Confirming deployment..."
    
    if [[ "${SKIP_CONFIRMATION:-false}" != "true" ]]; then
        echo ""
        log_warn "⚠️  WARNING: You are about to deploy to PRODUCTION!"
        echo ""
        echo "  Image: $IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
        echo "  Namespace: $NAMESPACE"
        echo ""
        read -p "Are you sure you want to proceed? (yes/no): " confirmation
        
        if [[ "$confirmation" != "yes" ]]; then
            log_info "Deployment cancelled by user."
            exit 0
        fi
    fi
    
    log_info "Deployment confirmed."
}

# Create backup of current state
create_backup() {
    log_step "3/7 Creating backup of current state..."
    
    BACKUP_DIR="/tmp/retail-pos-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Save current deployment state
    kubectl get deployment "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/deployment.yaml" 2>/dev/null || true
    
    # Save current revision for rollback
    CURRENT_REVISION=$(kubectl rollout history deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --revision=0 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
    echo "$CURRENT_REVISION" > "$BACKUP_DIR/revision.txt"
    
    log_info "Backup created at: $BACKUP_DIR"
    export BACKUP_DIR
    export CURRENT_REVISION
}

# Deploy application
deploy_application() {
    log_step "4/7 Deploying application..."
    
    log_info "Deploying $DEPLOYMENT_NAME with image: $IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    
    # Update deployment image
    kubectl set image deployment/"$DEPLOYMENT_NAME" \
        api="$IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG" \
        -n "$NAMESPACE"
    
    # Add annotation for tracking
    kubectl annotate deployment/"$DEPLOYMENT_NAME" \
        kubernetes.io/change-cause="Deployed via deploy-production.sh at $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --overwrite \
        -n "$NAMESPACE"
    
    log_info "Waiting for rollout to complete..."
    if ! kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=600s; then
        log_error "Deployment failed!"
        if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
            log_warn "Initiating automatic rollback..."
            kubectl rollout undo deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"
            kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=300s
            log_info "Rollback completed."
        fi
        exit 1
    fi
    
    log_info "Deployment completed."
}

# Run database migrations
run_migrations() {
    log_step "5/7 Running database migrations..."
    
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l app="$DEPLOYMENT_NAME" -o jsonpath='{.items[0].metadata.name}')
    
    if ! kubectl exec -n "$NAMESPACE" "$POD_NAME" -- alembic upgrade head; then
        log_error "Migration failed!"
        if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
            log_warn "Initiating automatic rollback..."
            kubectl rollout undo deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"
            kubectl rollout status deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE" --timeout=300s
        fi
        exit 1
    fi
    
    log_info "Migrations completed."
}

# Run health checks
run_health_checks() {
    log_step "6/7 Running health checks..."
    
    # Get service URL (adjust based on your ingress/service setup)
    SERVICE_URL=$(kubectl get svc "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [[ -z "$SERVICE_URL" ]]; then
        SERVICE_URL=$(kubectl get svc "$DEPLOYMENT_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}')
    fi
    
    # Wait for service to be ready
    sleep 10
    
    # Health check with retries
    for i in {1..5}; do
        if curl -sf "http://$SERVICE_URL/health" > /dev/null; then
            log_info "✅ Health check passed (attempt $i)"
            break
        else
            log_warn "Health check failed (attempt $i/5)"
            sleep 5
        fi
        
        if [[ $i -eq 5 ]]; then
            log_error "❌ Health check failed after 5 attempts"
            if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
                log_warn "Initiating automatic rollback..."
                kubectl rollout undo deployment/"$DEPLOYMENT_NAME" -n "$NAMESPACE"
            fi
            exit 1
        fi
    done
    
    # API endpoint check
    if curl -sf "http://$SERVICE_URL/api/v1/health" > /dev/null; then
        log_info "✅ API endpoint check passed"
    else
        log_warn "⚠️ API endpoint check failed (non-critical)"
    fi
    
    # Metrics endpoint check
    if curl -sf "http://$SERVICE_URL/metrics" > /dev/null; then
        log_info "✅ Metrics endpoint available"
    else
        log_warn "⚠️ Metrics endpoint not available"
    fi
    
    log_info "Health checks completed."
}

# Create release tag
create_release_tag() {
    log_step "7/7 Creating release tag..."
    
    VERSION="v$(date +%Y.%m.%d)-$(echo "$IMAGE_TAG" | cut -c1-7)"
    
    log_info "Deployment successful. Release: $VERSION"
    echo "$VERSION" > /tmp/release-version.txt
    
    # Optionally create git tag (requires git access)
    if command -v git &> /dev/null && [[ "${CREATE_GIT_TAG:-false}" == "true" ]]; then
        git tag -a "$VERSION" -m "Production deployment $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        git push origin "$VERSION"
        log_info "Git tag created: $VERSION"
    fi
}

# Main deployment flow
main() {
    echo ""
    log_info "=========================================="
    log_info "  PRODUCTION DEPLOYMENT"
    log_info "  Image: $IMAGE_REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    log_info "=========================================="
    echo ""
    
    validate_prerequisites
    confirm_deployment
    create_backup
    deploy_application
    run_migrations
    run_health_checks
    create_release_tag
    
    echo ""
    log_info "=========================================="
    log_info "  ✅ Production deployment successful!"
    log_info "=========================================="
    echo ""
}

main "$@"
