#!/bin/bash
# =============================================================================
# Invoice Processing Pipeline - Legacy Resource Cleanup
# =============================================================================
# This script removes old/duplicate resources from eda-gemini-dev
#
# WARNING: This is DESTRUCTIVE! Review carefully before running.
#
# Usage:
#   ./cleanup-legacy.sh           # Dry run (shows what would be deleted)
#   ./cleanup-legacy.sh --execute # Actually delete resources
# =============================================================================

set -e

PROJECT_ID="eda-gemini-dev"
REGION="us-central1"
DRY_RUN=true

# Parse arguments
if [[ "$1" == "--execute" ]]; then
    DRY_RUN=false
    echo "⚠️  EXECUTING DELETION - Resources will be permanently removed!"
    echo ""
    read -p "Are you sure? Type 'yes' to continue: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "Aborted."
        exit 1
    fi
else
    echo "🔍 DRY RUN - No resources will be deleted"
    echo "   Run with --execute to actually delete resources"
    echo ""
fi

# Set project
gcloud config set project $PROJECT_ID --quiet

echo "============================================="
echo "Cleanup Legacy Resources from $PROJECT_ID"
echo "============================================="

# -----------------------------------------------------------------------------
# 1. Delete Legacy Cloud Run Services
# -----------------------------------------------------------------------------
echo ""
echo "[1/6] Cloud Run Services to delete:"

LEGACY_SERVICES=(
    "fnc-bigquery-writer-dev"
    "fnc-data-extractor-dev"
    "fnc-data-extractor-v2-dev"
    "fnc-invoice-classifier-dev"
    "fnc-tiff-converter-dev"
    "fnc-tiff-to-png-converter-dev"
)

for service in "${LEGACY_SERVICES[@]}"; do
    echo "  - $service"
    if [[ "$DRY_RUN" == false ]]; then
        gcloud run services delete "$service" --region="$REGION" --quiet 2>/dev/null || echo "    (already deleted or not found)"
    fi
done

# -----------------------------------------------------------------------------
# 2. Delete Legacy Pub/Sub Subscriptions (must delete before topics)
# -----------------------------------------------------------------------------
echo ""
echo "[2/6] Pub/Sub Subscriptions to delete:"

LEGACY_SUBSCRIPTIONS=(
    "sub-classified-to-extractor-dev"
    "sub-fnc-invoice-classifier-dev"
    "eventarc-us-central1-trigger-gcs-landing-dev-sub-703"
    "sub-extracted-to-writer-dev"
    "sub-converted-to-classifier-dev"
    "sub-monitoring-dev"
    "sub-fnc-tiff-converter-dev"
    "sub-classified-to-extractor-v2-dev"
    "sub-fnc-bigquery-writer-dev"
)

for sub in "${LEGACY_SUBSCRIPTIONS[@]}"; do
    echo "  - $sub"
    if [[ "$DRY_RUN" == false ]]; then
        gcloud pubsub subscriptions delete "$sub" --quiet 2>/dev/null || echo "    (already deleted or not found)"
    fi
done

# -----------------------------------------------------------------------------
# 3. Delete Legacy Pub/Sub Topics
# -----------------------------------------------------------------------------
echo ""
echo "[3/6] Pub/Sub Topics to delete:"

LEGACY_TOPICS=(
    "eda-gemini-dev-invoice-extracted"
    "eda-gemini-dev-invoice-converted"
    "eda-gemini-dev-invoice-loaded"
    "eda-gemini-dev-invoice-classified"
    "eda-gemini-dev-invoice-uploaded"
    "eda-gemini-dev-invoice-extracted-v2"
    "tpc-invoice-extracted-dev"
    "tpc-invoice-converted-dev"
    "tpc-invoice-classified-dev"
    "tpc-invoice-uploaded-dev"
    "tpc-invoice-loaded-dev"
    "tpc-gcs-notifications-dev"
    "tpc-gcs-notifications-dev-dlq"
    "tpc-invoice-loaded-dev-dlq"
    "tpc-invoice-classified-dev-dlq"
    "tpc-invoice-converted-dev-dlq"
    "tpc-invoice-uploaded-dev-dlq"
    "tpc-invoice-extracted-dev-dlq"
    "eventarc-us-central1-trigger-gcs-landing-dev-605"
)

