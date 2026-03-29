"""Messaging adapter with Protocol interface and Pub/Sub implementation.

Handles publishing messages between pipeline functions via Pub/Sub topics.
"""

import json
from typing import Any, Protocol


class MessagingAdapter(Protocol):
    """Protocol for messaging operations."""

    def publish(self, topic: str, message: dict[str, Any], attributes: dict[str, str] | None = None) -> str:
        """Publish message to topic.

        Args:
            topic: Topic name (without projects/.../topics/ prefix)
            message: Message payload as dict (will be JSON serialized)
            attributes: Optional message attributes

        Returns:
            Message ID
        """
        ...


class PubSubAdapter:
    """Google Cloud Pub/Sub implementation."""

    def __init__(self, project_id: str | None = None):
        """Initialize Pub/Sub publisher.

        Args:
            project_id: GCP project ID (uses ADC default if None)
        """
        from google.cloud import pubsub_v1

        self._publisher = pubsub_v1.PublisherClient()
        self._project_id = project_id or self._get_default_project()

    def _get_default_project(self) -> str:
        """Get default project from environment or metadata."""
        import os

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project:
            return project

        project = os.environ.get("GCLOUD_PROJECT")
        if project:
            return project

        try:
            import google.auth

            _, project = google.auth.default()
            return project or "unknown-project"
        except Exception:
            return "unknown-project"

    def publish(
        self, topic: str, message: dict[str, Any], attributes: dict[str, str] | None = None
    ) -> str:
        """Publish message to Pub/Sub topic.

        Args:
            topic: Topic name (e.g., "invoice-converted")
            message: Message payload as dict
            attributes: Optional message attributes

        Returns:
            Message ID
        """
        topic_path = self._publisher.topic_path(self._project_id, topic)

        data = json.dumps(message, default=str).encode("utf-8")

        if attributes:
            future = self._publisher.publish(topic_path, data, **attributes)
        else:
            future = self._publisher.publish(topic_path, data)

        return future.result()
