# Design Document: Azure DevOps PR Review Agent

## Overview

The Azure DevOps PR Review Agent is an autonomous code review system that provides real-time, AI-powered analysis of pull requests in Azure DevOps repositories. The system combines line-level code quality analysis with holistic architectural evaluation to deliver comprehensive feedback directly within the Azure DevOps interface.

### System Goals

1. **Automated Code Review**: Provide immediate, consistent code review feedback without human intervention
2. **Multi-Level Analysis**: Combine granular line-level analysis with high-level architectural evaluation
3. **Real-Time Response**: Detect and analyze pull requests within seconds of creation
4. **Scalable Architecture**: Support concurrent analysis of multiple pull requests across multiple repositories
5. **Resilient Operation**: Handle failures gracefully and maintain system availability

### Key Design Principles

- **Event-Driven Architecture**: Webhook-based PR detection eliminates polling overhead
- **Agent Isolation**: Each PR gets a dedicated LangGraph agent instance for independent execution
- **State Persistence**: Redis-backed state management enables agent resumability and crash recovery
- **Async-First**: FastAPI and async patterns throughout for high-throughput I/O operations
- **Separation of Concerns**: Clear boundaries between webhook handling, agent orchestration, code analysis, and comment publishing

## Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Azure DevOps"
        ADO[Azure DevOps<br/>Service Hooks]
        ADOPR[Pull Request API]
    end
    
    subgraph "PR Review Agent System"
        subgraph "API Layer"
            WH[Webhook Handler<br/>FastAPI]
            API[REST API<br/>FastAPI]
        end
        
        subgraph "Orchestration Layer"
            PM[PR Monitor]
            AO[Agent Orchestrator]
        end
        
        subgraph "Agent Layer"
            RA1[Review Agent 1<br/>LangGraph]
            RA2[Review Agent 2<br/>LangGraph]
            RAN[Review Agent N<br/>LangGraph]
        end
        
        subgraph "Analysis Layer"
            CA[Code Analyzer<br/>tree-sitter + LLM]
            AA[Architecture Analyzer<br/>LLM]
        end
        
        subgraph "Integration Layer"
            CP[Comment Publisher<br/>Azure DevOps SDK]
            CR[Code Retriever<br/>Azure DevOps SDK]
        end
        
        subgraph "Data Layer"
            MY[(MySQL<br/>Repository Config)]
            RD[(Redis<br/>Agent State + Queue)]
        end
    end
    
    subgraph "Frontend"
        UI[Angular Admin UI]
    end
    
    ADO -->|PR Event Webhook| WH
    WH --> PM
    PM --> MY
    PM --> RD
    PM --> AO
    AO --> RA1
    AO --> RA2
    AO --> RAN
    RA1 --> CR
    RA1 --> CA
    RA1 --> AA
    RA1 --> CP
    CR --> ADOPR
    CP --> ADOPR
    UI --> API
    API --> MY
    
    style RA1 fill:#e1f5ff
    style RA2 fill:#e1f5ff
    style RAN fill:#e1f5ff
```

### Component Architecture

The system follows a layered architecture with clear separation of concerns:

1. **API Layer**: FastAPI-based HTTP endpoints for webhooks and admin operations
2. **Orchestration Layer**: Manages PR detection, agent lifecycle, and job distribution
3. **Agent Layer**: LangGraph-based autonomous agents that execute review workflows
4. **Analysis Layer**: Code and architecture analysis using AST parsing and LLM inference
5. **Integration Layer**: Azure DevOps API interactions for data retrieval and comment publishing
6. **Data Layer**: MySQL for configuration persistence, Redis for state and queuing

### Technology Stack Rationale

**FastAPI**: Chosen for async performance, automatic OpenAPI documentation, and Python ecosystem integration. Provides comparable performance to Spring Boot for I/O-bound workloads while enabling seamless integration with AI/LLM libraries.

**LangGraph**: Provides state graph orchestration for complex agent workflows with built-in state persistence, error recovery, and conditional branching. Superior to custom orchestration for multi-step AI agent workflows.

**Azure DevOps Python SDK**: Official SDK ensures API compatibility and reduces integration complexity compared to raw REST API calls.

**MySQL**: Widely adopted relational database with excellent performance for read-heavy workloads such as repository configuration queries. Provides strong ACID compliance for configuration persistence and is well-supported in enterprise environments. The mature Python ecosystem includes mysql-connector-python and aiomysql for async support, making it compatible with the organization's existing database infrastructure.

**Redis**: In-memory data store provides low-latency state management and job queuing. Supports agent state persistence for crash recovery and resumability.

**tree-sitter**: Language-agnostic AST parser with incremental parsing capabilities. Provides structured code representation for LLM analysis without language-specific parser dependencies.

**OpenAI/Azure OpenAI**: State-of-the-art LLM capabilities for code understanding, issue detection, and natural language generation of review comments.

## Components and Interfaces

### 1. Webhook Handler (FastAPI)

**Responsibility**: Receive and validate Azure DevOps Service Hook webhook events.

**Interface**:
```python
@app.post("/webhooks/azure-devops/pr")
async def handle_pr_webhook(
    event: AzureDevOpsPREvent,
    background_tasks: BackgroundTasks
) -> WebhookResponse:
    """
    Receives PR event webhooks from Azure DevOps Service Hooks.
    Validates event signature and enqueues for processing.
    """
    pass
