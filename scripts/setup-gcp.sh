#!/usr/bin/env bash
# Setup script for GCP Cloud Run deployment with GitHub Actions OIDC
# Usage: ./scripts/setup-gcp.sh <github-owner/repo>
set -euo pipefail

PROJECT_ID="taa-platform"
REGION="us-central1"
REPO_NAME="taa"
SA_NAME="github-actions-deploy"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-actions-provider"

GITHUB_REPO="${1:?Usage: $0 <github-owner/repo>}"

echo "=== Setting up Cloud Run deployment for ${GITHUB_REPO} ==="

# Set project
gcloud config set project "$PROJECT_ID"

# Enable APIs
echo "Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iamcredentials.googleapis.com \
  iam.googleapis.com \
  secretmanager.googleapis.com

# Create Artifact Registry repository
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create "$REPO_NAME" \
  --repository-format=docker \
  --location="$REGION" \
  --description="TAA container images" \
  2>/dev/null || echo "Repository already exists"

# Create service account
echo "Creating service account..."
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="GitHub Actions Deploy" \
  2>/dev/null || echo "Service account already exists"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant roles
echo "Granting IAM roles..."
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role" \
    --quiet
done

# Create Workload Identity Pool
echo "Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create "$POOL_NAME" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  2>/dev/null || echo "Pool already exists"

# Create Workload Identity Provider
echo "Creating Workload Identity Provider..."
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  2>/dev/null || echo "Provider already exists"

# Allow GitHub repo to impersonate the service account
echo "Binding Workload Identity..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}" \
  --quiet

# Create secret for TAA_SECRET_KEY
echo "Creating secret for TAA_SECRET_KEY..."
if ! gcloud secrets describe taa-secret-key --quiet 2>/dev/null; then
  python3 -c "import secrets; print(secrets.token_urlsafe(64))" | \
    gcloud secrets create taa-secret-key --data-file=- --quiet
  echo "Secret created with auto-generated key"
else
  echo "Secret already exists"
fi

# Output GitHub Actions secrets
WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Add these as GitHub Actions secrets:"
echo "  WIF_PROVIDER:        ${WIF_PROVIDER}"
echo "  WIF_SERVICE_ACCOUNT: ${SA_EMAIL}"
echo ""
echo "After linking billing, the deploy workflow will:"
echo "  1. Run tests"
echo "  2. Build & push image to Artifact Registry"
echo "  3. Deploy to Cloud Run at https://taa-${PROJECT_ID}.run.app"
