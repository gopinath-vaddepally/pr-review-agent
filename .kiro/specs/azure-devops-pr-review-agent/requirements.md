# Requirements Document

## Introduction

The Azure DevOps PR Review Agent System is an automated code review system that analyzes pull requests in Azure DevOps repositories. The system monitors configured repositories, spawns dedicated agent instances for each pull request, and provides both line-level code quality feedback and holistic architectural analysis based on SOLID principles and design patterns.

## Technology Stack

This is a hackathon project with plans for future standalone production deployment. While the organization standardizes on Java/Spring Boot and Angular, this project uses Python for superior AI/LLM integration capabilities.

### Backend Stack
- **FastAPI**: Async web framework for webhooks and REST API endpoints
- **LangGraph**: Multi-agent orchestration framework for autonomous agent workflows
- **Azure DevOps Python SDK**: Official SDK for Azure DevOps PR APIs
- **MySQL**: Repository configuration persistence
- **Redis**: Agent state management and job queue
- **Docker**: Containerization for deployment

### AI/Agent Layer
- **LangGraph**: Agent workflow orchestration with state graphs
- **OpenAI API or Azure OpenAI**: LLM for code analysis and review generation
- **AST parsers (tree-sitter)**: Code structure analysis

### Frontend
- **Angular**: Organization standard frontend framework

### Integration
- **Azure DevOps Service Hooks**: Real-time PR webhooks (no polling)
- **Azure DevOps REST API**: PR comments, file diffs, and metadata

### Key Architectural Decisions
1. Python chosen over Java/Spring Boot for superior AI/LLM ecosystem (LangChain, LangGraph)
2. FastAPI provides async performance comparable to Spring Boot for I/O-bound workloads
3. Real-time webhook integration (not polling) for immediate PR detection
4. Each PR gets dedicated agent instance using LangGraph state management
5. Microservices architecture allows future migration to Java if needed

## Glossary

- **PR_Monitor**: The FastAPI webhook handler that receives Azure DevOps Service Hook notifications for new pull requests
- **Review_Agent**: A LangGraph-orchestrated autonomous agent instance that analyzes a single pull request
- **Repository_Configuration**: A MySQL-backed persistent store of repository identifiers to monitor
- **Code_Analyzer**: The component that examines code changes using AST parsers and LLM analysis
- **Comment_Publisher**: The component that posts review comments via Azure DevOps REST API
- **Architecture_Analyzer**: The LLM-powered component that evaluates overall design and patterns
- **Azure_DevOps_API**: The external Azure DevOps REST API interface accessed via Azure DevOps Python SDK
- **PR_Event**: A webhook notification from Azure DevOps Service Hooks that a pull request has been created or updated
- **Line_Comment**: A review comment attached to a specific line of code
- **Summary_Comment**: A review comment describing overall architectural observations
- **Agent_State**: Redis-backed state management for tracking Review_Agent execution progress
- **Job_Queue**: Redis-backed queue for managing Review_Agent task distribution

## Requirements

### Requirement 1: Repository Configuration Management

**User Story:** As a development team lead, I want to configure which repositories should be monitored for pull requests, so that the review agent only analyzes relevant codebases.

#### Acceptance Criteria

1. THE Repository_Configuration SHALL store a list of Azure DevOps repository identifiers in MySQL
2. THE Repository_Configuration SHALL persist configuration across system restarts
3. WHEN a repository is added to the configuration, THE PR_Monitor SHALL register an Azure DevOps Service Hook for that repository within 60 seconds
4. WHEN a repository is removed from the configuration, THE PR_Monitor SHALL unregister the Azure DevOps Service Hook for that repository within 60 seconds
5. THE Repository_Configuration SHALL validate that repository identifiers are well-formed Azure DevOps repository URLs
6. WHEN an invalid repository identifier is provided, THE Repository_Configuration SHALL return a descriptive error message

### Requirement 2: Pull Request Detection

**User Story:** As a developer, I want the system to automatically detect when I submit a pull request, so that I receive timely code review feedback.