```

**Dependencies**:
- PR Monitor (for event processing)
- Redis (for job queue)

**Key Behaviors**:
- Validates webhook signature for security
- Parses PR event payload
- Returns 200 OK immediately (async processing)
- Enqueues event to Redis job queue

### 2. PR Monitor

**Responsibility**: Process PR events, manage repository configuration, and orchestrate agent lifecycle.

**Interface**:
```python
class PRMonitor:
    async def process_pr_event(self, event: PREvent) -> None:
        """Process incoming PR event and spawn review agent if needed."""
        pass
    
    async def register_service_hook(self, repo_id: str) -> ServiceHook:
        """Register Azure DevOps Service Hook for repository."""
        pass
    
    async def unregister_service_hook(self, repo_id: str) -> None:
        """Unregister Azure DevOps Service Hook for repository."""
        pass
    
    async def check_existing_agent(self, pr_id: str) -> Optional[str]:
        """Check if agent already exists for PR."""
        pass
    
    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate existing agent instance."""
        pass
```

**Dependencies**:
- MySQL (repository configuration)
- Redis (agent tracking)
- Azure DevOps SDK (service hook management)
- Agent Orchestrator (agent spawning)

**Key Behaviors**:
- Validates PR belongs to monitored repository
- Checks for existing agent instances
- Terminates stale agents before spawning new ones
- Manages service hook registration/unregistration
- Implements retry logic with exponential backoff for Azure DevOps API calls

### 3. Agent Orchestrator

**Responsibility**: Spawn, monitor, and manage Review Agent instances.

**Interface**:
```python
class AgentOrchestrator:
    async def spawn_agent(self, pr_id: str, pr_metadata: PRMetadata) -> str:
        """Spawn new Review Agent instance and return agent ID."""
        pass
    
    async def monitor_agent(self, agent_id: str) -> AgentStatus:
        """Check agent execution status."""
        pass
    
    async def terminate_agent(self, agent_id: str, reason: str) -> None:
        """Forcefully terminate agent instance."""
        pass
    
    async def get_agent_state(self, agent_id: str) -> AgentState:
        """Retrieve current agent state from Redis."""
        pass
```

**Dependencies**:
- Redis (agent state management)
- LangGraph (agent instantiation)

**Key Behaviors**:
- Creates unique agent ID for each PR
- Initializes LangGraph state graph with PR context
- Stores agent metadata in Redis
- Monitors agent execution time (10-minute timeout)
- Cleans up resources on agent completion or timeout

### 4. Review Agent (LangGraph)

**Responsibility**: Execute autonomous review workflow for a single pull request.

**LangGraph State Graph**:
```mermaid
stateDiagram-v2
    [*] --> Initialize
    Initialize --> RetrieveCode
    RetrieveCode --> ParseFiles
    ParseFiles --> LineAnalysis
    LineAnalysis --> ArchitectureAnalysis
    ArchitectureAnalysis --> GenerateComments
    GenerateComments --> PublishComments
    PublishComments --> Complete
    Complete --> [*]
    
    RetrieveCode --> HandleError: API Failure
    ParseFiles --> HandleError: Parse Failure
    LineAnalysis --> HandleError: LLM Failure
    ArchitectureAnalysis --> HandleError: LLM Failure
    PublishComments --> HandleError: API Failure
    HandleError --> Complete
```

**State Schema**:
```python
class ReviewAgentState(TypedDict):
    pr_id: str
    pr_metadata: PRMetadata
    changed_files: List[FileChange]
    parsed_asts: Dict[str, ASTNode]
    line_comments: List[LineComment]
    summary_comment: Optional[SummaryComment]
    errors: List[ErrorRecord]
    phase: str  # current execution phase
    start_time: float
    end_time: Optional[float]
```

**Node Functions**:
- `initialize_node`: Load PR metadata and validate inputs
- `retrieve_code_node`: Fetch file diffs using Code Retriever
- `parse_files_node`: Parse changed files using tree-sitter
- `line_analysis_node`: Analyze each line using Code Analyzer
- `architecture_analysis_node`: Evaluate overall design using Architecture Analyzer
- `generate_comments_node`: Format analysis results as Azure DevOps comments
- `publish_comments_node`: Post comments using Comment Publisher
- `handle_error_node`: Log errors and determine recovery strategy

**Dependencies**:
- Code Retriever (file diff retrieval)
- Code Analyzer (line-level analysis)
- Architecture Analyzer (holistic analysis)
- Comment Publisher (comment posting)
- Redis (state persistence)

**Key Behaviors**:
- Persists state to Redis after each node execution
- Continues execution even when individual file analysis fails
- Aggregates errors for final reporting
- Implements timeout awareness (checks elapsed time)

### 5. Code Retriever

**Responsibility**: Retrieve code changes and file content from Azure DevOps.

**Interface**:
```python
class CodeRetriever:
    async def get_pr_diff(self, pr_id: str) -> List[FileChange]:
        """Retrieve complete diff for all changed files."""
        pass
    
    async def get_file_content(
        self, 
        repo_id: str, 
        file_path: str, 
        commit_id: str
    ) -> str:
        """Retrieve file content at specific commit."""
        pass
    
    async def get_pr_metadata(self, pr_id: str) -> PRMetadata:
        """Retrieve PR metadata including branches and author."""
        pass
```

**Dependencies**:
- Azure DevOps Python SDK

**Key Behaviors**:
- Retrieves file diffs with line-level change information
- Fetches file content from both source and target branches
- Handles binary files gracefully (skips analysis)
- Implements retry logic for transient failures
- Logs all API calls for observability

### 6. Code Analyzer

**Responsibility**: Perform line-level code quality analysis using AST parsing and LLM inference.

**Interface**:
```python
class CodeAnalyzer:
    async def analyze_file(
        self, 
        file_change: FileChange, 
        ast: ASTNode
    ) -> List[LineComment]:
        """Analyze single file and return line-level comments."""
        pass
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """Parse file content into AST using tree-sitter."""
        pass
    
    async def analyze_line(
        self, 
        line: str, 
        context: CodeContext, 
        ast_node: ASTNode
    ) -> Optional[LineComment]:
        """Analyze single line of code using LLM."""
        pass
```

**Dependencies**:
- tree-sitter (AST parsing)
- OpenAI/Azure OpenAI (LLM analysis)

**Key Behaviors**:
- Parses files using tree-sitter with language detection
- Extracts AST context for each modified line
- Sends line + context to LLM for analysis
- Detects code smells (long methods, deep nesting, duplication)
- Detects potential bugs (null risks, resource leaks, boundary errors)
- Detects security vulnerabilities (injection risks, insecure data handling)
- Evaluates naming conventions and documentation
- Checks error handling patterns
- Generates actionable suggestions with code examples
- Batches LLM requests for efficiency

### 7. Architecture Analyzer

**Responsibility**: Evaluate overall design and architectural patterns using LLM inference.

**Interface**:
```python
class ArchitectureAnalyzer:
    async def analyze_architecture(
        self, 
        changed_files: List[FileChange], 
        asts: Dict[str, ASTNode]
    ) -> SummaryComment:
        """Analyze overall architecture and return summary comment."""
        pass
    
    async def evaluate_solid_principles(
        self, 
        asts: Dict[str, ASTNode]
    ) -> List[SOLIDViolation]:
        """Evaluate adherence to SOLID principles."""
        pass
    
    async def identify_design_patterns(
        self, 
        asts: Dict[str, ASTNode]
    ) -> List[DesignPattern]:
        """Identify design patterns in use."""
        pass
    
    async def detect_architectural_issues(
        self, 
        asts: Dict[str, ASTNode]
    ) -> List[ArchitecturalIssue]:
        """Detect layering violations and circular dependencies."""
        pass
```

**Dependencies**:
- OpenAI/Azure OpenAI (LLM analysis)

**Key Behaviors**:
- Analyzes all changed files as cohesive unit
- Evaluates SOLID principles (SRP, OCP, LSP, ISP, DIP)
- Identifies design patterns (creational, structural, behavioral)
- Detects pattern violations and inconsistencies
- Detects layering violations and circular dependencies
- Suggests applicable design patterns with justification
- Generates high-level architectural recommendations
- Uses multi-shot prompting with examples for consistency

### 8. Comment Publisher

**Responsibility**: Post review comments to Azure DevOps pull requests.

**Interface**:
```python
class CommentPublisher:
    async def publish_line_comments(
        self, 
        pr_id: str, 
        comments: List[LineComment]
    ) -> PublishResult:
        """Publish line-level comments to PR."""
        pass
    
    async def publish_summary_comment(
        self, 
        pr_id: str, 
        comment: SummaryComment
    ) -> PublishResult:
        """Publish summary comment to PR overview."""
        pass
    
    async def batch_publish(
        self, 
        pr_id: str, 
        line_comments: List[LineComment],
        summary_comment: SummaryComment
    ) -> PublishResult:
        """Publish all comments in optimized batches."""
        pass
```

**Dependencies**:
- Azure DevOps Python SDK

**Key Behaviors**:
- Associates line comments with correct file path, line number, and commit ID
- Posts summary comment to PR overview
- Batches comment API calls for efficiency
- Implements retry logic with exponential backoff (3 retries)
- Logs failures with full context for debugging
- Handles API rate limiting gracefully

### 9. Repository Configuration Service

**Responsibility**: Manage repository monitoring configuration in MySQL.

**Interface**:
```python
class RepositoryConfigService:
    async def add_repository(self, repo_url: str) -> Repository:
        """Add repository to monitoring configuration."""
        pass
    
    async def remove_repository(self, repo_id: str) -> None:
        """Remove repository from monitoring configuration."""
        pass
    
    async def list_repositories(self) -> List[Repository]:
        """List all monitored repositories."""
        pass
    
    async def is_monitored(self, repo_id: str) -> bool:
        """Check if repository is monitored."""
        pass
    
    async def validate_repository_url(self, repo_url: str) -> ValidationResult:
        """Validate repository URL format."""
        pass
```

**Dependencies**:
- MySQL
- PR Monitor (for service hook registration)

**Key Behaviors**:
- Validates repository URL format (Azure DevOps format)
- Persists configuration to MySQL
- Triggers service hook registration on add
- Triggers service hook unregistration on remove
- Provides transaction support for atomic operations

### 10. Admin REST API (FastAPI)

**Responsibility**: Provide HTTP API for repository configuration management.

**Interface**:
```python
@app.post("/api/repositories")
async def add_repository(repo: RepositoryCreate) -> Repository:
    """Add repository to monitoring configuration."""
    pass

@app.delete("/api/repositories/{repo_id}")
async def remove_repository(repo_id: str) -> None:
    """Remove repository from monitoring configuration."""
    pass

@app.get("/api/repositories")
async def list_repositories() -> List[Repository]:
    """List all monitored repositories."""
    pass

@app.get("/api/agents")
async def list_active_agents() -> List[AgentInfo]:
    """List currently active review agents."""
    pass

@app.get("/api/agents/{agent_id}")
async def get_agent_status(agent_id: str) -> AgentStatus:
    """Get detailed status of specific agent."""
    pass
```

**Dependencies**:
- Repository Configuration Service
- Agent Orchestrator

**Key Behaviors**:
- Provides RESTful API for admin operations
- Returns appropriate HTTP status codes
- Validates request payloads
- Provides OpenAPI documentation

## Data Models

### MySQL Schema

```sql
-- Repository configuration table
CREATE TABLE repositories (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    organization VARCHAR(255) NOT NULL,
    project VARCHAR(255) NOT NULL,
    repository_name VARCHAR(255) NOT NULL,
    repository_url TEXT NOT NULL UNIQUE,
    service_hook_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT unique_repo UNIQUE (organization, project, repository_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_repositories_url ON repositories(repository_url(255));
CREATE INDEX idx_repositories_org_project ON repositories(organization, project);

-- Service hook registration tracking
CREATE TABLE service_hooks (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    repository_id CHAR(36) NOT NULL,
    hook_id VARCHAR(255) NOT NULL UNIQUE,
    hook_url TEXT NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'active', 'failed', 'pending'
    last_triggered_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_service_hooks_repo ON service_hooks(repository_id);
CREATE INDEX idx_service_hooks_status ON service_hooks(status);

-- Agent execution history (for observability)
CREATE TABLE agent_executions (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_id VARCHAR(255) NOT NULL UNIQUE,
    pr_id VARCHAR(255) NOT NULL,
    repository_id CHAR(36) NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'running', 'completed', 'failed', 'timeout'
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NULL,
    duration_ms INTEGER,
    line_comments_count INTEGER DEFAULT 0,
    summary_comment_generated BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repository_id) REFERENCES repositories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_agent_executions_pr ON agent_executions(pr_id);
CREATE INDEX idx_agent_executions_status ON agent_executions(status);
CREATE INDEX idx_agent_executions_repo ON agent_executions(repository_id);
CREATE INDEX idx_agent_executions_start_time ON agent_executions(start_time);
```

### Redis Data Structures

```python
# Agent state storage (hash)
# Key: agent:{agent_id}:state
{
    "pr_id": "12345",
    "phase": "line_analysis",
    "start_time": "1234567890.123",
    "changed_files": "[...]",  # JSON serialized
    "line_comments": "[...]",  # JSON serialized
    "errors": "[...]"  # JSON serialized
}

# Agent tracking set (to prevent duplicates)
# Key: active_agents:{pr_id}
# Value: Set of agent IDs
{"agent_abc123", "agent_def456"}

# Job queue (list)
# Key: job_queue:pr_reviews
# Value: List of PR event payloads (JSON)
[
    '{"pr_id": "12345", "repo_id": "...", "timestamp": "..."}',
    '{"pr_id": "12346", "repo_id": "...", "timestamp": "..."}'
]

# Agent timeout tracking (sorted set)
# Key: agent_timeouts
# Score: expiration timestamp
# Value: agent_id
{
    "agent_abc123": 1234567890.123,
    "agent_def456": 1234567900.456
}
```

### Python Data Models

```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from enum import Enum

# Repository models
class Repository(BaseModel):
    id: str
    organization: str
    project: str
    repository_name: str
    repository_url: HttpUrl
    service_hook_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class RepositoryCreate(BaseModel):
    repository_url: HttpUrl

# PR event models
class PREvent(BaseModel):
    event_type: str  # 'git.pullrequest.created', 'git.pullrequest.updated'
    pr_id: str
    repository_id: str
    source_branch: str
    target_branch: str
    author: str
    title: str
    description: Optional[str] = None
    timestamp: datetime

class PRMetadata(BaseModel):
    pr_id: str
    repository_id: str
    source_branch: str
    target_branch: str
    author: str
    title: str
    description: Optional[str] = None
    source_commit_id: str
    target_commit_id: str

# File change models
class ChangeType(str, Enum):
    ADD = "add"
    EDIT = "edit"
    DELETE = "delete"

class LineChange(BaseModel):
    line_number: int
    change_type: ChangeType
    content: str

class FileChange(BaseModel):
    file_path: str
    change_type: ChangeType
    added_lines: List[LineChange]
    modified_lines: List[LineChange]
    deleted_lines: List[LineChange]
    source_content: Optional[str] = None
    target_content: Optional[str] = None

# AST models
class ASTNode(BaseModel):
    node_type: str
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    children: List['ASTNode'] = []
    text: Optional[str] = None

# Comment models
class CommentSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class CommentCategory(str, Enum):
    CODE_SMELL = "code_smell"
    BUG = "bug"
    SECURITY = "security"
    BEST_PRACTICE = "best_practice"
    ARCHITECTURE = "architecture"

class LineComment(BaseModel):
    file_path: str
    line_number: int
    severity: CommentSeverity
    category: CommentCategory
    message: str
    suggestion: Optional[str] = None
    code_example: Optional[str] = None

class SummaryComment(BaseModel):
    message: str
    solid_violations: List[str] = []
    design_patterns_identified: List[str] = []
    design_pattern_suggestions: List[str] = []
    architectural_issues: List[str] = []

# Agent models
class AgentStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class AgentState(BaseModel):
    agent_id: str
    pr_id: str
    pr_metadata: PRMetadata
    phase: str
    start_time: float
    end_time: Optional[float] = None
    changed_files: List[FileChange] = []
    parsed_asts: Dict[str, ASTNode] = {}
    line_comments: List[LineComment] = []
    summary_comment: Optional[SummaryComment] = None
    errors: List[str] = []

class AgentInfo(BaseModel):
    agent_id: str
    pr_id: str
    status: AgentStatus
    phase: str
    start_time: datetime
    elapsed_seconds: float

# Analysis models
class SOLIDViolation(BaseModel):
    principle: str  # 'SRP', 'OCP', 'LSP', 'ISP', 'DIP'
    description: str
    file_path: str
    suggestion: str

class DesignPattern(BaseModel):
    pattern_name: str
    pattern_type: str  # 'creational', 'structural', 'behavioral'
    file_paths: List[str]
    description: str

class ArchitecturalIssue(BaseModel):
    issue_type: str  # 'layering_violation', 'circular_dependency'
    description: str
    affected_files: List[str]
    suggestion: str

# Error models
class ErrorRecord(BaseModel):
    phase: str
    error_type: str
    message: str
    stack_trace: Optional[str] = None
    timestamp: datetime

# API response models
class WebhookResponse(BaseModel):
    status: str
    message: str

class PublishResult(BaseModel):
    success: bool
    published_count: int
    failed_count: int
    errors: List[str] = []

class ValidationResult(BaseModel):
    valid: bool
    error_message: Optional[str] = None
```


## Language-Specific Analyzer Plugin Architecture

### Design Goals

The system must support Java and Angular initially while being extensible for additional languages without modifying core components. This is achieved through a plugin-based architecture with clear interfaces and language-agnostic orchestration.

### Plugin Architecture

```mermaid
graph TB
    subgraph "Core Analysis Engine"
        CA[Code Analyzer Core]
        PM[Plugin Manager]
    end
    
    subgraph "Language Plugins"
        JP[Java Plugin]
        AP[Angular Plugin]
        PP[Python Plugin<br/>Future]
        TP[TypeScript Plugin<br/>Future]
    end
    
    subgraph "Plugin Components"
        subgraph "Java Plugin Components"
            JPA[Java Parser<br/>tree-sitter-java]
            JRA[Java Rules Engine]
            JCG[Java Context Generator]
        end
        
        subgraph "Angular Plugin Components"
            APA[Angular Parser<br/>tree-sitter-typescript]
            ARA[Angular Rules Engine]
            ACG[Angular Context Generator]
        end
    end
    
    CA --> PM
    PM --> JP
    PM --> AP
    PM -.-> PP
    PM -.-> TP
    
    JP --> JPA
    JP --> JRA
    JP --> JCG
    
    AP --> APA
    AP --> ARA
    AP --> ACG
    
    style PP stroke-dasharray: 5 5
    style TP stroke-dasharray: 5 5
```

### Language Plugin Interface

Each language plugin implements a standard interface that the Code Analyzer Core uses for analysis:

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class LanguagePlugin(ABC):
    """Base interface for language-specific analysis plugins."""
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language name (e.g., 'java', 'angular', 'python')."""
        pass
    
    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """Return supported file extensions (e.g., ['.java', '.kt'])."""
        pass
    
    @abstractmethod
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """Parse file content into AST using language-specific parser."""
        pass
    
    @abstractmethod
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        """Extract relevant context for a specific line."""
        pass
    
    @abstractmethod
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        """Return language-specific analysis rules."""
        pass
    
    @abstractmethod
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        """Format code suggestion in language-specific syntax."""
        pass
    
    @abstractmethod
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """Detect language-specific design patterns."""
        pass
