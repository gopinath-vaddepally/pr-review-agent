# Data Models

This directory contains all Pydantic data models for the Azure DevOps PR Review Agent system.

## Model Organization

Models are organized by domain:

### Repository Models (`repository.py`)
- **Repository**: Complete repository configuration with metadata
- **RepositoryCreate**: Request model for adding new repositories

### PR Event Models (`pr_event.py`)
- **PREvent**: Webhook event data from Azure DevOps
- **PRMetadata**: Enriched PR metadata for agent processing

### File Change Models (`file_change.py`)
- **ChangeType**: Enum for file change types (add, edit, delete)
- **LineChange**: Individual line-level change
- **FileChange**: Complete file change with line-level details

### AST Models (`ast_node.py`)
- **ASTNode**: Abstract Syntax Tree node representation (recursive)

### Comment Models (`comment.py`)
- **CommentSeverity**: Enum for severity levels (info, warning, error)
- **CommentCategory**: Enum for comment categories (code_smell, bug, security, best_practice, architecture)
- **LineComment**: Line-level code review comment
- **SummaryComment**: High-level architectural summary

### Agent Models (`agent.py`)
- **AgentStatus**: Enum for agent execution status (running, completed, failed, timeout)
- **AgentState**: Complete agent state for persistence
- **AgentInfo**: Agent information for monitoring

### Analysis Models (`analysis.py`)
- **SOLIDViolation**: SOLID principle violation
- **DesignPattern**: Identified design pattern
- **ArchitecturalIssue**: Architectural issue (layering, dependencies)

### Error Models (`error.py`)
- **ErrorRecord**: Error tracking with context

### API Response Models (`api_response.py`)
- **WebhookResponse**: Webhook handler response
- **PublishResult**: Comment publishing result
- **ValidationResult**: Validation operation result

## Usage

Import models from the package:

```python
from app.models import (
    Repository,
    PREvent,
    FileChange,
    LineComment,
    AgentState,
)
```

## Validation

All models use Pydantic for automatic validation:

```python
from app.models import Repository
from datetime import datetime

# Valid model
repo = Repository(
    id="123",
    organization="myorg",
    project="myproject",
    repository_name="myrepo",
    repository_url="https://dev.azure.com/myorg/myproject/_git/myrepo",
    created_at=datetime.now(),
    updated_at=datetime.now()
)

# Invalid model raises ValidationError
try:
    repo = Repository(
        id="123",
        organization="myorg",
        # Missing required fields
    )
except ValidationError as e:
    print(e)
```

## Type Safety

All models provide full type hints for IDE support:

```python
from app.models import LineComment, CommentSeverity, CommentCategory

comment = LineComment(
    file_path="src/main.py",
    line_number=42,
    severity=CommentSeverity.WARNING,  # Type-safe enum
    category=CommentCategory.CODE_SMELL,  # Type-safe enum
    message="Consider refactoring this method",
    suggestion="Extract this logic into a separate function"
)
```

## Serialization

All models support JSON serialization:

```python
from app.models import PREvent
from datetime import datetime

event = PREvent(
    event_type="git.pullrequest.created",
    pr_id="123",
    repository_id="repo-456",
    source_branch="feature/new-feature",
    target_branch="main",
    author="user@example.com",
    title="Add new feature",
    timestamp=datetime.now()
)

# Serialize to JSON
json_data = event.model_dump_json()

# Deserialize from JSON
event_copy = PREvent.model_validate_json(json_data)
```

## Requirements Mapping

These models satisfy the following requirements:

- **1.5**: Repository URL validation (Repository, RepositoryCreate)
- **2.2**: PR metadata structure (PREvent, PRMetadata)
- **4.1**: File change tracking (FileChange, LineChange, ChangeType)
- **5.6**: Comment structure (LineComment, SummaryComment)
- **6.6**: Architectural analysis results (SOLIDViolation, DesignPattern, ArchitecturalIssue)

## Testing

Models can be tested using property-based testing:

```python
from hypothesis import given
from hypothesis.strategies import text, integers
from app.models import LineComment, CommentSeverity, CommentCategory

@given(
    file_path=text(min_size=1),
    line_number=integers(min_value=1),
    message=text(min_size=1)
)
def test_line_comment_creation(file_path, line_number, message):
    comment = LineComment(
        file_path=file_path,
        line_number=line_number,
        severity=CommentSeverity.INFO,
        category=CommentCategory.BEST_PRACTICE,
        message=message
    )
    assert comment.file_path == file_path
    assert comment.line_number == line_number
    assert comment.message == message
```