for topic in "${LEGACY_TOPICS[@]}"; do
    echo "  - $topic"
    if [[ "$DRY_RUN" == false ]]; then
        gcloud pubsub topics delete "$topic" --quiet 2>/dev/null || echo "    (already deleted or not found)"
    fi
done

# -----------------------------------------------------------------------------
# 4. Delete Legacy GCS Buckets (WARNING: Deletes all contents!)
# -----------------------------------------------------------------------------
echo ""
echo "[4/6] GCS Buckets to delete (and their contents):"

LEGACY_BUCKETS=(
    "gs://eda-gemini-dev-archive"
    "gs://eda-gemini-dev-classified"
    "gs://eda-gemini-dev-converted"
    "gs://eda-gemini-dev-extracted"
    "gs://eda-gemini-dev-failed"
    "gs://eda-gemini-dev-landing"
    "gs://eda-gemini-dev-loaded"
    "gs://eda-gemini-dev-pipeline"
)

for bucket in "${LEGACY_BUCKETS[@]}"; do
    echo "  - $bucket"
    if [[ "$DRY_RUN" == false ]]; then
        gsutil -m rm -r "$bucket" 2>/dev/null || echo "    (already deleted or not found)"
    fi
done

# -----------------------------------------------------------------------------
# 5. Delete Legacy BigQuery Dataset
# -----------------------------------------------------------------------------
echo ""
echo "[5/6] BigQuery Datasets to delete:"

LEGACY_DATASETS=(
    "ds_bq_gemini_dev"
)

for dataset in "${LEGACY_DATASETS[@]}"; do
    echo "  - $dataset"
    if [[ "$DRY_RUN" == false ]]; then
        bq rm -r -f -d "$PROJECT_ID:$dataset" 2>/dev/null || echo "    (already deleted or not found)"
    fi
done

# -----------------------------------------------------------------------------
# 6. Delete Legacy Container Images
# -----------------------------------------------------------------------------
echo ""
echo "[6/6] Container Images to delete:"

LEGACY_IMAGES=(
    "gcr.io/eda-gemini-dev/fnc-data-extractor-v2-dev"
    "gcr.io/eda-gemini-dev/fnc-invoice-classifier-dev"
)

for image in "${LEGACY_IMAGES[@]}"; do
    echo "  - $image"
    if [[ "$DRY_RUN" == false ]]; then
        # Delete all tags/digests for this image
        gcloud container images list-tags "$image" --format="get(digest)" | while read digest; do
            gcloud container images delete "$image@$digest" --force-delete-tags --quiet 2>/dev/null || true
        done
    fi
done

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo "============================================="
if [[ "$DRY_RUN" == true ]]; then
    echo "✅ DRY RUN COMPLETE"
    echo ""
    echo "To execute deletion, run:"
    echo "  ./cleanup-legacy.sh --execute"
else
    echo "✅ CLEANUP COMPLETE"
    echo ""
    echo "Remaining resources (KEEP):"
    echo "  Cloud Run:    bigquery-writer, data-extractor, invoice-classifier, tiff-to-png-converter"
    echo "  Topics:       invoice-uploaded, invoice-converted, invoice-classified, invoice-extracted (+ DLQs)"
    echo "  Subscriptions: tiff-to-png-sub, classifier-sub, extractor-sub, writer-sub"
    echo "  Buckets:      eda-gemini-dev-invoices-{input,processed,archive,failed}"
    echo "  BigQuery:     invoices dataset"
fi
echo "============================================="
