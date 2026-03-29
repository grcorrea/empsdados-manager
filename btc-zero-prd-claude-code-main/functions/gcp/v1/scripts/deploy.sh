#!/bin/bash
# =============================================================================
# Invoice Processing Pipeline - GCP Deployment Script
# =============================================================================
# Prerequisites:
#   - gcloud CLI authenticated
#   - APIs enabled: run.googleapis.com, pubsub.googleapis.com, storage.googleapis.com,
#                   bigquery.googleapis.com, aiplatform.googleapis.com
# =============================================================================

set -e  # Exit on error

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-eda-gemini-dev}"
REGION="${GCP_REGION:-us-central1}"
ENV="${DEPLOY_ENV:-dev}"

# Derived names
BUCKET_PREFIX="${PROJECT_ID}-invoices"
INPUT_BUCKET="${BUCKET_PREFIX}-input"
PROCESSED_BUCKET="${BUCKET_PREFIX}-processed"
ARCHIVE_BUCKET="${BUCKET_PREFIX}-archive"
FAILED_BUCKET="${BUCKET_PREFIX}-failed"

# Pub/Sub topics
UPLOADED_TOPIC="invoice-uploaded"
CONVERTED_TOPIC="invoice-converted"
CLASSIFIED_TOPIC="invoice-classified"
EXTRACTED_TOPIC="invoice-extracted"

# BigQuery
BQ_DATASET="invoices"
BQ_LOCATION="US"

echo "============================================="
echo "Invoice Pipeline Deployment"
echo "============================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Env:      $ENV"
echo "============================================="

# -----------------------------------------------------------------------------
# Step 0: Enable Required APIs
# -----------------------------------------------------------------------------
echo ""
echo "[Step 0] Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    pubsub.googleapis.com \
    storage.googleapis.com \
    bigquery.googleapis.com \
    aiplatform.googleapis.com \
    cloudbuild.googleapis.com \
    --project="$PROJECT_ID" \
    --quiet

# -----------------------------------------------------------------------------
# Step 1: Create GCS Buckets
# -----------------------------------------------------------------------------
echo ""
echo "[Step 1] Creating GCS buckets..."

for BUCKET in "$INPUT_BUCKET" "$PROCESSED_BUCKET" "$ARCHIVE_BUCKET" "$FAILED_BUCKET"; do
    if gsutil ls -b "gs://$BUCKET" &>/dev/null; then
        echo "  ✓ Bucket exists: $BUCKET"
    else
        echo "  Creating bucket: $BUCKET"
        gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$BUCKET"
    fi
done

# -----------------------------------------------------------------------------
# Step 2: Create Pub/Sub Topics
# -----------------------------------------------------------------------------
echo ""
echo "[Step 2] Creating Pub/Sub topics..."

for TOPIC in "$UPLOADED_TOPIC" "$CONVERTED_TOPIC" "$CLASSIFIED_TOPIC" "$EXTRACTED_TOPIC"; do
    if gcloud pubsub topics describe "$TOPIC" --project="$PROJECT_ID" &>/dev/null; then
        echo "  ✓ Topic exists: $TOPIC"
    else
        echo "  Creating topic: $TOPIC"
        gcloud pubsub topics create "$TOPIC" --project="$PROJECT_ID"
    fi
done

# Create Dead Letter Topics
for TOPIC in "$UPLOADED_TOPIC" "$CONVERTED_TOPIC" "$CLASSIFIED_TOPIC" "$EXTRACTED_TOPIC"; do
    DLQ_TOPIC="${TOPIC}-dlq"
    if gcloud pubsub topics describe "$DLQ_TOPIC" --project="$PROJECT_ID" &>/dev/null; then
        echo "  ✓ DLQ exists: $DLQ_TOPIC"
    else
        echo "  Creating DLQ: $DLQ_TOPIC"
        gcloud pubsub topics create "$DLQ_TOPIC" --project="$PROJECT_ID"
    fi
done

# -----------------------------------------------------------------------------
# Step 3: Create BigQuery Dataset and Tables
# -----------------------------------------------------------------------------
echo ""
echo "[Step 3] Creating BigQuery dataset and tables..."

# Create dataset
if bq show --project_id="$PROJECT_ID" "$BQ_DATASET" &>/dev/null; then
    echo "  ✓ Dataset exists: $BQ_DATASET"
else
    echo "  Creating dataset: $BQ_DATASET"
    bq mk --project_id="$PROJECT_ID" --location="$BQ_LOCATION" "$BQ_DATASET"
fi

# Create invoices table
INVOICES_TABLE="${BQ_DATASET}.extracted_invoices"
if bq show --project_id="$PROJECT_ID" "$INVOICES_TABLE" &>/dev/null; then
    echo "  ✓ Table exists: $INVOICES_TABLE"
