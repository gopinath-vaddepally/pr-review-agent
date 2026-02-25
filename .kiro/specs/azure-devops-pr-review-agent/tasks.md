# Implementation Plan: Azure DevOps PR Review Agent

## Overview

This implementation plan breaks down the Azure DevOps PR Review Agent into discrete, implementable tasks. The system is a hackathon project with production-ready architecture using Python (FastAPI, LangGraph), MySQL, Redis, and Docker. The agent provides automated code review for Java and Angular codebases via Azure DevOps webhooks.

The implementation follows a bottom-up approach: infrastructure setup, data layer, core services, agent orchestration, analysis components, and finally integration. Each task builds on previous work to ensure incremental validation.

## Tasks

- [x] 1. Project setup and infrastructure foundation
  - Create project directory structure (app/, plugins/, tests/, docker/)
  - Set up Python virtual environment and requirements.txt with core dependencies (FastAPI, LangGraph, aiomysql, redis, tree-sitter, openai, azure-devops)
  - Create Docker Compose configuration for MySQL, Redis, FastAPI, and worker containers
  - Create Dockerfile for Python application with tree-sitter build steps
  - Set up environment variable configuration (.env.example with DATABASE_URL, REDIS_URL, AZURE_DEVOPS_PAT, OPENAI_API_KEY, WEBHOOK_SECRET)
  - _Requirements: 11.1, 11.4, 11.5, 11.6, 11.10_

- [ ] 2. Database schema and models
  - [x] 2.1 Create MySQL schema initialization script
    - Write init.sql with repositories, service_hooks, and agent_executions tables
    - Include indexes for performance (repository_url, pr_id, status, timestamps)
    - _Requirements: 1.1, 1.2, 10.1_
  
  - [x] 2.2 Implement Pydantic data models
    - Create models for Repository, PREvent, PRMetadata, FileChange, LineComment, SummaryComment, AgentState
    - Include validation rules and type constraints
    - _Requirements: 1.5, 2.2, 4.1, 5.6, 6.6_
  
  - [ ]* 2.3 Write property test for repository persistence
    - **Property 1: Repository Configuration Persistence**
    - **Validates: Requirements 1.1, 1.2**
  
  - [ ]* 2.4 Write unit tests for data model validation
    - Test Pydantic validation for invalid inputs
    - Test model serialization/deserialization
    - _Requirements: 1.5, 1.6_


- [ ] 3. Repository configuration service
  - [x] 3.1 Implement MySQL connection and repository CRUD operations
    - Create RepositoryConfigService with add_repository, remove_repository, list_repositories, is_monitored methods
    - Use aiomysql for async database operations
    - Implement repository URL validation (Azure DevOps format)
    - _Requirements: 1.1, 1.2, 1.5, 1.6_
  
  - [ ]* 3.2 Write property test for repository URL validation
    - **Property 2: Repository URL Validation**
    - **Validates: Requirements 1.5, 1.6**
  
  - [ ]* 3.3 Write unit tests for repository service
    - Test CRUD operations with in-memory SQLite
    - Test URL validation edge cases (malformed URLs, missing components)
    - _Requirements: 1.5, 1.6_

- [ ] 4. Redis state management and job queue
  - [x] 4.1 Implement Redis client wrapper
    - Create RedisClient with connection pooling and retry logic
    - Implement methods for agent state storage (hash operations)
    - Implement job queue operations (list push/pop)
    - Implement agent tracking set operations
    - _Requirements: 3.1, 3.3, 3.5, 11.5_
  
  - [ ]* 4.2 Write property test for agent state persistence
    - **Property 6: Agent State Persistence Round-Trip**
    - **Validates: Requirements 3.3**
  
  - [ ]* 4.3 Write unit tests for Redis operations
    - Test state serialization/deserialization
    - Test queue operations (enqueue, dequeue, empty queue)
    - Use fakeredis for unit tests
    - _Requirements: 3.1, 3.3_

