#!/bin/bash
# =============================================================================
# Invoice Processing Pipeline - Deploy Cloud Run Functions
# =============================================================================
# Builds and deploys all 4 functions using Cloud Build
# Run setup-infra.sh FIRST to create buckets, topics, and tables
# =============================================================================

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-eda-gemini-dev}"
REGION="${GCP_REGION:-us-central1}"

# Derived names
BUCKET_PREFIX="${PROJECT_ID}-invoices"
INPUT_BUCKET="${BUCKET_PREFIX}-input"
PROCESSED_BUCKET="${BUCKET_PREFIX}-processed"
ARCHIVE_BUCKET="${BUCKET_PREFIX}-archive"
FAILED_BUCKET="${BUCKET_PREFIX}-failed"

# Topics
UPLOADED_TOPIC="invoice-uploaded"
CONVERTED_TOPIC="invoice-converted"
CLASSIFIED_TOPIC="invoice-classified"
EXTRACTED_TOPIC="invoice-extracted"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================="
echo "Deploying Cloud Run Functions"
echo "============================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "============================================="

cd "$PROJECT_DIR"

# Common environment variables
ENV_VARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
ENV_VARS="$ENV_VARS,GCP_REGION=$REGION"
ENV_VARS="$ENV_VARS,INPUT_BUCKET=$INPUT_BUCKET"
ENV_VARS="$ENV_VARS,PROCESSED_BUCKET=$PROCESSED_BUCKET"
ENV_VARS="$ENV_VARS,ARCHIVE_BUCKET=$ARCHIVE_BUCKET"
ENV_VARS="$ENV_VARS,FAILED_BUCKET=$FAILED_BUCKET"
ENV_VARS="$ENV_VARS,UPLOADED_TOPIC=$UPLOADED_TOPIC"
ENV_VARS="$ENV_VARS,CONVERTED_TOPIC=$CONVERTED_TOPIC"
ENV_VARS="$ENV_VARS,CLASSIFIED_TOPIC=$CLASSIFIED_TOPIC"
ENV_VARS="$ENV_VARS,EXTRACTED_TOPIC=$EXTRACTED_TOPIC"
ENV_VARS="$ENV_VARS,BQ_DATASET=invoices"
ENV_VARS="$ENV_VARS,GEMINI_MODEL=gemini-2.0-flash-exp"

# Helper function to build and deploy
deploy_function() {
    local NAME=$1
    local DOCKERFILE=$2
    local MEMORY=$3
    local TIMEOUT=$4

    echo ""
    echo "Building $NAME..."

    # Create a temporary cloudbuild.yaml for this function
    cat > /tmp/cloudbuild-${NAME}.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/$NAME:latest'
      - '-f'
      - '$DOCKERFILE'
      - '.'
images:
  - 'gcr.io/$PROJECT_ID/$NAME:latest'
EOF

    gcloud builds submit \
        --project="$PROJECT_ID" \
        --config="/tmp/cloudbuild-${NAME}.yaml" \
        --quiet \
        .

    echo "Deploying $NAME to Cloud Run..."
    gcloud run deploy "$NAME" \
        --image="gcr.io/$PROJECT_ID/$NAME:latest" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --platform=managed \
        --memory="$MEMORY" \
        --timeout="$TIMEOUT" \
        --max-instances=10 \
        --set-env-vars="$ENV_VARS" \
        --no-allow-unauthenticated \
        --quiet

    echo "✓ $NAME deployed successfully"
}

# Function 1: tiff-to-png-converter
echo ""
echo "[1/4] tiff-to-png-converter"
deploy_function "tiff-to-png-converter" "deploy/tiff_to_png.Dockerfile" "1Gi" "300"

# Function 2: invoice-classifier
echo ""
echo "[2/4] invoice-classifier"
deploy_function "invoice-classifier" "deploy/invoice_classifier.Dockerfile" "1Gi" "300"

# Function 3: data-extractor
echo ""
echo "[3/4] data-extractor"
deploy_function "data-extractor" "deploy/data_extractor.Dockerfile" "2Gi" "540"

# Function 4: bigquery-writer
echo ""
echo "[4/4] bigquery-writer"
deploy_function "bigquery-writer" "deploy/bigquery_writer.Dockerfile" "512Mi" "120"

echo ""
echo "============================================="
echo "✅ All Functions Deployed!"
echo "============================================="
echo ""
echo "Next step: Create Pub/Sub subscriptions with:"
echo "  ./scripts/setup-triggers.sh"
echo ""