else
    echo "  Creating table: $INVOICES_TABLE"
    bq mk --project_id="$PROJECT_ID" --table "$INVOICES_TABLE" \
        invoice_id:STRING,vendor_name:STRING,vendor_type:STRING,invoice_date:DATE,due_date:DATE,currency:STRING,subtotal:FLOAT,tax_amount:FLOAT,commission_rate:FLOAT,commission_amount:FLOAT,total_amount:FLOAT,line_items_count:INTEGER,source_file:STRING,extraction_model:STRING,extraction_latency_ms:INTEGER,confidence_score:FLOAT,created_at:TIMESTAMP,updated_at:TIMESTAMP
fi

# Create line_items table
LINE_ITEMS_TABLE="${BQ_DATASET}.line_items"
if bq show --project_id="$PROJECT_ID" "$LINE_ITEMS_TABLE" &>/dev/null; then
    echo "  ✓ Table exists: $LINE_ITEMS_TABLE"
else
    echo "  Creating table: $LINE_ITEMS_TABLE"
    bq mk --project_id="$PROJECT_ID" --table "$LINE_ITEMS_TABLE" \
        invoice_id:STRING,line_number:INTEGER,description:STRING,quantity:INTEGER,unit_price:FLOAT,amount:FLOAT,created_at:TIMESTAMP
fi

# Create metrics table
METRICS_TABLE="${BQ_DATASET}.extraction_metrics"
if bq show --project_id="$PROJECT_ID" "$METRICS_TABLE" &>/dev/null; then
    echo "  ✓ Table exists: $METRICS_TABLE"
else
    echo "  Creating table: $METRICS_TABLE"
    bq mk --project_id="$PROJECT_ID" --table "$METRICS_TABLE" \
        invoice_id:STRING,vendor_type:STRING,source_file:STRING,extraction_model:STRING,extraction_latency_ms:INTEGER,confidence_score:FLOAT,success:BOOLEAN,error_message:STRING,created_at:TIMESTAMP
fi

# -----------------------------------------------------------------------------
# Step 4: Set up GCS Notification to Pub/Sub
# -----------------------------------------------------------------------------
echo ""
echo "[Step 4] Configuring GCS notification..."

# Check if notification exists
EXISTING_NOTIF=$(gsutil notification list "gs://$INPUT_BUCKET" 2>/dev/null | grep "$UPLOADED_TOPIC" || true)
if [ -n "$EXISTING_NOTIF" ]; then
    echo "  ✓ GCS notification already configured"
else
    echo "  Creating GCS notification for uploads"
    gsutil notification create \
        -t "$UPLOADED_TOPIC" \
        -f json \
        -e OBJECT_FINALIZE \
        "gs://$INPUT_BUCKET"
fi

# -----------------------------------------------------------------------------
# Step 5: Deploy Cloud Run Functions
# -----------------------------------------------------------------------------
echo ""
echo "[Step 5] Deploying Cloud Run functions..."

# Common environment variables
COMMON_ENV="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCP_REGION=$REGION,INPUT_BUCKET=$INPUT_BUCKET,PROCESSED_BUCKET=$PROCESSED_BUCKET,ARCHIVE_BUCKET=$ARCHIVE_BUCKET,FAILED_BUCKET=$FAILED_BUCKET,UPLOADED_TOPIC=$UPLOADED_TOPIC,CONVERTED_TOPIC=$CONVERTED_TOPIC,CLASSIFIED_TOPIC=$CLASSIFIED_TOPIC,EXTRACTED_TOPIC=$EXTRACTED_TOPIC,BQ_DATASET=$BQ_DATASET,GEMINI_MODEL=gemini-2.0-flash-exp"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$SCRIPT_DIR")/src"

echo ""
echo "  [5.1] Deploying tiff-to-png-converter..."
gcloud run deploy tiff-to-png-converter \
    --source="$SRC_DIR/functions/tiff_to_png" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --platform=managed \
    --memory=1Gi \
    --timeout=300 \
    --max-instances=10 \
    --set-env-vars="$COMMON_ENV" \
    --no-allow-unauthenticated \
    --quiet