```

### Plugin Manager

The Plugin Manager handles plugin registration, discovery, and lifecycle:

```python
class PluginManager:
    """Manages language plugin registration and selection."""
    
    def __init__(self):
        self._plugins: Dict[str, LanguagePlugin] = {}
        self._extension_map: Dict[str, str] = {}
    
    def register_plugin(self, plugin: LanguagePlugin) -> None:
        """Register a language plugin."""
        self._plugins[plugin.language_name] = plugin
        for ext in plugin.file_extensions:
            self._extension_map[ext] = plugin.language_name
    
    def get_plugin_for_file(self, file_path: str) -> Optional[LanguagePlugin]:
        """Get appropriate plugin based on file extension."""
        ext = Path(file_path).suffix
        language = self._extension_map.get(ext)
        return self._plugins.get(language) if language else None
    
    def list_supported_languages(self) -> List[str]:
        """List all registered language plugins."""
        return list(self._plugins.keys())
    
    async def initialize_plugins(self) -> None:
        """Initialize all registered plugins."""
        # Auto-discover plugins from plugins directory
        # Load plugin configurations
        # Initialize tree-sitter parsers
        pass
```

### Java Plugin Implementation

```python
class JavaPlugin(LanguagePlugin):
    """Java language analysis plugin."""
    
    def __init__(self):
        self._parser = tree_sitter.Parser()
        self._parser.set_language(tree_sitter.Language('build/languages.so', 'java'))
        self._rules = self._load_java_rules()
    
    @property
    def language_name(self) -> str:
        return "java"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".java"]
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """Parse Java file using tree-sitter-java."""
        tree = self._parser.parse(bytes(content, "utf8"))
        return self._convert_to_ast_node(tree.root_node)
    
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        """Extract Java-specific context including class, method, and imports."""
        # Find enclosing class
        enclosing_class = self._find_enclosing_node(ast, line_number, "class_declaration")
        # Find enclosing method
        enclosing_method = self._find_enclosing_node(ast, line_number, "method_declaration")
        # Extract imports
        imports = self._extract_imports(ast)
        # Extract method signature
        method_signature = self._extract_method_signature(enclosing_method)
        
        return CodeContext(
            language="java",
            file_path=file_path,
            line_number=line_number,
            enclosing_class=enclosing_class.text if enclosing_class else None,
            enclosing_method=method_signature,
            imports=imports,
            surrounding_lines=self._get_surrounding_lines(file_content, line_number, 3)
        )
    
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        """Return Java-specific analysis rules."""
        return [
            AnalysisRule(
                name="avoid_null_pointer",
                category=CommentCategory.BUG,
                severity=CommentSeverity.ERROR,
                pattern="Potential null pointer dereference",
                llm_prompt="Check if this Java code properly handles null values..."
            ),
            AnalysisRule(
                name="resource_leak",
                category=CommentCategory.BUG,
                severity=CommentSeverity.WARNING,
                pattern="Resource not closed in try-with-resources",
                llm_prompt="Check if Java resources (streams, connections) are properly closed..."
            ),
            AnalysisRule(
                name="exception_handling",
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.WARNING,
                pattern="Empty catch block or generic exception catching",
                llm_prompt="Check if Java exception handling follows best practices..."
            ),
            # Additional Java-specific rules...
        ]
    
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        """Format code suggestion in Java syntax."""
        # Generate Java-specific code examples
        # Use Java formatting conventions
        pass
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """Detect Java design patterns (Singleton, Factory, Builder, etc.)."""
        patterns = []
        
        # Detect Singleton pattern
        if self._is_singleton_pattern(ast):
            patterns.append(DesignPattern(
                pattern_name="Singleton",
                pattern_type="creational",
                file_paths=[context.file_path],
                description="Singleton pattern detected with private constructor and static instance"
            ))
        
        # Detect Factory pattern
        # Detect Builder pattern
        # etc.
        
        return patterns
