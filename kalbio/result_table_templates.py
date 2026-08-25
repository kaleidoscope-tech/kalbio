"""Result table templates module for the Kaleidoscope API client.

Result table templates are reusable record-view configurations that can be
linked to one or more experiment types (operation definitions). When linked,
each experiment of that type gets a record view created from the template's
field/filter/sort configuration.

This module provides a dedicated `ResultTableTemplate` model so templates
remain conceptually separate from regular record views (which are scoped to
a specific operation or workspace context).

Classes:
    ResultTableTemplate: Data model for a result table template.
    ResultTableTemplatesService: Service for CRUD operations on templates,
        plus linking templates to experiment types.

Example:
    ```python
    # List all templates
    templates = client.result_table_templates.get_templates()

    # Create a template on an entity slice with two fields
    template = client.result_table_templates.create_template(
        view_name="Compound results",
        entity_slice_id="slice-uuid",
        data_field_ids=["field-uuid-1", "field-uuid-2"],
        template_name="Standard compound results",
    )

    # Link the template to an experiment type
    view = client.result_table_templates.link_to_operation_definition(
        template.id,
        operation_definition_id="definition-uuid",
    )
    ```
"""

from kalbio._base import _BaseService
from kalbio._cache import cached
from typing import Any, List, Optional

from kalbio.client import _require_response_body
from kalbio.record_views import (
    RecordView,
    RecordViewColorFilter,
    RecordViewFilter,
    RecordViewSort,
)


class ResultTableTemplate(RecordView):
    """A reusable record-view configuration that can be linked to experiment types.

    Same data shape as `RecordView` (templates ARE record views server-side,
    distinguished by `is_template=True`), exposed as its own type for
    clarity at call sites. Templates are not bound to a specific operation
    or read-only context — they're blueprints that experiment types
    instantiate when linked.

    Inherits all of `RecordView`'s fields, including `template_name` and
    `is_template` (always True for instances of this class).
    """

    is_template: bool = True

    def __str__(self):
        return self.template_name or self.view_name or self.id


