"""GCS utility functions.

Provides common utilities for working with Google Cloud Storage.
"""


def parse_gcs_uri(uri: str) -> tuple[str, str]:
    """Parse GCS URI into bucket and path.

    Args:
        uri: GCS URI in format gs://bucket/path

    Returns:
        Tuple of (bucket, path)

    Raises:
        ValueError: If URI is not a valid GCS URI

    Examples:
        >>> parse_gcs_uri("gs://my-bucket/path/to/file.txt")
        ('my-bucket', 'path/to/file.txt')
    """
    if not uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI: {uri}")

    parts = uri[5:].split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid GCS URI format: {uri}")

    return parts[0], parts[1]