#### Acceptance Criteria

1. WHEN a PR_Event webhook is received by the FastAPI endpoint, THE PR_Monitor SHALL process the event within 5 seconds
2. THE PR_Monitor SHALL retrieve pull request metadata including branch names, changed files, and author information using Azure DevOps Python SDK
3. WHEN a pull request is updated with new commits, THE Azure DevOps Service Hook SHALL trigger a webhook to the PR_Monitor within 30 seconds
4. THE PR_Monitor SHALL authenticate with Azure_DevOps_API using secure credentials

### Requirement 3: Review Agent Instantiation

**User Story:** As a system administrator, I want each pull request to have its own dedicated review agent, so that reviews run in isolation without interference.

#### Acceptance Criteria

1. WHEN a PR_Event is detected, THE PR_Monitor SHALL enqueue a review job in the Redis Job_Queue
2. THE Review_Agent SHALL be instantiated as a LangGraph state graph associated with exactly one pull request identifier
3. THE Review_Agent SHALL store its execution state in Redis Agent_State for resumability
4. WHEN a Review_Agent completes its analysis, THE Review_Agent SHALL terminate and release resources
5. THE PR_Monitor SHALL track active Review_Agent instances in Redis to prevent duplicate agents for the same pull request
6. IF a Review_Agent already exists for a pull request, THEN THE PR_Monitor SHALL terminate the existing agent before spawning a new one

### Requirement 4: Code Change Retrieval

**User Story:** As a review agent, I want to retrieve all file changes in a pull request, so that I can analyze the code modifications.

#### Acceptance Criteria

1. THE Review_Agent SHALL retrieve the complete diff of all changed files using Azure DevOps Python SDK
2. THE Review_Agent SHALL identify added lines, modified lines, and deleted lines for each file
3. THE Review_Agent SHALL retrieve file content from both source and target branches
4. WHEN file retrieval fails, THE Review_Agent SHALL log the error and continue with available files

### Requirement 5: Line-Level Code Analysis

**User Story:** As a developer, I want the agent to identify problematic code statements, so that I can fix issues before merging.

#### Acceptance Criteria

1. THE Code_Analyzer SHALL parse each modified file using tree-sitter AST parser
2. THE Code_Analyzer SHALL examine each modified line of code for quality issues using LLM analysis
3. THE Code_Analyzer SHALL detect common code smells including long methods, deep nesting, and duplicated code
4. THE Code_Analyzer SHALL detect potential bugs including null pointer risks, resource leaks, and boundary condition errors
5. THE Code_Analyzer SHALL detect security vulnerabilities including injection risks and insecure data handling
6. WHEN a problematic statement is identified, THE Code_Analyzer SHALL generate a Line_Comment with the issue description and suggested fix
7. THE Code_Analyzer SHALL associate each Line_Comment with the specific file path and line number

### Requirement 6: Architectural Analysis

**User Story:** As a software architect, I want the agent to evaluate the overall design of the pull request, so that I can ensure architectural consistency.

#### Acceptance Criteria

1. THE Architecture_Analyzer SHALL examine all changed files as a cohesive unit using LLM analysis
2. THE Architecture_Analyzer SHALL evaluate adherence to SOLID principles including Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion
3. THE Architecture_Analyzer SHALL identify applicable design patterns including creational, structural, and behavioral patterns
4. THE Architecture_Analyzer SHALL detect violations of design patterns already in use in the codebase
5. THE Architecture_Analyzer SHALL detect architectural inconsistencies including layering violations and circular dependencies
6. WHEN architectural issues are identified, THE Architecture_Analyzer SHALL generate a Summary_Comment describing the concerns and recommendations
7. WHEN design patterns could improve the code, THE Architecture_Analyzer SHALL suggest specific patterns with justification

### Requirement 7: Best Practices Evaluation

**User Story:** As a developer, I want the agent to suggest coding best practices, so that I can improve code quality and maintainability.

