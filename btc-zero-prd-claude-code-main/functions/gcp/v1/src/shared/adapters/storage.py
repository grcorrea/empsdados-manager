"""Storage adapter with Protocol interface and GCS implementation.

The Protocol pattern enables:
- Unit tests with mock storage (no GCP calls)
- Integration tests with real GCS
- Future portability to other cloud providers
"""

from typing import Protocol


class StorageAdapter(Protocol):
    """Protocol for storage operations - enables testing with mocks."""

    def read(self, bucket: str, path: str) -> bytes:
        """Read file from storage.

        Args:
            bucket: Bucket name (without gs:// prefix)
            path: File path within bucket

        Returns:
            File contents as bytes
        """
        ...

    def write(self, bucket: str, path: str, data: bytes, content_type: str) -> str:
        """Write file to storage.

        Args:
            bucket: Bucket name
            path: File path within bucket
            data: File contents as bytes
            content_type: MIME type (e.g., "image/png")

        Returns:
            GCS URI (gs://bucket/path)
        """
        ...

    def copy(
        self, source_bucket: str, source_path: str, dest_bucket: str, dest_path: str
    ) -> str:
        """Copy file between buckets.

        Args:
            source_bucket: Source bucket name
            source_path: Source file path
            dest_bucket: Destination bucket name
            dest_path: Destination file path

        Returns:
            Destination GCS URI
        """
        ...

    def delete(self, bucket: str, path: str) -> bool:
        """Delete file from storage.

        Args:
            bucket: Bucket name
            path: File path

        Returns:
            True if deleted successfully
        """
        ...

    def exists(self, bucket: str, path: str) -> bool:
        """Check if file exists.

        Args:
            bucket: Bucket name
            path: File path

        Returns:
            True if file exists
        """
        ...


class GCSAdapter:
    """Google Cloud Storage implementation."""

    def __init__(self, project_id: str | None = None):
        """Initialize GCS client.

        Args:
            project_id: GCP project ID (uses ADC default if None)
        """
        from google.cloud import storage

        self._client = storage.Client(project=project_id)
        self._project_id = project_id

    def read(self, bucket: str, path: str) -> bytes:
        """Read file from GCS."""
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(path)
        return blob.download_as_bytes()

    def write(self, bucket: str, path: str, data: bytes, content_type: str) -> str:
        """Write file to GCS."""
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(path)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{bucket}/{path}"

    def copy(
        self, source_bucket: str, source_path: str, dest_bucket: str, dest_path: str
    ) -> str:
        """Copy file between GCS buckets."""
        source_bucket_obj = self._client.bucket(source_bucket)
        source_blob = source_bucket_obj.blob(source_path)
        dest_bucket_obj = self._client.bucket(dest_bucket)
        source_bucket_obj.copy_blob(source_blob, dest_bucket_obj, dest_path)
        return f"gs://{dest_bucket}/{dest_path}"

    def delete(self, bucket: str, path: str) -> bool:
        """Delete file from GCS."""
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(path)
        blob.delete()
        return True

    def exists(self, bucket: str, path: str) -> bool:
        """Check if file exists in GCS."""
        bucket_obj = self._client.bucket(bucket)
        blob = bucket_obj.blob(path)
        return blob.exists()