class ResultTableTemplatesService(_BaseService):
    """Service for managing result table templates.

    Provides CRUD methods for templates and helpers for linking templates
    to experiment types (operation definitions).
    """

    #########################
    #    Public Methods     #
    #########################

    @cached
    def get_templates(self) -> List[ResultTableTemplate]:
        """Retrieve all result table templates in the workspace.

        This method caches its results.

        Returns:
            A list of ResultTableTemplate objects.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        resp = _require_response_body(
            "GET",
            "/record_view_templates",
            self._client._get("/record_view_templates"),
        )
        return [self._create_template(data) for data in resp]

    def get_template_by_id(self, template_id: str) -> Optional[ResultTableTemplate]:
        """Retrieve a single template by ID.

        Args:
            template_id: UUID of the template to fetch.

        Returns:
            The ResultTableTemplate if found, otherwise None.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        resp = self._client._get(f"/record_view_templates/{template_id}")
        if resp is None:
            return None
        return self._create_template(resp)

    def create_template(
        self,
        *,
        view_name: str,
        entity_slice_id: str,
        template_name: Optional[str] = None,
        program_ids: Optional[List[str]] = None,
        view_field_ids: Optional[List[str]] = None,
        data_field_ids: Optional[List[str]] = None,
        lookup_field_ids: Optional[List[str]] = None,
        plot_field_ids: Optional[List[str]] = None,
        filters: Optional[List[RecordViewFilter]] = None,
        sorts: Optional[List[RecordViewSort]] = None,
        color_filters: Optional[List[RecordViewColorFilter]] = None,
        record_set_ids_filter: Optional[List[str]] = None,
        sort_order: Optional[str] = None,
        sort_descending: Optional[bool] = None,
        view_mode: Optional[str] = None,
        group_by_mode: Optional[str] = None,
        group_by_field_id: Optional[str] = None,
    ) -> ResultTableTemplate:
        """Create a new result table template from scratch.

        For each optional argument, pass `None` (default) to omit it from the
        request — the server applies its own defaults (typically empty lists).

        Args:
            view_name: Display name for the view this template produces.
            entity_slice_id: UUID of the entity slice the template targets.
            template_name: Optional human-readable template label.
            program_ids: Programs to associate with the template.
            view_field_ids: Existing view-field UUIDs to copy into the template.
            data_field_ids: Data field UUIDs to add as view fields.
            lookup_field_ids: Lookup field UUIDs to add as view fields.
            plot_field_ids: Plot field UUIDs to add as view fields.
            filters: View filters (each entry follows the server filter shape).
            sorts: View sorts.
            color_filters: Color-filter configurations.
            record_set_ids_filter: Record set UUIDs to restrict the view to.
            sort_order: `'alphabetical'`, `'created_date'`, or `'manual'`.
            sort_descending: Sort direction.
            view_mode: Display mode (e.g. `'table'`).
            group_by_mode: Grouping mode.
            group_by_field_id: Group-by field UUID.

        Returns:
            The newly created ResultTableTemplate.

        Raises:
            KalbioAPIError: If the API request fails.

        Example:
            ```python
            template = client.result_table_templates.create_template(
                view_name="Compound results",
                entity_slice_id="slice-uuid",
                data_field_ids=["field-uuid-1", "field-uuid-2"],
                template_name="Standard compound results",
            )
            ```
        """
        payload: dict = {
            "view_name": view_name,
            "entity_slice_id": entity_slice_id,
        }
        _set_if_not_none(payload, "template_name", template_name)
        _set_if_not_none(payload, "program_ids", program_ids)
        _set_if_not_none(payload, "view_field_ids", view_field_ids)
        _set_if_not_none(payload, "data_field_ids", data_field_ids)
        _set_if_not_none(payload, "lookup_field_ids", lookup_field_ids)
        _set_if_not_none(payload, "plot_field_ids", plot_field_ids)
        _set_if_not_none(payload, "filters", filters)
        _set_if_not_none(payload, "sorts", sorts)
        _set_if_not_none(payload, "color_filters", color_filters)
        _set_if_not_none(payload, "record_set_ids_filter", record_set_ids_filter)
        _set_if_not_none(payload, "sort_order", sort_order)
        _set_if_not_none(payload, "sort_descending", sort_descending)
        _set_if_not_none(payload, "view_mode", view_mode)
        _set_if_not_none(payload, "group_by_mode", group_by_mode)
        _set_if_not_none(payload, "group_by_field_id", group_by_field_id)

        resp = _require_response_body(
            "POST",
            "/record_view_templates",
            self._client._post("/record_view_templates", payload),
        )
        self.get_templates.cache_clear()
        return self._create_template(resp)

    def save_view_as_template(
        self,
        *,
        source_view_id: str,
        view_name: str,
        template_name: Optional[str] = None,
    ) -> ResultTableTemplate:
        """Save an existing record view as a template.

        Args:
            source_view_id: UUID of the record view to copy.
            view_name: Display name for the new template's view.
            template_name: Optional human-readable template label.

        Returns:
            The newly created ResultTableTemplate.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload: dict = {
            "source_view_id": source_view_id,
            "view_name": view_name,
        }
        _set_if_not_none(payload, "template_name", template_name)

        resp = _require_response_body(
            "POST",
            "/record_view_templates",
            self._client._post("/record_view_templates", payload),
        )
        self.get_templates.cache_clear()
        return self._create_template(resp)

    def update_template(
        self,
        template_id: str,
        *,
        view_name: Optional[str] = None,
        template_name: Optional[str] = None,
        program_ids: Optional[List[str]] = None,
        save_view_field_ids: Optional[List[str]] = None,
        remove_view_field_ids: Optional[List[str]] = None,
        reorder_view_field_ids: Optional[List[str]] = None,
        filters: Optional[List[RecordViewFilter]] = None,
        sorts: Optional[List[RecordViewSort]] = None,
        color_filters: Optional[List[RecordViewColorFilter]] = None,
        record_set_ids_filter: Optional[List[str]] = None,
        is_archived: Optional[bool] = None,
        sort_order: Optional[str] = None,
        sort_descending: Optional[bool] = None,
        view_mode: Optional[str] = None,
        group_by_mode: Optional[str] = None,
        group_by_field_id: Optional[str] = None,
    ) -> ResultTableTemplate:
        """Update an existing template.

        Only arguments with a non-None value are sent to the server —
        omitted fields (or fields passed as None) are left unchanged.
        There's no way to explicitly clear a nullable field through this
        method; use `client._put` directly if you need to send `null`.

        Args:
            template_id: UUID of the template to update.
            view_name: New display name.
            template_name: New template label.
            program_ids: Replace the associated programs.
            save_view_field_ids: View-field UUIDs to add/save.
            remove_view_field_ids: View-field UUIDs to remove.
            reorder_view_field_ids: New order of view-field UUIDs.
            filters, sorts, color_filters: Replace these configurations
                wholesale with the provided list.
            record_set_ids_filter: Replace record set filter.
            is_archived: Set archived state.
            sort_order, sort_descending, view_mode: View-level config.
            group_by_mode, group_by_field_id: Grouping config.

        Returns:
            The updated ResultTableTemplate.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload: dict = {}
        _set_if_not_none(payload, "view_name", view_name)
        _set_if_not_none(payload, "template_name", template_name)
        _set_if_not_none(payload, "program_ids", program_ids)
        _set_if_not_none(payload, "save_view_field_ids", save_view_field_ids)
        _set_if_not_none(payload, "remove_view_field_ids", remove_view_field_ids)
        _set_if_not_none(payload, "reorder_view_field_ids", reorder_view_field_ids)
        _set_if_not_none(payload, "filters", filters)
        _set_if_not_none(payload, "sorts", sorts)
        _set_if_not_none(payload, "color_filters", color_filters)
        _set_if_not_none(payload, "record_set_ids_filter", record_set_ids_filter)
        _set_if_not_none(payload, "is_archived", is_archived)
        _set_if_not_none(payload, "sort_order", sort_order)
        _set_if_not_none(payload, "sort_descending", sort_descending)
        _set_if_not_none(payload, "view_mode", view_mode)
        _set_if_not_none(payload, "group_by_mode", group_by_mode)
        _set_if_not_none(payload, "group_by_field_id", group_by_field_id)

        url = f"/record_view_templates/{template_id}"
        resp = _require_response_body("PUT", url, self._client._put(url, payload))
        self.get_templates.cache_clear()
        return self._create_template(resp)

    def delete_template(self, template_id: str) -> None:
        """Soft-delete a template.

        Any experiment types linked to the template will have their template
        pointers cleared.

        Args:
            template_id: UUID of the template to delete.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        self._client._delete(f"/record_view_templates/{template_id}")
        self.get_templates.cache_clear()
        # Deleting clears linked experiment types' template pointers and their
        # instantiated views, so the cached record-view list is now stale.
        self._client.record_views._clear_record_view_caches()

    def duplicate_template(self, template_id: str) -> ResultTableTemplate:
        """Create a copy of an existing template.

        Args:
            template_id: UUID of the template to duplicate.

        Returns:
            The newly created ResultTableTemplate copy.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        url = f"/record_view_templates/{template_id}/duplicate"
        resp = _require_response_body("POST", url, self._client._post(url, {}))
        self.get_templates.cache_clear()
        return self._create_template(resp)

    def promote_view_to_template(
        self,
        *,
        source_view_id: str,
        operation_definition_id: str,
        view_name: str,
        position_index: Optional[int] = None,
    ) -> ResultTableTemplate:
        """Promote an existing record view to a template, linked to the same definition.

        Atomically saves the view as a template, links the template to the
        operation definition at the same position the original view occupied,
        and removes the original view.

        Args:
            source_view_id: UUID of the record view to promote.
            operation_definition_id: UUID of the operation definition the
                view currently belongs to.
            view_name: Display name for the resulting template's view.
            position_index: Optional layout position for the new linked view.

        Returns:
            The newly created ResultTableTemplate.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload: dict = {
            "source_view_id": source_view_id,
            "operation_definition_id": operation_definition_id,
            "view_name": view_name,
        }
        _set_if_not_none(payload, "position_index", position_index)

        resp = _require_response_body(
            "POST",
            "/record_view_templates/promote",
            self._client._post("/record_view_templates/promote", payload),
        )
        self.get_templates.cache_clear()
        # Promotion removes the source record view, so the record-view list cache
        # would otherwise still return the deleted view.
        self._client.record_views._clear_record_view_caches()
        return self._create_template(resp)

    def link_to_operation_definition(
        self,
        template_view_id: str,
        *,
        operation_definition_id: str,
        position_index: Optional[int] = None,
    ) -> ResultTableTemplate:
        """Link a template to an experiment type (operation definition).

        Adds the definition's id to the template's `operation_definition_ids`
        so the template appears in that experiment type's content layout.

        Args:
            template_view_id: UUID of the template to link.
            operation_definition_id: UUID of the operation definition.
            position_index: Optional layout position.

        Returns:
            The updated template (now linked to the operation definition).

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload: dict = {
            "template_view_id": template_view_id,
            "operation_definition_id": operation_definition_id,
        }
        _set_if_not_none(payload, "position_index", position_index)

        self._client._post("/record_view_templates/link", payload)
        self.get_templates.cache_clear()
        # Linking instantiates a per-experiment record view from the template,
        # so the cached record-view list no longer reflects the server.
        self._client.record_views._clear_record_view_caches()
        # The server's /link response returns the template's pre-link state,
        # so refetch to return data with the new operation_definition_id.
        url = f"/record_view_templates/{template_view_id}"
        fresh = _require_response_body("GET", url, self._client._get(url))
        return self._create_template(fresh)

    def unlink_from_operation_definition(
        self,
        template_id: str,
        *,
        operation_definition_id: str,
        content_layout_id: str,
    ) -> None:
        """Remove a single template link from an experiment type.

        Args:
            template_id: UUID of the template that's linked.
            operation_definition_id: UUID of the operation definition.
            content_layout_id: UUID of the content layout item to remove.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload = {
            "operation_definition_id": operation_definition_id,
            "content_layout_id": content_layout_id,
        }
        self._client._post(
            f"/record_view_templates/{template_id}/unlink", payload
        )
        self.get_templates.cache_clear()
        # Unlinking removes the template's instantiated per-experiment view.
        self._client.record_views._clear_record_view_caches()

    def bulk_link_to_operation_definitions(
        self,
        template_view_id: str,
        *,
        operation_definition_ids: List[str],
    ) -> None:
        """Link a template to multiple experiment types at once.

        The template is appended to the bottom of each definition's content
        layout.

        Args:
            template_view_id: UUID of the template.
            operation_definition_ids: UUIDs of operation definitions to link to.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload = {
            "template_view_id": template_view_id,
            "operation_definition_ids": operation_definition_ids,
        }
        self._client._post("/record_view_templates/bulk/link", payload)
        self.get_templates.cache_clear()
        # Each link instantiates a per-experiment record view from the template.
        self._client.record_views._clear_record_view_caches()

    def bulk_unlink_from_operation_definitions(
        self,
        template_view_id: str,
        *,
        operation_definition_ids: List[str],
    ) -> None:
        """Remove all instances of a template from multiple experiment types.

        Clears any registration configurations referencing the template on
        those definitions.

        Args:
            template_view_id: UUID of the template.
            operation_definition_ids: UUIDs of operation definitions to
                unlink from.

        Raises:
            KalbioAPIError: If the API request fails.
        """
        payload = {
            "template_view_id": template_view_id,
            "operation_definition_ids": operation_definition_ids,
        }
        self._client._post("/record_view_templates/bulk/unlink", payload)
        self.get_templates.cache_clear()
        # Unlinking removes the template's instantiated per-experiment views.
        self._client.record_views._clear_record_view_caches()

    #########################
    #    Private Methods    #
    #########################

    def _create_template(self, data: dict) -> ResultTableTemplate:
        """Validate raw template data and attach the client to the model."""
        template = ResultTableTemplate.model_validate(data)
        template._set_client(self._client)
        return template


def _set_if_not_none(payload: dict, key: str, value: Any) -> None:
    """Add `key: value` to `payload` only if value is not None."""
    if value is not None:
        payload[key] = value