#### Acceptance Criteria

1. THE Code_Analyzer SHALL evaluate code against language-specific best practices
2. THE Code_Analyzer SHALL check naming conventions for classes, methods, and variables
3. THE Code_Analyzer SHALL evaluate code documentation and comment quality
4. THE Code_Analyzer SHALL check error handling patterns
5. THE Code_Analyzer SHALL evaluate test coverage for changed code
6. WHEN best practice violations are found, THE Code_Analyzer SHALL generate comments with specific improvement suggestions

### Requirement 8: Comment Publishing

**User Story:** As a developer, I want review comments to appear in my pull request, so that I can see feedback directly in Azure DevOps.

#### Acceptance Criteria

1. WHEN analysis is complete, THE Comment_Publisher SHALL post all Line_Comment instances using Azure DevOps Python SDK
2. THE Comment_Publisher SHALL post the Summary_Comment to the pull request overview
3. THE Comment_Publisher SHALL associate Line_Comment instances with the correct file path, line number, and commit identifier
4. WHEN comment publishing fails, THE Comment_Publisher SHALL retry up to 3 times with exponential backoff
5. WHEN comment publishing fails after all retries, THE Comment_Publisher SHALL log the error with full context
6. THE Comment_Publisher SHALL authenticate with Azure_DevOps_API using secure credentials

### Requirement 9: Error Handling and Resilience

**User Story:** As a system administrator, I want the system to handle errors gracefully, so that one failure doesn't break the entire review process.

#### Acceptance Criteria

1. WHEN Azure_DevOps_API is unavailable, THE PR_Monitor SHALL retry connection attempts with exponential backoff up to 5 minutes
2. IF a Review_Agent crashes, THEN THE PR_Monitor SHALL log the error and clean up resources
3. WHEN a Review_Agent exceeds 10 minutes of execution time, THE PR_Monitor SHALL terminate the agent and log a timeout error
4. THE Review_Agent SHALL continue analysis even when individual file analysis fails
5. WHEN authentication fails, THE System SHALL log the error with sufficient detail for troubleshooting

### Requirement 10: Logging and Observability

**User Story:** As a system administrator, I want comprehensive logging of agent activities, so that I can troubleshoot issues and monitor system health.

#### Acceptance Criteria

1. THE PR_Monitor SHALL log all PR_Event detections with timestamp and repository identifier
2. THE Review_Agent SHALL log the start and completion of each analysis phase
3. THE System SHALL log all API calls to Azure_DevOps_API including request and response status
4. THE System SHALL log all errors with stack traces and contextual information
5. THE System SHALL emit metrics including agent execution time, number of comments generated, and API call latency
6. THE System SHALL structure logs in a machine-readable format for automated analysis

### Requirement 11: Technology Stack Compliance

**User Story:** As a system architect, I want the system to use the specified technology stack, so that we leverage the best tools for AI/LLM integration while maintaining organizational standards where appropriate.

#### Acceptance Criteria

1. THE System SHALL implement the webhook endpoint using FastAPI framework
2. THE Review_Agent SHALL be orchestrated using LangGraph state graph framework
3. THE System SHALL use Azure DevOps Python SDK for all Azure DevOps API interactions
4. THE Repository_Configuration SHALL persist data in MySQL database
5. THE Agent_State SHALL store agent execution state in Redis
6. THE Job_Queue SHALL use Redis for job queue management
7. THE Code_Analyzer SHALL use tree-sitter for AST parsing
8. THE Code_Analyzer SHALL use OpenAI API or Azure OpenAI for LLM-based code analysis
9. THE Architecture_Analyzer SHALL use OpenAI API or Azure OpenAI for architectural evaluation
10. THE System SHALL be containerized using Docker
11. WHERE a frontend interface is provided, THE System SHALL implement it using Angular framework
12. THE PR_Monitor SHALL receive PR notifications via Azure DevOps Service Hooks webhooks
13. THE System SHALL NOT use polling mechanisms for PR detection
