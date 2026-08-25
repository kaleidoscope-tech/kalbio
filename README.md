# Kalbio

<!-- **Source Code**: [https://github.com/kaleidoscope-tech/kalbio](https://github.com/kaleidoscope-tech/kalbio)

--- -->

Kalbio is a Python Client library for building applications with the Kaleidoscope platform.

## Key features

- **Type-safe API Client**: Built with Pydantic models for full type safety and IDE autocomplete support
- **Intuitive Resource Management**: Clean, object-oriented interface for programs, activities, records, and more
- **Advanced Search & Filtering**: Powerful query capabilities with type-safe filter operators
- **File Upload Support**: Direct file upload to record fields with support for multiple file types
- **Bulk Operations**: Import and export capabilities for efficient data management

## Requirements

- [Python](https://docs.python.org/3/) 3.10+
- [Pydantic](https://docs.pydantic.dev/) 2.9.2+
- [Requests](https://requests.readthedocs.io/) 2.32.3+

<!--
TODO

## Installation

Clone the repository and install the client in editable mode:

```bash
git clone https://github.com/kaleidoscope-tech/kalbio.git
cd kalbio
pip install -e .
```
-->

## Authentication

Set your API credentials as environment variables before running examples:

```bash
export KALEIDOSCOPE_API_CLIENT_ID="your_client_id"
export KALEIDOSCOPE_API_CLIENT_SECRET="your_client_secret"
```

## Example

### Create it

Create a file `main.py` with:

```python
from kalbio.client import KaleidoscopeClient
from kalbio.activities import ActivityStatusEnum

# Initialize the client using environment variables
client = KaleidoscopeClient()

# # Or with explicit arguements
# client = KaleidoscopeClient(
#     client_id="your_api_client_id",
#     client_secret="your_api_client_secret"
# )

# Work with activities
activities = client.activities.get_activities()
for activity in activities:
    print(f"Activity: {activity.title} - Status: {activity.status.value}")
```

### Run it

Run the program with:

```bash
python main.py
```

Output:

```text
Activity: Experiment 1 - Status: to do
Activity: Task 1 - Status: to do
Activity: Drug Tests - Status: in progress
```

### Check it

You now have a fully functional Kaleidoscope API client.

## Features

### Intuitive API Design

Work with resources naturally:

```python
# Records
record = client.records.get_record_by_id("record-uuid")

if record:
    record.add_value(
        field_id="field-uuid",
        content="Experiment result",
        activity_id="activity-uuid"
    )

# Entity Types
entity_types = client.entity_types.get_types()
compound_type = client.entity_types.get_type_by_name("Compound")
```

### File Upload Support

Upload files directly to records:

```python
# Upload a file to a record field
with open("experiment_data.csv", "rb") as file:
    record.update_field_file(
        field_id="data-field-id",
        file_name="experiment_data.csv",
        file_data=file,
        file_type="text/csv",
        activity_id="activity-uuid"
    )
```

### Resource Management

Kalbio provides services for the following Kaleidoscope resources:

- **Programs**: Organize your work
- **Activities**: Tasks, experiments, projects, etc.
- **Records**: Structured entity records
- **Entity Types**: Define your data schemas
- **Entity Fields**: Manage field definitions
- **Labels**: Tag and categorize
- **Imports/Exports**: Bulk data operations
- **Workspace**: User and group management

## Interactive Documentation

### Available Services

Once you have a client instance, you have access to:

| Service                | Description                                 |
| ---------------------- | ------------------------------------------- |
| `client.programs`      | Program management                          |
| `client.activities`    | Activities (tasks, experiments, projects)   |
| `client.records`       | Entity record CRUD operations               |
| `client.entity_types`  | Entity type definitions                     |
| `client.entity_fields` | Field definitions (key fields, data fields) |
| `client.labels`        | Label management                            |
| `client.imports`       | Import operations and templates             |
| `client.exports`       | Export operations                           |
| `client.workspace`     | Workspace, users, and groups                |

### Activity Management

```python
# Create an activity
new_activity = client.activities.create_activity(
    title="Synthesis Experiment",
    activity_type="experiment",
    program_ids=["program-uuid"],
    assigned_user_ids=["user-uuid"]
)

if new_activity:
    # Update activity status
    new_activity.update(status=ActivityStatusEnum.IN_PROGRESS)

    # Add records to activity
    new_activity.add_records(["record-uuid-1", "record-uuid-2"])

    # Get activity data
    record_data = new_activity.get_record_data()
```

### Record Operations

```python
# Get record by ID
record = client.records.get_record_by_id("record-uuid")

if record:
    # Add a value
    record.add_value(
        field_id="field-uuid",
        content="High purity sample",
        activity_id="activity-uuid"
    )

    # Get field value
    value = record.get_value_content(field_id="field-uuid")

    # Get values for specific activity
    activity_values = record.get_activity_data(activity_id="activity-uuid")
```

## Full Example

Here's a complete workflow example:

```python
# Initialize client
client = KaleidoscopeClient(
    KALEIDOSCOPE_API_CLIENT_ID,
    KALEIDOSCOPE_API_CLIENT_SECRET,
    "https://api.kaleidoscope.bio",
)

# 1. Get or create a program
programs = client.programs.get_programs()
program = programs[0] if programs else None

if program:
    print(f"Working with program: {program.title}")

    # 2. Get entity types
    entity_types = client.entity_types.get_types()
    compound_type = next(
        (et for et in entity_types if et.slice_name == "Compound"),
        None
    )

    if compound_type:
        # 3. Search for records
        record_ids = client.records.search_records(
            entity_slice_id=compound_type.id,
            limit=10
        )

        print(f"Found {len(record_ids)} compound records")

        # 4. Get detailed record information
        if record_ids:
            record = client.records.get_record_by_id(record_ids[0])
            assert record
            print(f"Record: {record.record_identifier}")

            # 5. Create an activity
            activity = client.activities.create_activity(
                title="Quality Check",
                activity_type="task",
                program_ids=[program.id]
            )
            assert activity

            # 6. Add data to record
            record.add_value(
                field_id="notes-field-id",
                content="Quality check completed successfully",
                activity_id=activity.id
            )

            # 7. Update activity status
            activity.update(task_status=ActivityStatusEnum.COMPLETE)

            print("Workflow completed successfully!")
```

## Support

For support, email [support@kaleidoscope.bio](mailto:support@kaleidoscope.bio).
