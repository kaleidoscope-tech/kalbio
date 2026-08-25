"""Service class for handling file operations in Kaleidoscope.

This module provides methods for downloading files from the Kaleidoscope API.

Classes:
    FilesService: Service for downloading files by ID.

Example:
    ```python
    path = client.files.download_file(
        file_id="file-uuid",
        filename="original_filename.csv",
        destination="/tmp/downloads",
        activity_id="activity-uuid",
    )
    ```
"""

from pathlib import Path
from typing import Optional

from kalbio._base import _BaseService



class FilesService(_BaseService):
    """Service class for file operations.

    Provides methods to download files by ID from the Kaleidoscope API.
    """

    def download_file(
        self,
        file_id: str,
        filename: Optional[str] = None,
        destination: Optional[str | Path] = None,
        activity_id: Optional[str] = None,
    ) -> str | None:
        """Download a file by ID and save it to a local path.

        When ``activity_id`` is provided, the download is scoped to that
        activity using ``/activities/{activity_id}/file/{file_id}``.
        Otherwise falls back to ``/files/{file_id}``.

        Args:
            file_id (str): The ID of the file to download.
            filename (str, optional): Name to save the file as. Defaults to
                the file_id if not provided. Typically the ``file_name``
                from the webhook event payload.
            destination (str | Path, optional): Directory to save the file in.
                Defaults to the current working directory.
            activity_id (str, optional): The activity ID to scope the
                download to. When provided, uses the activity-scoped
                endpoint.

        Returns:
            (str | None): The path to the downloaded file on success,
            or None on failure.

        Example:
            ```python
            # Download scoped to an activity
            path = client.files.download_file(
                "file-uuid",
                filename="data.csv",
                activity_id="activity-uuid",
            )

            # Download by file ID only
            path = client.files.download_file(
                "file-uuid",
                filename="data.csv",
                destination="/tmp/downloads",
            )
            ```
        """
        # `filename` is typically server-supplied (a webhook payload), so reduce
        # it to a bare name: an absolute path or one containing ".." would
        # otherwise write outside `destination`.
        safe_name = Path(filename).name if filename else ""
        name = safe_name or file_id
        dest = Path(destination or ".")
        dest.mkdir(parents=True, exist_ok=True)
        download_path = str(dest / name)

        if activity_id:
            url = f"/activities/{activity_id}/file/{file_id}"
        else:
            url = f"/files/{file_id}"

        return self._client._get_file(url, download_path)