- [ ] 5. Azure DevOps integration layer
  - [x] 5.1 Implement Code Retriever component
    - Create CodeRetriever class using Azure DevOps Python SDK
    - Implement get_pr_diff to retrieve file changes with line-level diffs
    - Implement get_file_content for source and target branches
    - Implement get_pr_metadata for PR details
    - Add retry logic with exponential backoff for API calls
    - _Requirements: 2.2, 2.4, 4.1, 4.2, 4.3, 9.1_
  
  - [ ]* 5.2 Write property test for PR metadata completeness
    - **Property 3: PR Metadata Completeness**
    - **Validates: Requirements 2.2, 4.1, 4.2, 4.3**
  
  - [ ]* 5.3 Write unit tests for Code Retriever
    - Test with mocked Azure DevOps API responses
    - Test retry logic on transient failures
    - Test error handling for invalid PR IDs
    - _Requirements: 4.4, 9.1_

- [x] 6. Checkpoint - Verify infrastructure and data layer
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 7. Language plugin architecture foundation
  - [x] 7.1 Create plugin interface and manager
    - Define LanguagePlugin abstract base class with parse_file, extract_context, get_analysis_rules, format_suggestion, detect_patterns methods
    - Implement PluginManager with plugin registration and file extension mapping
    - Create plugin configuration loader (YAML-based)
    - _Requirements: 7.1, 11.7_
  
  - [x] 7.2 Build tree-sitter grammars
    - Create build_grammars.py script to compile tree-sitter-java and tree-sitter-typescript
    - Generate language.so shared library
    - _Requirements: 5.1, 11.7_
  
  - [ ]* 7.3 Write property test for plugin selection
    - **Property 16: Language Plugin Selection**
    - **Validates: Requirements 7.1**
  
  - [ ]* 7.4 Write unit tests for plugin manager
    - Test plugin registration and discovery
    - Test file extension to plugin mapping
    - _Requirements: 7.1_

- [ ] 8. Java language plugin
  - [x] 8.1 Implement Java plugin core functionality
    - Create JavaPlugin class implementing LanguagePlugin interface
    - Implement parse_file using tree-sitter-java
    - Implement extract_context to find enclosing class, method, and imports
    - Create plugins/java/config.yaml with analysis rules
    - _Requirements: 5.1, 7.1_
  
  - [x] 8.2 Implement Java analysis rules
    - Define rules for null pointer detection, resource leaks, exception handling, naming conventions
    - Create LLM prompt templates for each rule category
    - _Requirements: 5.3, 5.4, 5.5, 7.2, 7.3, 7.4_
  
  - [x] 8.3 Implement Java pattern detection
    - Add detect_patterns method to identify Singleton, Factory, Builder patterns
    - _Requirements: 6.3, 6.4_
  
  - [ ]* 8.4 Write unit tests for Java plugin
    - Test AST parsing for valid Java code
    - Test context extraction for classes, methods, imports
    - Test pattern detection with known examples
    - _Requirements: 5.1, 6.3_

- [ ] 9. Angular language plugin
  - [x] 9.1 Implement Angular plugin core functionality
    - Create AngularPlugin class implementing LanguagePlugin interface
    - Implement parse_file using tree-sitter-typescript
    - Implement extract_context to find decorators, components, services
    - Create plugins/angular/config.yaml with analysis rules
    - _Requirements: 5.1, 7.1_
  
  - [x] 9.2 Implement Angular analysis rules
    - Define rules for Observable unsubscribe, change detection, dependency injection, RxJS best practices
    - Create LLM prompt templates for Angular-specific patterns
    - _Requirements: 5.3, 7.2, 7.3, 7.4_
  
  - [x] 9.3 Implement Angular pattern detection
    - Add detect_patterns method to identify Service, Component, Directive patterns
    - _Requirements: 6.3, 6.4_
  
  - [ ]* 9.4 Write unit tests for Angular plugin
    - Test TypeScript AST parsing
    - Test decorator extraction
    - Test pattern detection for Angular components and services
    - _Requirements: 5.1, 6.3_


