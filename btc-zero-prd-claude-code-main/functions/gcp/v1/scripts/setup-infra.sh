#!/bin/bash
# =============================================================================
# Invoice Processing Pipeline - Infrastructure Setup
# =============================================================================
# Creates GCS buckets, Pub/Sub topics, and BigQuery tables
# Run this BEFORE deploying Cloud Run functions
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

# Pub/Sub topics
UPLOADED_TOPIC="invoice-uploaded"
CONVERTED_TOPIC="invoice-converted"
CLASSIFIED_TOPIC="invoice-classified"
EXTRACTED_TOPIC="invoice-extracted"

# BigQuery
BQ_DATASET="invoices"
BQ_LOCATION="US"

echo "============================================="
echo "Infrastructure Setup for Invoice Pipeline"
echo "============================================="
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "============================================="

# Enable APIs
echo ""
echo "[1/5] Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    pubsub.googleapis.com \
    storage.googleapis.com \
    bigquery.googleapis.com \
    aiplatform.googleapis.com \
    cloudbuild.googleapis.com \
    --project="$PROJECT_ID" \
    --quiet

# Create GCS Buckets
echo ""
echo "[2/5] Creating GCS buckets..."
for BUCKET in "$INPUT_BUCKET" "$PROCESSED_BUCKET" "$ARCHIVE_BUCKET" "$FAILED_BUCKET"; do
    if gsutil ls -b "gs://$BUCKET" &>/dev/null; then
        echo "  ✓ $BUCKET (exists)"
    else
        gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://$BUCKET"
        echo "  ✓ $BUCKET (created)"
    fi
done

# Create Pub/Sub Topics
echo ""
echo "[3/5] Creating Pub/Sub topics..."
for TOPIC in "$UPLOADED_TOPIC" "$CONVERTED_TOPIC" "$CLASSIFIED_TOPIC" "$EXTRACTED_TOPIC"; do
    if gcloud pubsub topics describe "$TOPIC" --project="$PROJECT_ID" &>/dev/null; then
        echo "  ✓ $TOPIC (exists)"
    else
        gcloud pubsub topics create "$TOPIC" --project="$PROJECT_ID" --quiet
        echo "  ✓ $TOPIC (created)"
    fi

    # Create DLQ
    DLQ="${TOPIC}-dlq"
    if gcloud pubsub topics describe "$DLQ" --project="$PROJECT_ID" &>/dev/null; then
        echo "  ✓ $DLQ (exists)"
    else
        gcloud pubsub topics create "$DLQ" --project="$PROJECT_ID" --quiet
        echo "  ✓ $DLQ (created)"
    fi
done

# Create BigQuery Dataset and Tables
echo ""
echo "[4/5] Creating BigQuery dataset and tables..."

if bq show --project_id="$PROJECT_ID" "$BQ_DATASET" &>/dev/null; then
    echo "  ✓ Dataset $BQ_DATASET (exists)"
else
    bq mk --project_id="$PROJECT_ID" --location="$BQ_LOCATION" "$BQ_DATASET"
    echo "  ✓ Dataset $BQ_DATASET (created)"
fi

# Invoices table
TABLE="${BQ_DATASET}.extracted_invoices"
if bq show --project_id="$PROJECT_ID" "$TABLE" &>/dev/null; then
    echo "  ✓ Table $TABLE (exists)"
else
    bq mk --project_id="$PROJECT_ID" --table "$TABLE" \
        invoice_id:STRING,vendor_name:STRING,vendor_type:STRING,invoice_date:DATE,due_date:DATE,currency:STRING,subtotal:FLOAT,tax_amount:FLOAT,commission_rate:FLOAT,commission_amount:FLOAT,total_amount:FLOAT,line_items_count:INTEGER,source_file:STRING,extraction_model:STRING,extraction_latency_ms:INTEGER,confidence_score:FLOAT,created_at:TIMESTAMP,updated_at:TIMESTAMP
    echo "  ✓ Table $TABLE (created)"
fi

# Line items table
TABLE="${BQ_DATASET}.line_items"
if bq show --project_id="$PROJECT_ID" "$TABLE" &>/dev/null; then
    echo "  ✓ Table $TABLE (exists)"
else
    bq mk --project_id="$PROJECT_ID" --table "$TABLE" \
        invoice_id:STRING,line_number:INTEGER,description:STRING,quantity:INTEGER,unit_price:FLOAT,amount:FLOAT,created_at:TIMESTAMP
    echo "  ✓ Table $TABLE (created)"
fi

# Metrics table
TABLE="${BQ_DATASET}.extraction_metrics"
if bq show --project_id="$PROJECT_ID" "$TABLE" &>/dev/null; then
    echo "  ✓ Table $TABLE (exists)"
else
    bq mk --project_id="$PROJECT_ID" --table "$TABLE" \
        invoice_id:STRING,vendor_type:STRING,source_file:STRING,extraction_model:STRING,extraction_latency_ms:INTEGER,confidence_score:FLOAT,success:BOOLEAN,error_message:STRING,created_at:TIMESTAMP
    echo "  ✓ Table $TABLE (created)"
fi

# Configure GCS notification
echo ""
echo "[5/5] Configuring GCS notification..."
EXISTING=$(gsutil notification list "gs://$INPUT_BUCKET" 2>/dev/null | grep "$UPLOADED_TOPIC" || true)
if [ -n "$EXISTING" ]; then
    echo "  ✓ GCS → Pub/Sub notification (exists)"
else
    gsutil notification create -t "$UPLOADED_TOPIC" -f json -e OBJECT_FINALIZE "gs://$INPUT_BUCKET"
    echo "  ✓ GCS → Pub/Sub notification (created)"
fi

echo ""
echo "============================================="
echo "✅ Infrastructure Ready!"
echo "============================================="
echo ""
echo "Next step: Deploy functions with:"
echo "  ./scripts/deploy-functions.sh"
echo ""