```

### Angular Plugin Implementation

```python
class AngularPlugin(LanguagePlugin):
    """Angular/TypeScript language analysis plugin."""
    
    def __init__(self):
        self._parser = tree_sitter.Parser()
        self._parser.set_language(tree_sitter.Language('build/languages.so', 'typescript'))
        self._rules = self._load_angular_rules()
    
    @property
    def language_name(self) -> str:
        return "angular"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".ts", ".component.ts", ".service.ts", ".module.ts", ".html"]
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """Parse Angular/TypeScript file using tree-sitter-typescript."""
        tree = self._parser.parse(bytes(content, "utf8"))
        return self._convert_to_ast_node(tree.root_node)
    
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        """Extract Angular-specific context including component, service, decorators."""
        # Find enclosing class
        enclosing_class = self._find_enclosing_node(ast, line_number, "class_declaration")
        # Find decorators (@Component, @Injectable, etc.)
        decorators = self._extract_decorators(enclosing_class)
        # Find enclosing method
        enclosing_method = self._find_enclosing_node(ast, line_number, "method_definition")
        # Extract imports
        imports = self._extract_imports(ast)
        
        return CodeContext(
            language="angular",
            file_path=file_path,
            line_number=line_number,
            enclosing_class=enclosing_class.text if enclosing_class else None,
            enclosing_method=enclosing_method.text if enclosing_method else None,
            decorators=decorators,
            imports=imports,
            surrounding_lines=self._get_surrounding_lines(file_content, line_number, 3)
        )
    
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        """Return Angular-specific analysis rules."""
        return [
            AnalysisRule(
                name="unsubscribe_observables",
                category=CommentCategory.BUG,
                severity=CommentSeverity.WARNING,
                pattern="Observable subscription without unsubscribe",
                llm_prompt="Check if Angular Observable subscriptions are properly unsubscribed..."
            ),
            AnalysisRule(
                name="change_detection_performance",
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern="Inefficient change detection strategy",
                llm_prompt="Check if Angular component uses appropriate change detection strategy..."
            ),
            AnalysisRule(
                name="dependency_injection",
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.WARNING,
                pattern="Improper dependency injection usage",
                llm_prompt="Check if Angular dependency injection follows best practices..."
            ),
            # Additional Angular-specific rules...
        ]
    
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        """Format code suggestion in TypeScript/Angular syntax."""
        # Generate Angular-specific code examples
        # Use TypeScript formatting conventions
        pass
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """Detect Angular patterns (Service, Component, Directive, etc.)."""
        patterns = []
        
        # Detect Service pattern
        if self._has_injectable_decorator(ast):
            patterns.append(DesignPattern(
                pattern_name="Service",
                pattern_type="structural",
                file_paths=[context.file_path],
                description="Angular Service pattern with @Injectable decorator"
            ))
        
        # Detect Component pattern
        # Detect Observable patterns
        # etc.
        
        return patterns
