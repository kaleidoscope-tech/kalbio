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
    filtered = client.programs.get_programs_by_ids(['prog1_uuid', 'prog2_uuid'])
    ```
"""

from kalbio._base import _BaseService
from kalbio._cache import cached
from kalbio._kaleidoscope_model import _KaleidoscopeBaseModel
from kalbio.client import _require_response_body
from typing import List, Optional



class Program(_KaleidoscopeBaseModel):
    """Represents a program in the Kaleidoscope system.

    A Program is a base model that contains identifying information about
    a program, including its title and ID.

    Attributes:
        title (str): The title/name of the program.
    """

    title: Optional[str] = None

    def __str__(self):
        return f"{self.title}"


class ProgramsService(_BaseService):
    """Service class for managing and retrieving programs (experiments) from Kaleidoscope.

    This service provides methods to interact with the programs API endpoint,
    allowing users to fetch all available programs or filter programs by their IDs.

    Example:
        ```python
        # get all programs in the workspace
        programs = client.programs.get_programs()

        # get several programs by their ids
        filtered = client.programs.get_programs_by_ids(['prog1_uuid', 'prog2_uuid'])
        ```
    """

    @cached
    def get_programs(self) -> List[Program]:
        """Retrieve all programs available in the workspace.

        This method caches its values.

        Returns:
            List[Program]: A list of Program objects in the workspace.

        Raises:
            KalbioAPIError: If the API request fails.
            KalbioResponseError: If the endpoint returns no usable body.
        """
        resp = _require_response_body(
            "GET", "/programs", self._client._get("/programs")
        )
        return Program._list_from_api(resp, self._client)

    def get_programs_by_ids(self, ids: List[str]) -> List[Program]:
        """Retrieve a list of Program objects whose IDs match the provided list.

        Args:
            ids (List[str]): A list of program IDs to filter by.

        Returns:
            List[Program]: A list of Program instances with IDs found in ids.
        """
        programs = self.get_programs()
        return [program for program in programs if program.id in ids]

    def create_program(self, title: str) -> Program:
        """Create a new program in the workspace.

        Args:
            title (str): The title of the program to create.

        Returns:
            Program: The created Program object.

        Raises:
            KalbioAPIError: If the API request fails (e.g. validation error).
        """
        resp = _require_response_body(
            "POST", "/programs", self._client._post("/programs", {"title": title})
        )
        self.get_programs.cache_clear()
        return Program._from_api(resp, self._client)

    def update_program(self, program_id: str, title: str) -> Program:
        """Update an existing program.

        Args:
            program_id (str): The UUID of the program to update.
            title (str): The new title for the program.

        Returns:
            Program: The updated Program object.

        Raises:
            KalbioAPIError: If the API request fails (e.g. validation error).
        """
        url = f"/programs/{program_id}"
        resp = _require_response_body(
            "PUT", url, self._client._put(url, {"title": title})
        )
        self.get_programs.cache_clear()
        return Program._from_api(resp, self._client)
