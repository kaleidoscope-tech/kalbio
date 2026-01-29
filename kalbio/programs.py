"""Programs module for interacting with Kaleidoscope programs.

The service allows users to retrieve all available programs in a workspace
and filter programs by specific IDs.

Classes:
    Program: Data model for a Kaleidoscope program.
    ProgramsService: Service for managing program retrieval operations.

Example:
    ```python
    # get all programs in the workspace
    programs = client.programs.get_programs()

    # get several programs by their ids
    filtered = client.programs.get_program_by_ids(['prog1_uuid', 'prog2_uuid'])
    ```
"""

import logging
from functools import lru_cache
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import KaleidoscopeClient
from pydantic import TypeAdapter
from typing import List

_logger = logging.getLogger(__name__)


class Program(_KaleidoscopeBaseModel):
    """Represents a program in the Kaleidoscope system.

    A Program is a base model that contains identifying information about
    a program, including its title and ID.

    Attributes:
        title (str): The title/name of the program.
    """

    title: str

    def __str__(self):
        return f"{self.title}"


class ProgramsService:
    """Service class for managing and retrieving programs (experiments) from Kaleidoscope.

    This service provides methods to interact with the programs API endpoint,
    allowing users to fetch all available programs or filter programs by their IDs.

    Example:
        ```python
        # get all programs in the workspace
        programs = client.programs.get_programs()

        # get several programs by their ids
        filtered = client.programs.get_program_by_ids(['prog1_uuid', 'prog2_uuid'])
        ```
    """

    def __init__(self, client: KaleidoscopeClient):
        self._client = client

    @lru_cache
    def get_programs(self) -> List[Program]:
        """Retrieve all programs available in the workspace.

        This method caches its values.

        Returns:
            List[Program]: A list of Program objects in the workspace.

        Note:
            If an exception occurs during the API request, it logs the error,
            clears the cache, and returns an empty list.
        """
        try:
            resp = self._client._get("/programs")
            return TypeAdapter(List[Program]).validate_python(resp)
        except Exception as e:
            _logger.error(f"Error fetching programs: {e}")
            self.get_programs.cache_clear()
            return []

    def get_programs_by_ids(self, ids: List[str]) -> List[Program]:
        """Retrieve a list of Program objects whose IDs match the provided list.

        Args:
            ids (List[str]): A list of program IDs to filter by.

        Returns:
            List[Program]: A list of Program instances with IDs found in ids.
        """
        programs = self.get_programs()
        return [program for program in programs if program.id in ids]