```

### Plugin Configuration

Plugins are configured via YAML files in the `plugins/` directory:

```yaml
# plugins/java/config.yaml
name: java
version: 1.0.0
file_extensions:
  - .java
tree_sitter_grammar: tree-sitter-java
analysis_rules:
  - avoid_null_pointer
  - resource_leak
  - exception_handling
  - naming_conventions
  - code_complexity
llm_prompts:
  system_prompt: |
    You are a Java code reviewer. Analyze the provided code for bugs,
    code smells, security issues, and best practice violations.
  context_template: |
    File: {file_path}
    Class: {enclosing_class}
    Method: {enclosing_method}
    Line {line_number}: {line_content}
```

```yaml
# plugins/angular/config.yaml
name: angular
version: 1.0.0
file_extensions:
  - .ts
  - .component.ts
  - .service.ts
  - .module.ts
  - .html
tree_sitter_grammar: tree-sitter-typescript
analysis_rules:
  - unsubscribe_observables
  - change_detection_performance
  - dependency_injection
  - template_syntax
  - rxjs_best_practices
llm_prompts:
  system_prompt: |
    You are an Angular code reviewer. Analyze the provided TypeScript/Angular
    code for bugs, performance issues, and best practice violations.
  context_template: |
    File: {file_path}
    Component/Service: {enclosing_class}
    Decorators: {decorators}
    Method: {enclosing_method}
    Line {line_number}: {line_content}
```

### Adding New Language Support

To add support for a new language:

1. **Create Plugin Class**: Implement `LanguagePlugin` interface
2. **Add tree-sitter Grammar**: Install language-specific tree-sitter grammar
3. **Define Analysis Rules**: Create language-specific rules in config YAML
4. **Implement Pattern Detection**: Add language-specific pattern detection logic
5. **Register Plugin**: Add plugin registration in `PluginManager` initialization

Example for adding Python support:

```python
# plugins/python/python_plugin.py
class PythonPlugin(LanguagePlugin):
    @property
    def language_name(self) -> str:
        return "python"
    
    @property
    def file_extensions(self) -> List[str]:
        return [".py"]
    
    # Implement remaining interface methods...
```

```yaml
# plugins/python/config.yaml
name: python
version: 1.0.0
file_extensions:
  - .py
tree_sitter_grammar: tree-sitter-python
analysis_rules:
  - type_hints
  - exception_handling
  - pep8_compliance
  - security_issues
```

### Integration with Code Analyzer Core

The Code Analyzer Core uses the Plugin Manager to delegate language-specific operations:

```python
class CodeAnalyzer:
    def __init__(self, plugin_manager: PluginManager):
        self._plugin_manager = plugin_manager
        self._llm_client = OpenAIClient()
    
    async def analyze_file(
        self, 
        file_change: FileChange, 
        ast: ASTNode
    ) -> List[LineComment]:
        """Analyze file using appropriate language plugin."""
        
        # Get plugin for file
        plugin = self._plugin_manager.get_plugin_for_file(file_change.file_path)
        if not plugin:
            logger.warning(f"No plugin found for {file_change.file_path}, skipping")
            return []
        
        # Get language-specific rules
        rules = await plugin.get_analysis_rules()
        
        comments = []
        for line_change in file_change.modified_lines + file_change.added_lines:
            # Extract context using plugin
            context = await plugin.extract_context(
                line_change.line_number,
                ast,
                file_change.target_content
            )
            
            # Analyze line with LLM using plugin rules
            for rule in rules:
                issue = await self._analyze_with_llm(
                    line_change.content,
                    context,
                    rule
                )
                
                if issue:
                    # Format suggestion using plugin
                    suggestion = await plugin.format_suggestion(issue, context)
                    
                    comments.append(LineComment(
                        file_path=file_change.file_path,
                        line_number=line_change.line_number,
                        severity=rule.severity,
                        category=rule.category,
                        message=issue.message,
                        suggestion=suggestion
                    ))
        
        return comments
```

This architecture ensures:
- **Modularity**: Core components remain unchanged when adding languages
- **Extensibility**: New languages added via plugin implementation
- **Consistency**: All plugins follow same interface contract
- **Maintainability**: Language-specific logic isolated in plugins
- **Testability**: Plugins can be tested independently

## Deployment Architecture

### Docker Containerization

The system is deployed as multiple Docker containers orchestrated with Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'

services:
  # FastAPI application
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+aiomysql://user:pass@mysql:3306/pr_review
      - REDIS_URL=redis://redis:6379/0
      - AZURE_DEVOPS_PAT=${AZURE_DEVOPS_PAT}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
    depends_on:
      - mysql
      - redis
    volumes:
      - ./plugins:/app/plugins
    restart: unless-stopped
  
  # Agent worker (processes review jobs from queue)
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: python -m app.worker
    environment:
      - DATABASE_URL=mysql+aiomysql://user:pass@mysql:3306/pr_review
      - REDIS_URL=redis://redis:6379/0
      - AZURE_DEVOPS_PAT=${AZURE_DEVOPS_PAT}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - mysql
      - redis
    volumes:
      - ./plugins:/app/plugins
    restart: unless-stopped
    deploy:
      replicas: 3  # Multiple workers for parallel processing
  
  # MySQL database
  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=rootpass
      - MYSQL_DATABASE=pr_review
      - MYSQL_USER=user
      - MYSQL_PASSWORD=pass
    volumes:
      - mysql_data:/var/lib/mysql
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "3306:3306"
    restart: unless-stopped
    command: --default-authentication-plugin=mysql_native_password
  
  # Redis for state and queue
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
  
  # Angular frontend (optional)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "4200:80"
    depends_on:
      - api
    restart: unless-stopped

volumes:
  mysql_data:
  redis_data:
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for tree-sitter
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build tree-sitter grammars
COPY build_grammars.py .
RUN python build_grammars.py

# Copy application code
COPY app/ ./app/
COPY plugins/ ./plugins/

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Deployment Diagram

```mermaid
graph TB
    subgraph "Azure DevOps"
        ADO[Azure DevOps<br/>Service Hooks]
    end
    
    subgraph "Docker Host"
        subgraph "API Container"
            API[FastAPI<br/>Webhook Handler]
        end
        
        subgraph "Worker Containers"
            W1[Worker 1<br/>Review Agent]
            W2[Worker 2<br/>Review Agent]
            W3[Worker 3<br/>Review Agent]
        end
        
        subgraph "Data Containers"
            MY[(MySQL)]
            RD[(Redis)]
        end
        
        subgraph "Frontend Container"
            UI[Angular UI<br/>Nginx]
        end
    end
    
    ADO -->|Webhook| API
    API --> RD
    API --> MY
    W1 --> RD
    W1 --> MY
    W1 --> ADO
    W2 --> RD
    W2 --> MY
    W2 --> ADO
    W3 --> RD
    W3 --> MY
    W3 --> ADO
    UI --> API