# Create Pub/Sub subscription for tiff-to-png-converter
echo "  Creating Pub/Sub trigger for tiff-to-png-converter..."
SERVICE_URL=$(gcloud run services describe tiff-to-png-converter --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
gcloud pubsub subscriptions create tiff-to-png-converter-sub \
    --topic="$UPLOADED_TOPIC" \
    --push-endpoint="$SERVICE_URL" \
    --push-auth-service-account="$(gcloud iam service-accounts list --project=$PROJECT_ID --filter='displayName:Compute Engine' --format='value(email)' | head -1)" \
    --ack-deadline=300 \
    --project="$PROJECT_ID" \
    2>/dev/null || echo "  (subscription may already exist)"

echo ""
echo "  [5.2] Deploying invoice-classifier..."
gcloud run deploy invoice-classifier \
    --source="$SRC_DIR/functions/invoice_classifier" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --platform=managed \
    --memory=1Gi \
    --timeout=300 \
    --max-instances=10 \
    --set-env-vars="$COMMON_ENV" \
    --no-allow-unauthenticated \
    --quiet

# Create Pub/Sub subscription for invoice-classifier
echo "  Creating Pub/Sub trigger for invoice-classifier..."
SERVICE_URL=$(gcloud run services describe invoice-classifier --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
gcloud pubsub subscriptions create invoice-classifier-sub \
    --topic="$CONVERTED_TOPIC" \
    --push-endpoint="$SERVICE_URL" \
    --push-auth-service-account="$(gcloud iam service-accounts list --project=$PROJECT_ID --filter='displayName:Compute Engine' --format='value(email)' | head -1)" \
    --ack-deadline=300 \
    --project="$PROJECT_ID" \
    2>/dev/null || echo "  (subscription may already exist)"

echo ""
echo "  [5.3] Deploying data-extractor..."
gcloud run deploy data-extractor \
    --source="$SRC_DIR/functions/data_extractor" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --platform=managed \
    --memory=2Gi \
    --timeout=540 \
    --max-instances=10 \
    --set-env-vars="$COMMON_ENV" \
    --no-allow-unauthenticated \
    --quiet

# Create Pub/Sub subscription for data-extractor
echo "  Creating Pub/Sub trigger for data-extractor..."
SERVICE_URL=$(gcloud run services describe data-extractor --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
gcloud pubsub subscriptions create data-extractor-sub \
    --topic="$CLASSIFIED_TOPIC" \
    --push-endpoint="$SERVICE_URL" \
    --push-auth-service-account="$(gcloud iam service-accounts list --project=$PROJECT_ID --filter='displayName:Compute Engine' --format='value(email)' | head -1)" \
    --ack-deadline=540 \
    --project="$PROJECT_ID" \
    2>/dev/null || echo "  (subscription may already exist)"

echo ""
echo "  [5.4] Deploying bigquery-writer..."
gcloud run deploy bigquery-writer \
    --source="$SRC_DIR/functions/bigquery_writer" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --platform=managed \
    --memory=512Mi \
    --timeout=120 \
    --max-instances=10 \
    --set-env-vars="$COMMON_ENV" \
    --no-allow-unauthenticated \
    --quiet

# Create Pub/Sub subscription for bigquery-writer
echo "  Creating Pub/Sub trigger for bigquery-writer..."
SERVICE_URL=$(gcloud run services describe bigquery-writer --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
gcloud pubsub subscriptions create bigquery-writer-sub \
    --topic="$EXTRACTED_TOPIC" \
    --push-endpoint="$SERVICE_URL" \
    --push-auth-service-account="$(gcloud iam service-accounts list --project=$PROJECT_ID --filter='displayName:Compute Engine' --format='value(email)' | head -1)" \
    --ack-deadline=120 \
    --project="$PROJECT_ID" \
    2>/dev/null || echo "  (subscription may already exist)"

# -----------------------------------------------------------------------------
# Step 6: Summary
# -----------------------------------------------------------------------------
echo ""
echo "============================================="
echo "✅ Deployment Complete!"
echo "============================================="
echo ""
echo "Resources Created:"
echo "  • 4 GCS Buckets:"
echo "    - gs://$INPUT_BUCKET (upload invoices here)"
echo "    - gs://$PROCESSED_BUCKET"
echo "    - gs://$ARCHIVE_BUCKET"
echo "    - gs://$FAILED_BUCKET"
echo ""
echo "  • 4 Pub/Sub Topics + 4 DLQ Topics"
echo ""
echo "  • BigQuery Tables:"
echo "    - $PROJECT_ID.$BQ_DATASET.extracted_invoices"
echo "    - $PROJECT_ID.$BQ_DATASET.line_items"
echo "    - $PROJECT_ID.$BQ_DATASET.extraction_metrics"
echo ""
echo "  • 4 Cloud Run Services:"
echo "    - tiff-to-png-converter"
echo "    - invoice-classifier"
echo "    - data-extractor"
echo "    - bigquery-writer"
echo ""
echo "To test the pipeline:"
echo "  gsutil cp sample_invoice.tiff gs://$INPUT_BUCKET/"
echo ""
echo "To view logs:"
echo "  gcloud logging read 'resource.type=\"cloud_run_revision\"' --limit=50"
echo ""