- [ ] 10. Code Analyzer component
  - [x] 10.1 Implement Code Analyzer core
    - Create CodeAnalyzer class with analyze_file, parse_file, analyze_line methods
    - Integrate with PluginManager for language-specific analysis
    - Implement LLM client wrapper for OpenAI/Azure OpenAI API
    - Add batching logic for efficient LLM API calls
    - _Requirements: 5.1, 5.2, 7.1, 11.8_
  
  - [x] 10.2 Implement line-level analysis workflow
    - For each modified/added line, extract context via plugin
    - Send line + context to LLM with language-specific rules
    - Parse LLM response into LineComment objects
    - Handle LLM API failures gracefully (continue with other lines)
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  
  - [ ]* 10.3 Write property test for modified lines coverage
    - **Property 11: Modified Lines Analysis Coverage**
    - **Validates: Requirements 5.2**
  
  - [ ]* 10.4 Write property test for comment generation completeness
    - **Property 12: Comment Generation Completeness**
    - **Validates: Requirements 5.6, 5.7, 8.3**
  
  - [ ]* 10.5 Write unit tests for Code Analyzer
    - Test with mocked LLM responses for known code issues
    - Test error handling when LLM API fails
    - Test batching logic
    - _Requirements: 5.2, 5.6, 9.4_

- [ ] 11. Architecture Analyzer component
  - [x] 11.1 Implement Architecture Analyzer
    - Create ArchitectureAnalyzer class with analyze_architecture, evaluate_solid_principles, identify_design_patterns, detect_architectural_issues methods
    - Implement LLM-based analysis for SOLID principles (SRP, OCP, LSP, ISP, DIP)
    - Implement design pattern identification (creational, structural, behavioral)
    - Implement architectural issue detection (layering violations, circular dependencies)
    - Generate SummaryComment with findings and recommendations
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 11.9_
  
  - [ ]* 11.2 Write property test for architectural analysis input completeness
    - **Property 13: Architectural Analysis Input Completeness**
    - **Validates: Requirements 6.1**
  
  - [ ]* 11.3 Write property test for architectural summary generation
    - **Property 14: Architectural Summary Generation**
    - **Validates: Requirements 6.6**
  
  - [ ]* 11.4 Write unit tests for Architecture Analyzer
    - Test SOLID principle evaluation with known violations
    - Test design pattern identification with example code
    - Test with mocked LLM responses
    - _Requirements: 6.2, 6.3, 6.4, 6.5_

- [x] 12. Checkpoint - Verify analysis components
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 13. Comment Publisher component
  - [x] 13.1 Implement Comment Publisher
    - Create CommentPublisher class with publish_line_comments, publish_summary_comment, batch_publish methods
    - Use Azure DevOps Python SDK to post comments via REST API
    - Associate line comments with correct file path, line number, and commit ID
    - Implement batching for efficient API usage
    - Add retry logic with exponential backoff (3 retries)
    - Handle API rate limiting gracefully
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 11.3_
  
  - [ ]* 13.2 Write property test for comment publishing completeness
    - **Property 17: Comment Publishing Completeness**
    - **Validates: Requirements 8.1**
  
  - [ ]* 13.3 Write property test for retry with exponential backoff
    - **Property 18: Retry with Exponential Backoff**
    - **Validates: Requirements 8.4, 9.1**
  
  - [ ]* 13.4 Write unit tests for Comment Publisher
    - Test with mocked Azure DevOps API
    - Test retry logic on transient failures
    - Test batching behavior
    - Test error logging on permanent failures
    - _Requirements: 8.4, 8.5_