```

### Scaling Considerations

**Horizontal Scaling**:
- Multiple worker containers process review jobs in parallel
- Redis job queue distributes work across workers
- Stateless API containers can be scaled independently

**Resource Allocation**:
- API container: 1 CPU, 2GB RAM (handles webhooks, lightweight)
- Worker container: 2 CPU, 4GB RAM (LLM inference, AST parsing)
- MySQL: 2 CPU, 4GB RAM
- Redis: 1 CPU, 2GB RAM

**Performance Targets**:
- Webhook response time: < 100ms
- PR analysis completion: < 5 minutes for typical PR (< 20 files)
- Concurrent PR reviews: 10+ simultaneous reviews


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Repository Configuration Persistence

*For any* valid Azure DevOps repository identifier, when stored in the Repository_Configuration and the system is restarted (database connection reset), querying for that repository should return the same repository data.

**Validates: Requirements 1.1, 1.2**

### Property 2: Repository URL Validation

*For any* string input to Repository_Configuration, the validation function should correctly accept well-formed Azure DevOps repository URLs and reject malformed URLs with descriptive error messages.

**Validates: Requirements 1.5, 1.6**

### Property 3: PR Metadata Completeness

*For any* pull request ID, when retrieving PR metadata, the returned data structure should contain all required fields: branch names (source and target), changed files list, author information, and commit identifiers.

**Validates: Requirements 2.2, 4.1, 4.2, 4.3**

### Property 4: PR Event to Job Queue Mapping

*For any* PR_Event received by the webhook handler, a corresponding review job should appear in the Redis Job_Queue with matching PR identifier and metadata.

**Validates: Requirements 3.1**

### Property 5: Agent-to-PR One-to-One Association

*For any* Review_Agent instance, it should be associated with exactly one pull request identifier throughout its lifecycle.

**Validates: Requirements 3.2**

### Property 6: Agent State Persistence Round-Trip

*For any* Review_Agent state update, storing the state to Redis and immediately retrieving it should return an equivalent state object with all fields preserved.

**Validates: Requirements 3.3**

### Property 7: Agent Resource Cleanup

*For any* Review_Agent that completes its analysis (successfully or with errors), the agent should no longer appear in the active agents tracking set and should have released its resources.

**Validates: Requirements 3.4**

### Property 8: Single Active Agent Per PR

*For any* pull request identifier, there should be at most one active Review_Agent instance in the Redis tracking set at any given time.

**Validates: Requirements 3.5, 3.6**

### Property 9: Analysis Resilience to File Failures

*For any* set of changed files where a subset fails to retrieve or parse, the Review_Agent should continue processing the remaining files and generate comments for successfully analyzed files.

**Validates: Requirements 4.4, 9.4**

### Property 10: File Parsing Produces AST

*For any* valid source file in a supported language, parsing with the appropriate tree-sitter grammar should produce a non-empty AST structure with root node.

**Validates: Requirements 5.1**

### Property 11: Modified Lines Analysis Coverage

*For any* file with modified or added lines, the Code_Analyzer should process each modified/added line through the analysis pipeline (though not necessarily generate a comment for each).

**Validates: Requirements 5.2**

### Property 12: Comment Generation Completeness

*For any* identified code issue, the generated Line_Comment should contain all required fields: file path, line number, severity, category, message, and the file path and line number should match the analyzed code location.

**Validates: Requirements 5.6, 5.7, 8.3**

### Property 13: Architectural Analysis Input Completeness

*For any* PR analysis, the Architecture_Analyzer should receive all changed files as input for cohesive analysis, not individual files in isolation.

**Validates: Requirements 6.1**

### Property 14: Architectural Summary Generation

*For any* architectural analysis that identifies issues or patterns, a Summary_Comment should be generated containing the findings and recommendations.

**Validates: Requirements 6.6**

### Property 15: Best Practice Suggestion Completeness

*For any* best practice violation identified by the Code_Analyzer, the generated comment should include a specific improvement suggestion, not just identification of the problem.

**Validates: Requirements 7.6**

### Property 16: Language Plugin Selection

*For any* file being analyzed, the Code_Analyzer should select the appropriate language plugin based on file extension, or skip the file if no plugin is available.

**Validates: Requirements 7.1**

### Property 17: Comment Publishing Completeness

*For any* set of Line_Comments generated by analysis, all comments should be sent to the Azure DevOps API for publishing (though individual API calls may fail and retry).

**Validates: Requirements 8.1**

### Property 18: Retry with Exponential Backoff

*For any* failed API call (comment publishing or PR data retrieval), the system should retry with exponentially increasing delays between attempts, up to the configured maximum retry count.

**Validates: Requirements 8.4, 9.1**

### Property 19: Error Logging Completeness

*For any* error that occurs during system operation (agent crashes, authentication failures, API failures), an error log entry should be created containing the error message, stack trace, and contextual information (phase, PR ID, etc.).

**Validates: Requirements 9.2, 9.5, 10.4**

### Property 20: Agent Timeout Enforcement

*For any* Review_Agent that exceeds the configured timeout duration (10 minutes), the Agent Orchestrator should terminate the agent and log a timeout error.

**Validates: Requirements 9.3**

### Property 21: Event Logging with Required Fields

*For any* PR_Event processed by the system, a log entry should be created containing at minimum: timestamp, event type, PR identifier, and repository identifier.

**Validates: Requirements 10.1**

### Property 22: Phase Transition Logging

*For any* Review_Agent execution, log entries should be created for the start and completion of each analysis phase (initialize, retrieve_code, parse_files, line_analysis, architecture_analysis, publish_comments).

**Validates: Requirements 10.2**

### Property 23: API Call Logging

*For any* API call to Azure DevOps, a log entry should be created containing the request details (endpoint, method) and response status code.

**Validates: Requirements 10.3**

### Property 24: Metrics Emission

*For any* completed Review_Agent execution, metrics should be emitted including: total execution time, number of line comments generated, number of files analyzed, and API call count.

**Validates: Requirements 10.5**

### Property 25: Structured Log Format

*For any* log entry created by the system, the log should be in a structured, machine-readable format (JSON) containing standard fields: timestamp, level, message, and context.

**Validates: Requirements 10.6**


## Error Handling

### Error Categories

The system handles four categories of errors with distinct strategies:

1. **Transient Errors**: Temporary failures that may succeed on retry (network timeouts, API rate limits)
2. **Permanent Errors**: Failures that won't succeed on retry (authentication failures, invalid data)
3. **Partial Errors**: Failures affecting subset of operation (single file parse failure in multi-file analysis)
4. **Critical Errors**: System-level failures requiring immediate attention (database connection loss)

### Error Handling Strategies

#### Transient Error Handling

**Strategy**: Retry with exponential backoff

```python
async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> Any:
    """Retry function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await func()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

**Applied to**:
- Azure DevOps API calls (PR data retrieval, comment publishing)
- Redis connection failures
- MySQL connection failures

**Configuration**:
- Max retries: 3 for comment publishing, 5 for PR data retrieval
- Base delay: 1 second
- Max delay: 60 seconds
- Timeout: 5 minutes total for PR data retrieval


#### Permanent Error Handling

**Strategy**: Fail fast with detailed logging

```python
class PermanentError(Exception):
    """Error that won't succeed on retry."""
    pass

