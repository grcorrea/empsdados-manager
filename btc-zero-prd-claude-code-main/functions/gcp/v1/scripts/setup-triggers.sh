#!/bin/bash
# =============================================================================
# Invoice Processing Pipeline - Setup Pub/Sub Triggers
# =============================================================================
# Creates Pub/Sub subscriptions that trigger Cloud Run functions
# Run AFTER deploy-functions.sh
# =============================================================================

set -e

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-eda-gemini-dev}"
REGION="${GCP_REGION:-us-central1}"

echo "============================================="
echo "Setting up Pub/Sub Triggers"
echo "============================================="

# Get service account for push authentication
SA_EMAIL=$(gcloud iam service-accounts list \
    --project="$PROJECT_ID" \
    --filter="displayName~'Compute Engine'" \
    --format="value(email)" | head -1)

if [ -z "$SA_EMAIL" ]; then
    SA_EMAIL="${PROJECT_ID}@appspot.gserviceaccount.com"
fi

echo "Using service account: $SA_EMAIL"
echo ""

# Grant invoker role to service account for all functions
echo "Granting Cloud Run invoker role..."
for SVC in tiff-to-png-converter invoice-classifier data-extractor bigquery-writer; do
    gcloud run services add-iam-policy-binding "$SVC" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/run.invoker" \
        --quiet 2>/dev/null || true
done

# Create subscriptions
create_subscription() {
    local SUB_NAME=$1
    local TOPIC=$2
    local SERVICE=$3
    local ACK_DEADLINE=$4

    SERVICE_URL=$(gcloud run services describe "$SERVICE" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        --format="value(status.url)")

    if gcloud pubsub subscriptions describe "$SUB_NAME" --project="$PROJECT_ID" &>/dev/null; then
        echo "  ✓ $SUB_NAME (exists)"
    else
        gcloud pubsub subscriptions create "$SUB_NAME" \
            --topic="$TOPIC" \
            --push-endpoint="$SERVICE_URL" \
            --push-auth-service-account="$SA_EMAIL" \
            --ack-deadline="$ACK_DEADLINE" \
            --project="$PROJECT_ID" \
            --quiet
        echo "  ✓ $SUB_NAME (created)"
    fi
}

echo ""
echo "Creating Pub/Sub subscriptions..."
create_subscription "tiff-to-png-sub" "invoice-uploaded" "tiff-to-png-converter" 300
create_subscription "classifier-sub" "invoice-converted" "invoice-classifier" 300
create_subscription "extractor-sub" "invoice-classified" "data-extractor" 540
create_subscription "writer-sub" "invoice-extracted" "bigquery-writer" 120

echo ""
echo "============================================="
echo "✅ Triggers Configured!"
echo "============================================="
echo ""
echo "Pipeline is ready! Test with:"
echo "  gsutil cp your_invoice.tiff gs://${PROJECT_ID}-invoices-input/"
echo ""
echo "Monitor logs:"
echo "  gcloud logging read 'resource.type=\"cloud_run_revision\"' --limit=50 --project=$PROJECT_ID"
echo ""