- [ ] 14. LangGraph Review Agent workflow
  - [x] 14.1 Define Review Agent state graph
    - Create ReviewAgentState TypedDict with all required fields
    - Define LangGraph nodes: initialize_node, retrieve_code_node, parse_files_node, line_analysis_node, architecture_analysis_node, generate_comments_node, publish_comments_node, handle_error_node
    - Define state transitions and conditional edges
    - _Requirements: 3.2, 11.2_
  
  - [x] 14.2 Implement Review Agent node functions
    - Implement initialize_node to load PR metadata
    - Implement retrieve_code_node using CodeRetriever
    - Implement parse_files_node using language plugins
    - Implement line_analysis_node using CodeAnalyzer
    - Implement architecture_analysis_node using ArchitectureAnalyzer
    - Implement generate_comments_node to format results
    - Implement publish_comments_node using CommentPublisher
    - Implement handle_error_node for error recovery
    - Add state persistence to Redis after each node
    - _Requirements: 3.3, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 6.1, 8.1_
  
  - [x] 14.3 Implement error handling and resilience
    - Continue execution when individual file analysis fails
    - Aggregate errors in state for final reporting
    - Implement timeout awareness (check elapsed time)
    - _Requirements: 9.2, 9.3, 9.4_
  
  - [ ]* 14.4 Write property test for agent-to-PR association
    - **Property 5: Agent-to-PR One-to-One Association**
    - **Validates: Requirements 3.2**
  
  - [ ]* 14.5 Write property test for analysis resilience
    - **Property 9: Analysis Resilience to File Failures**
    - **Validates: Requirements 4.4, 9.4**
  
  - [ ]* 14.6 Write integration tests for agent workflow
    - Test complete workflow from PR event to comment publishing
    - Test state persistence across node transitions
    - Test error recovery scenarios
    - _Requirements: 3.3, 9.4_


- [ ] 15. Agent Orchestrator
  - [x] 15.1 Implement Agent Orchestrator
    - Create AgentOrchestrator class with spawn_agent, monitor_agent, terminate_agent, get_agent_state methods
    - Generate unique agent IDs for each PR
    - Initialize LangGraph state graph with PR context
    - Store agent metadata in Redis
    - Implement agent timeout monitoring (10-minute timeout)
    - Clean up resources on agent completion or timeout
    - _Requirements: 3.2, 3.3, 3.4, 9.3_
  
  - [ ]* 15.2 Write property test for agent resource cleanup
    - **Property 7: Agent Resource Cleanup**
    - **Validates: Requirements 3.4**
  
  - [ ]* 15.3 Write property test for agent timeout enforcement
    - **Property 20: Agent Timeout Enforcement**
    - **Validates: Requirements 9.3**
  
  - [ ]* 15.4 Write unit tests for Agent Orchestrator
    - Test agent spawning and ID generation
    - Test timeout monitoring and termination
    - Test resource cleanup
    - _Requirements: 3.4, 9.3_

- [ ] 16. PR Monitor and Service Hook management
  - [x] 16.1 Implement PR Monitor
    - Create PRMonitor class with process_pr_event, register_service_hook, unregister_service_hook, check_existing_agent, terminate_agent methods
    - Validate PR belongs to monitored repository
    - Check for existing agent instances in Redis
    - Terminate stale agents before spawning new ones
    - Enqueue review job to Redis job queue
    - Implement retry logic with exponential backoff for Azure DevOps API
    - _Requirements: 2.1, 3.1, 3.5, 3.6, 9.1_
  
  - [x] 16.2 Implement Service Hook registration
    - Use Azure DevOps SDK to register/unregister Service Hooks
    - Store service hook IDs in MySQL
    - Trigger registration when repository is added
    - Trigger unregistration when repository is removed
    - _Requirements: 1.3, 1.4, 11.12_
  
  - [ ]* 16.3 Write property test for PR event to job queue mapping
    - **Property 4: PR Event to Job Queue Mapping**
    - **Validates: Requirements 3.1**
  
  - [ ]* 16.4 Write property test for single active agent per PR
    - **Property 8: Single Active Agent Per PR**
    - **Validates: Requirements 3.5, 3.6**
  
  - [ ]* 16.5 Write unit tests for PR Monitor
    - Test event validation and processing
    - Test duplicate agent detection and termination
    - Test service hook registration/unregistration
    - _Requirements: 3.5, 3.6, 1.3, 1.4_

- [x] 17. Checkpoint - Verify agent orchestration
  - Ensure all tests pass, ask the user if questions arise.