async def handle_permanent_error(error: PermanentError, context: Dict[str, Any]) -> None:
    """Handle permanent errors with logging and notification."""
    logger.error(
        "Permanent error occurred",
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc(),
            "context": context
        }
    )
    # Optionally notify administrators
    # Do not retry
```

**Applied to**:
- Authentication failures (invalid PAT token)
- Invalid repository URLs
- Malformed webhook payloads
- Invalid PR identifiers

**Behavior**:
- Log error with full context
- Return error response to caller
- Do not retry operation
- Optionally alert administrators for critical failures


#### Partial Error Handling

**Strategy**: Continue with available data, log failures

```python
async def analyze_files_with_partial_failure(
    files: List[FileChange]
) -> Tuple[List[LineComment], List[ErrorRecord]]:
    """Analyze files, continuing even if individual files fail."""
    comments = []
    errors = []
    
    for file in files:
        try:
            file_comments = await analyze_single_file(file)
            comments.extend(file_comments)
        except Exception as e:
            logger.warning(f"Failed to analyze {file.file_path}: {e}")
            errors.append(ErrorRecord(
                phase="line_analysis",
                error_type=type(e).__name__,
                message=f"Failed to analyze {file.file_path}: {str(e)}",
                timestamp=datetime.now()
            ))
            # Continue with next file
    
    return comments, errors
```

**Applied to**:
- Individual file parsing failures (continue with other files)
- Individual file analysis failures (continue with other files)
- Individual comment publishing failures (continue with other comments)
- LLM API failures for specific lines (continue with other lines)

**Behavior**:
- Log error for failed item
- Continue processing remaining items
- Include error summary in final report
- Ensure at least partial results are delivered


#### Critical Error Handling

**Strategy**: Graceful degradation and resource cleanup

```python
async def handle_critical_error(error: Exception, agent_id: str) -> None:
    """Handle critical errors with cleanup and alerting."""
    logger.critical(
        "Critical error in agent execution",
        extra={
            "agent_id": agent_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": traceback.format_exc()
        }
    )
    
    # Clean up resources
    await cleanup_agent_resources(agent_id)
    
    # Update agent status to failed
    await update_agent_status(agent_id, AgentStatus.FAILED)
    
    # Alert administrators
    await send_alert(f"Critical error in agent {agent_id}")
```

**Applied to**:
- Database connection loss
- Redis connection loss
- Agent crashes
- Out of memory errors
- Unhandled exceptions in agent workflow

**Behavior**:
- Log critical error with full context
- Clean up agent resources (remove from tracking, release memory)
- Update agent status to failed
- Alert administrators
- Ensure system remains operational for other PRs


### Timeout Management

**Agent Execution Timeout**: 10 minutes

```python
async def monitor_agent_timeout(agent_id: str, timeout_seconds: int = 600) -> None:
    """Monitor agent execution and terminate if timeout exceeded."""
    start_time = time.time()
    
    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.error(f"Agent {agent_id} exceeded timeout of {timeout_seconds}s")
            await terminate_agent(agent_id, reason="timeout")
            break
        
        # Check if agent completed
        status = await get_agent_status(agent_id)
        if status in [AgentStatus.COMPLETED, AgentStatus.FAILED]:
            break
```

**API Call Timeouts**:
- Azure DevOps API calls: 30 seconds per request
- LLM API calls: 60 seconds per request
- Database queries: 10 seconds per query

### Circuit Breaker Pattern

For external service calls (Azure DevOps API, LLM API), implement circuit breaker to prevent cascading failures:

```python
class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    async def call(self, func: Callable) -> Any:
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func()
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning("Circuit breaker opened due to repeated failures")
            
            raise
```


### Error Recovery and State Management

**Agent State Persistence**: Agent state is persisted to Redis after each phase completion, enabling recovery from crashes:

```python
async def execute_agent_node(node_func: Callable, state: ReviewAgentState) -> ReviewAgentState:
    """Execute agent node with state persistence."""
    try:
        # Execute node
        new_state = await node_func(state)
        
        # Persist state to Redis
        await save_agent_state(new_state.agent_id, new_state)
        
        return new_state
    except Exception as e:
        # Log error
        state.errors.append(ErrorRecord(
            phase=state.phase,
            error_type=type(e).__name__,
            message=str(e),
            stack_trace=traceback.format_exc(),
            timestamp=datetime.now()
        ))
        
        # Persist error state
        await save_agent_state(state.agent_id, state)
        
        # Decide whether to continue or fail
        if isinstance(e, CriticalError):
            raise
        else:
            # Continue to next phase
            return state
```

**Recovery Scenarios**:

1. **Agent Crash**: State persisted in Redis allows inspection of last successful phase
2. **System Restart**: Active agents can be identified from Redis and either resumed or terminated
3. **Partial Completion**: If agent completes some files before failure, those results are preserved


## Testing Strategy

### Dual Testing Approach

The system employs both unit testing and property-based testing for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, error conditions, and integration points
- **Property tests**: Verify universal properties across all inputs using randomized test data

Both approaches are complementary and necessary. Unit tests catch concrete bugs and verify specific scenarios, while property tests verify general correctness across a wide input space.

### Property-Based Testing

**Framework**: Hypothesis (Python property-based testing library)

**Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test references its design document property via comment tag
- Tag format: `# Feature: azure-devops-pr-review-agent, Property {number}: {property_text}`

**Example Property Test**:

```python
from hypothesis import given, strategies as st
import pytest

# Feature: azure-devops-pr-review-agent, Property 1: Repository Configuration Persistence
@given(
    org=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    project=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    repo=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
)
@pytest.mark.asyncio
async def test_repository_persistence_round_trip(org: str, project: str, repo: str):
    """Property 1: Repository data persists across system restarts."""
    # Arrange
    repo_url = f"https://dev.azure.com/{org}/{project}/_git/{repo}"
    config_service = RepositoryConfigService()
    
    # Act: Store repository
    stored_repo = await config_service.add_repository(repo_url)
    
    # Simulate restart by creating new service instance
    new_config_service = RepositoryConfigService()
    
    # Assert: Retrieved data matches stored data
    retrieved_repo = await new_config_service.get_repository(stored_repo.id)
    assert retrieved_repo.organization == org
    assert retrieved_repo.project == project
    assert retrieved_repo.repository_name == repo
    assert retrieved_repo.repository_url == repo_url
```


### Unit Testing Strategy

**Framework**: pytest with pytest-asyncio for async support

**Test Organization**:
```
tests/
├── unit/
│   ├── test_webhook_handler.py
│   ├── test_pr_monitor.py
│   ├── test_agent_orchestrator.py
│   ├── test_code_analyzer.py
│   ├── test_architecture_analyzer.py
│   ├── test_comment_publisher.py
│   ├── test_repository_config.py
│   └── plugins/
│       ├── test_java_plugin.py
│       └── test_angular_plugin.py
├── integration/
│   ├── test_agent_workflow.py
│   ├── test_azure_devops_integration.py
│   └── test_redis_state_management.py
├── property/
│   ├── test_properties_repository.py
│   ├── test_properties_agent.py
│   ├── test_properties_analysis.py
│   └── test_properties_error_handling.py
└── fixtures/
    ├── sample_prs.py
    ├── sample_code.py
    └── mock_responses.py
```