- [x] 18. FastAPI webhook handler and REST API
  - [x] 18.1 Implement webhook endpoint
    - Create FastAPI application with /webhooks/azure-devops/pr POST endpoint
    - Validate webhook signature for security
    - Parse PR event payload into PREvent model
    - Return 200 OK immediately (async processing)
    - Enqueue event to Redis job queue via PRMonitor
    - _Requirements: 2.1, 11.1, 11.12_
  
  - [x] 18.2 Implement admin REST API endpoints
    - Create POST /api/repositories endpoint to add repository
    - Create DELETE /api/repositories/{repo_id} endpoint to remove repository
    - Create GET /api/repositories endpoint to list repositories
    - Create GET /api/agents endpoint to list active agents
    - Create GET /api/agents/{agent_id} endpoint to get agent status
    - Add request validation and error handling
    - _Requirements: 1.1, 1.2_
  
  - [x] 18.3 Add CORS and security middleware
    - Configure CORS for Angular frontend
    - Add authentication middleware for admin endpoints
    - Add request logging middleware
    - _Requirements: 2.4_
  
  - [ ]* 18.4 Write unit tests for API endpoints
    - Test webhook endpoint with valid and invalid payloads
    - Test admin endpoints with mocked services
    - Test authentication and authorization
    - _Requirements: 2.1, 1.1, 1.2_

- [x] 19. Worker process for job queue
  - [x] 19.1 Implement worker process
    - Create worker.py that polls Redis job queue
    - Dequeue PR events and spawn Review Agents via AgentOrchestrator
    - Handle multiple workers for parallel processing
    - Implement graceful shutdown on SIGTERM
    - _Requirements: 3.1, 11.2_
  
  - [ ]* 19.2 Write integration tests for worker
    - Test job dequeuing and agent spawning
    - Test parallel processing with multiple workers
    - _Requirements: 3.1_

- [x] 20. Logging and observability
  - [x] 20.1 Implement structured logging
    - Configure Python logging with JSON formatter
    - Add log context (agent_id, pr_id, phase) to all log entries
    - Log PR event detections with timestamp and repository ID
    - Log agent phase transitions (start and completion)
    - Log all Azure DevOps API calls with request/response status
    - Log all errors with stack traces and context
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_
  
  - [x] 20.2 Implement metrics emission
    - Emit metrics for agent execution time
    - Emit metrics for number of comments generated
    - Emit metrics for API call latency
    - Store metrics in agent_executions table
    - _Requirements: 10.5_
  
  - [ ]* 20.3 Write property tests for logging completeness
    - **Property 19: Error Logging Completeness**
    - **Property 21: Event Logging with Required Fields**
    - **Property 22: Phase Transition Logging**
    - **Property 23: API Call Logging**
    - **Property 25: Structured Log Format**
    - **Validates: Requirements 9.2, 9.5, 10.1, 10.2, 10.3, 10.4, 10.6**
  
  - [ ]* 20.4 Write unit tests for logging
    - Test log entry creation for various events
    - Test log format and required fields
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_


- [x] 21. Error handling and resilience patterns
  - [x] 21.1 Implement retry with exponential backoff utility
    - Create retry_with_backoff decorator for transient errors
    - Configure max retries, base delay, and max delay
    - Apply to Azure DevOps API calls and Redis operations
    - _Requirements: 9.1, 8.4_
  
  - [x] 21.2 Implement circuit breaker pattern
    - Create CircuitBreaker class for external service calls
    - Configure failure threshold and timeout
    - Apply to Azure DevOps API and LLM API calls
    - _Requirements: 9.1_
  
  - [x] 21.3 Implement error recovery and state management
    - Persist agent state to Redis after each phase
    - Handle partial failures (continue with available data)
    - Log errors with full context
    - _Requirements: 9.2, 9.4, 9.5_
  
  - [ ]* 21.4 Write unit tests for error handling
    - Test retry logic with transient failures
    - Test circuit breaker state transitions
    - Test partial failure scenarios
    - _Requirements: 9.1, 9.2, 9.4_

- [x] 22. Docker containerization and deployment
  - [x] 22.1 Create production Dockerfile
    - Base on python:3.11-slim
    - Install system dependencies for tree-sitter
    - Copy and install Python requirements
    - Build tree-sitter grammars
    - Copy application code and plugins
    - Configure uvicorn for production
    - _Requirements: 11.10_
  
  - [x] 22.2 Create Docker Compose configuration
    - Define services: api, worker (3 replicas), mysql, redis, frontend (optional)
    - Configure environment variables and secrets
    - Set up volumes for data persistence
    - Configure networking and port mappings
    - Add health checks for all services
    - _Requirements: 11.4, 11.5, 11.6, 11.10_
  
  - [x] 22.3 Create deployment documentation
    - Document environment variable configuration
    - Document Azure DevOps PAT setup
    - Document OpenAI API key setup
    - Document webhook URL configuration
    - _Requirements: 2.4, 8.6_

- [x] 23. Checkpoint - Verify deployment configuration
  - Ensure all tests pass, ask the user if questions arise.


- [ ] 24. Integration testing and end-to-end validation
  - [ ]* 24.1 Write integration test for complete workflow
    - Test webhook → PR Monitor → Agent Orchestrator → Review Agent → Comment Publisher flow
    - Use mocked Azure DevOps API and real Redis/MySQL (test containers)
    - Verify comments are generated and published
    - _Requirements: 2.1, 3.1, 3.2, 4.1, 5.1, 6.1, 8.1_
  
  - [ ]* 24.2 Write integration test for Azure DevOps API
    - Test real API calls in staging environment (if available)
    - Test PR metadata retrieval, file diff retrieval, comment publishing
    - _Requirements: 2.2, 4.1, 8.1_
  
  - [ ]* 24.3 Write integration test for Redis state management
    - Test agent state persistence across operations
    - Test job queue operations with multiple workers
    - _Requirements: 3.3, 3.1_
  
  - [ ]* 24.4 Write integration test for MySQL operations
    - Test repository CRUD operations with real MySQL
    - Test transaction handling and rollback
    - _Requirements: 1.1, 1.2_

- [ ] 25. Angular admin UI (optional for hackathon)
  - [ ]* 25.1 Create Angular project structure
    - Generate Angular application with CLI
    - Set up routing and core modules
    - Configure API service for backend communication
    - _Requirements: 11.11_
  
  - [ ]* 25.2 Implement repository management UI
    - Create repository list component
    - Create add repository form
    - Create delete repository confirmation
    - _Requirements: 1.1, 1.2_
  
  - [ ]* 25.3 Implement agent monitoring UI
    - Create active agents list component
    - Create agent detail view with status and logs
    - Add real-time updates (polling or WebSocket)
    - _Requirements: 3.2, 10.1, 10.2_
  
  - [ ]* 25.4 Create Dockerfile for Angular frontend
    - Multi-stage build with Node.js and Nginx
    - Configure Nginx to serve static files and proxy API
    - _Requirements: 11.11_

- [x] 26. Final integration and system testing
  - [x] 26.1 Deploy complete system with Docker Compose
    - Start all services (api, worker, mysql, redis)
    - Verify service health checks
    - Test connectivity between services
    - _Requirements: 11.10_
  
  - [x] 26.2 Configure Azure DevOps Service Hook
    - Register webhook URL in Azure DevOps project
    - Test webhook delivery with test PR
    - Verify PR event is received and processed
    - _Requirements: 1.3, 2.1, 11.12_
  
  - [x] 26.3 End-to-end validation with real PR
    - Create test PR in monitored repository
    - Verify agent is spawned and completes analysis
    - Verify comments appear in Azure DevOps PR
    - Verify logging and metrics are captured
    - _Requirements: 2.1, 3.1, 3.2, 5.1, 6.1, 8.1, 10.1, 10.5_
  
  - [x] 26.4 Performance and load testing
    - Test with multiple concurrent PRs
    - Verify worker scaling and job distribution
    - Monitor resource usage (CPU, memory, API rate limits)
    - _Requirements: 3.1, 9.3_

- [x] 27. Final checkpoint - System ready for hackathon demo
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical milestones
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples, edge cases, and error conditions
- Integration tests validate component interactions and end-to-end workflows
- The implementation follows a bottom-up approach: infrastructure → data layer → services → orchestration → integration
- For hackathon timeline, prioritize core functionality (tasks 1-23) and defer optional UI (task 25) if time is limited
- Docker Compose enables local development and testing before production deployment
- Multiple worker replicas enable parallel PR processing for scalability