**Unit Test Focus Areas**:

1. **Specific Examples**: Test known code smells, bugs, and security issues
2. **Edge Cases**: Empty files, binary files, very large files, special characters
3. **Error Conditions**: API failures, parsing errors, timeout scenarios
4. **Integration Points**: Azure DevOps API mocking, Redis operations, MySQL queries

**Example Unit Test**:

```python
@pytest.mark.asyncio
async def test_java_plugin_detects_null_pointer_risk():
    """Unit test: Java plugin detects specific null pointer risk pattern."""
    # Arrange
    java_code = '''
    public void processUser(User user) {
        String name = user.getName();  // Potential NPE
        System.out.println(name.toUpperCase());
    }
    '''
    plugin = JavaPlugin()
    
    # Act
    ast = await plugin.parse_file("Test.java", java_code)
    context = await plugin.extract_context(2, ast, java_code)
    rules = await plugin.get_analysis_rules()
    null_check_rule = next(r for r in rules if r.name == "avoid_null_pointer")
    
    # Assert
    # This would involve calling the analyzer with mocked LLM
    # and verifying that a null pointer warning is generated
```


### Integration Testing

**Focus**: Test interactions between components and external services

**Key Integration Tests**:

1. **End-to-End Agent Workflow**: Test complete flow from webhook to comment publishing
2. **Azure DevOps API Integration**: Test real API calls (in staging environment)
3. **Redis State Management**: Test state persistence and retrieval across operations
4. **MySQL Operations**: Test database transactions and queries
5. **LangGraph State Transitions**: Test agent state graph execution

**Example Integration Test**:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_agent_workflow(test_pr_event, mock_azure_devops_api):
    """Integration test: Complete agent workflow from event to comments."""
    # Arrange
    pr_monitor = PRMonitor()
    agent_orchestrator = AgentOrchestrator()
    
    # Act
    await pr_monitor.process_pr_event(test_pr_event)
    
    # Wait for agent to complete (with timeout)
    agent_id = await wait_for_agent_completion(test_pr_event.pr_id, timeout=60)
    
    # Assert
    agent_state = await agent_orchestrator.get_agent_state(agent_id)
    assert agent_state.phase == "complete"
    assert len(agent_state.line_comments) > 0
    assert agent_state.summary_comment is not None
    
    # Verify comments were published to mock API
    published_comments = mock_azure_devops_api.get_published_comments(test_pr_event.pr_id)
    assert len(published_comments) == len(agent_state.line_comments)
```


### Test Data Generation

**Strategies for generating test data**:

1. **Hypothesis Strategies**: For property-based tests, define custom strategies for domain objects

```python
from hypothesis import strategies as st

# Strategy for generating valid Azure DevOps repository URLs
@st.composite
def azure_devops_repo_url(draw):
    org = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    project = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    repo = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    return f"https://dev.azure.com/{org}/{project}/_git/{repo}"

# Strategy for generating PR events
@st.composite
def pr_event(draw):
    return PREvent(
        event_type=draw(st.sampled_from(['git.pullrequest.created', 'git.pullrequest.updated'])),
        pr_id=draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Nd',)))),
        repository_id=draw(st.uuids()).hex,
        source_branch=draw(st.text(min_size=1, max_size=50)),
        target_branch=draw(st.text(min_size=1, max_size=50)),
        author=draw(st.emails()),
        title=draw(st.text(min_size=1, max_size=200)),
        timestamp=draw(st.datetimes())
    )
```

2. **Fixture Files**: Store sample code files with known issues for unit tests

```python
# tests/fixtures/sample_code.py
JAVA_NULL_POINTER_EXAMPLE = '''
public class UserService {
    public void processUser(User user) {
        String name = user.getName();  // NPE risk
        System.out.println(name.toUpperCase());
    }
}
'''

ANGULAR_UNSUBSCRIBED_OBSERVABLE = '''
export class UserComponent implements OnInit {
    ngOnInit() {
        this.userService.getUsers().subscribe(users => {
            this.users = users;
        });  // Memory leak: no unsubscribe
    }
}
'''
```


### Mocking Strategy

**External Services to Mock**:

1. **Azure DevOps API**: Mock PR data retrieval and comment publishing
2. **OpenAI/Azure OpenAI API**: Mock LLM responses for deterministic testing
3. **Redis**: Use fakeredis for unit tests, real Redis for integration tests
4. **MySQL**: Use in-memory SQLite for unit tests, real MySQL for integration tests

**Example Mock**:

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_azure_devops_client():
    """Mock Azure DevOps API client."""
    client = AsyncMock()
    
    # Mock PR metadata retrieval
    client.get_pull_request.return_value = PRMetadata(
        pr_id="12345",
        repository_id="repo-123",
        source_branch="feature/new-feature",
        target_branch="main",
        author="developer@example.com",
        title="Add new feature",
        source_commit_id="abc123",
        target_commit_id="def456"
    )
    
    # Mock file diff retrieval
    client.get_pull_request_changes.return_value = [
        FileChange(
            file_path="src/main/java/UserService.java",
            change_type=ChangeType.EDIT,
            added_lines=[LineChange(line_number=10, change_type=ChangeType.ADD, content="String name = user.getName();")],
            modified_lines=[],
            deleted_lines=[]
        )
    ]
    
    # Mock comment publishing
    client.create_thread.return_value = {"id": "thread-123"}
    
    return client
```


### Test Coverage Goals

**Coverage Targets**:
- Overall code coverage: 80%+
- Critical paths (agent workflow, error handling): 95%+
- Plugin interfaces: 90%+
- API endpoints: 100%

**Coverage Exclusions**:
- Configuration files
- Type definitions
- Logging statements (but test that logging occurs)

### Continuous Testing

**CI/CD Integration**:
- Run unit tests on every commit
- Run property tests on every PR
- Run integration tests on merge to main
- Generate coverage reports and fail if below threshold

**Test Execution Time Targets**:
- Unit tests: < 30 seconds total
- Property tests: < 2 minutes total (100 iterations per property)
- Integration tests: < 5 minutes total

### Language Plugin Testing

Each language plugin must have:

1. **Parser Tests**: Verify AST generation for valid code
2. **Context Extraction Tests**: Verify correct context extraction for various code structures
3. **Rule Tests**: Verify each analysis rule detects intended issues
4. **Pattern Detection Tests**: Verify design pattern identification
5. **Suggestion Formatting Tests**: Verify code suggestions are syntactically valid

**Example Plugin Test**:

```python
# Feature: azure-devops-pr-review-agent, Property 16: Language Plugin Selection
@given(
    file_ext=st.sampled_from(['.java', '.ts', '.component.ts', '.py', '.js'])
)
@pytest.mark.asyncio
async def test_plugin_selection_by_extension(file_ext: str):
    """Property 16: Correct plugin selected based on file extension."""
    # Arrange
    plugin_manager = PluginManager()
    await plugin_manager.initialize_plugins()
    file_path = f"test/file{file_ext}"
    
    # Act
    plugin = plugin_manager.get_plugin_for_file(file_path)
    
    # Assert
    if file_ext in ['.java']:
        assert plugin.language_name == "java"
    elif file_ext in ['.ts', '.component.ts']:
        assert plugin.language_name == "angular"
    elif file_ext in ['.py']:
        assert plugin.language_name == "python"
    else:
        assert plugin is None  # No plugin for unsupported extension
```

This comprehensive testing strategy ensures system correctness through both concrete examples (unit tests) and universal properties (property-based tests), while maintaining fast feedback cycles and high confidence in system behavior.

