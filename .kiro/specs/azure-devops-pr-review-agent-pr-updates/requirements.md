# Requirements Document

## Introduction

This document specifies requirements for enhancing the Azure DevOps PR Review Agent to handle pull request updates. The current system successfully reviews newly created PRs by handling `git.pullrequest.created` webhook events. This enhancement adds support for `git.pullrequest.updated` events, enabling the system to review only the newly added changes when developers push additional commits to an existing PR.

The enhancement focuses on incremental review capabilities: detecting PR updates, comparing iterations to identify new changes, and posting comments only on the new code to avoid duplicate feedback on previously reviewed code.

## Glossary

- **PR_Update_Event**: A webhook notification from Azure DevOps Service Hooks triggered when a pull request is updated with new commits
- **PR_Iteration**: A snapshot of a pull request at a specific point in time, created each time new commits are pushed
- **Iteration_Comparator**: The component that compares two PR iterations to identify newly added changes
- **Change_Delta**: The set of file changes that exist in a newer iteration but not in a previous iteration
- **Incremental_Review**: A review process that analyzes only the newly added changes since the last review
- **Last_Reviewed_Iteration**: The most recent PR iteration that was analyzed by the Review_Agent
- **Iteration_Metadata**: Information about a PR iteration including iteration ID, commit IDs, and timestamp
- **PR_Monitor**: The FastAPI webhook handler that receives Azure DevOps Service Hook notifications (existing component)
- **Review_Agent**: A LangGraph-orchestrated autonomous agent instance that analyzes pull request changes (existing component)
- **Code_Analyzer**: The component that examines code changes using AST parsers and LLM analysis (existing component)
- **Comment_Publisher**: The component that posts review comments via Azure DevOps REST API (existing component)

## Requirements

### Requirement 1: PR Update Event Detection

**User Story:** As a developer, I want the system to automatically detect when I push new commits to an existing pull request, so that I receive review feedback on my latest changes.

#### Acceptance Criteria

1. THE PR_Monitor SHALL register to receive `git.pullrequest.updated` webhook events from Azure DevOps Service Hooks
2. WHEN a PR_Update_Event webhook is received, THE PR_Monitor SHALL process the event within 5 seconds
3. THE PR_Monitor SHALL extract the pull request ID, repository ID, and iteration information from the webhook payload
4. THE PR_Monitor SHALL distinguish between PR_Update_Event and `git.pullrequest.created` events
5. WHEN a PR_Update_Event is received for a non-existent pull request, THE PR_Monitor SHALL log a warning and skip processing

### Requirement 2: PR Iteration Retrieval

**User Story:** As a review agent, I want to retrieve iteration information for a pull request, so that I can identify what has changed since the last review.

#### Acceptance Criteria

1. THE Review_Agent SHALL retrieve all PR iterations using Azure DevOps Python SDK
2. THE Review_Agent SHALL extract Iteration_Metadata including iteration ID, commit IDs, and creation timestamp for each iteration
3. THE Review_Agent SHALL identify the current iteration from the PR_Update_Event
4. THE Review_Agent SHALL retrieve the Last_Reviewed_Iteration from persistent storage
5. WHEN no Last_Reviewed_Iteration exists, THE Review_Agent SHALL treat the current iteration as a new PR and review all changes
6. THE Review_Agent SHALL store the current iteration ID as the Last_Reviewed_Iteration after completing the review

### Requirement 3: Iteration Comparison

**User Story:** As a review agent, I want to compare two PR iterations, so that I can identify only the newly added changes.

#### Acceptance Criteria

1. THE Iteration_Comparator SHALL retrieve file changes for both the Last_Reviewed_Iteration and the current iteration
2. THE Iteration_Comparator SHALL identify files that were added in the current iteration
3. THE Iteration_Comparator SHALL identify files that were modified between iterations
4. THE Iteration_Comparator SHALL identify specific line ranges that changed in modified files
5. THE Iteration_Comparator SHALL produce a Change_Delta containing only the new or modified content
6. THE Iteration_Comparator SHALL exclude files that were deleted in the current iteration from the Change_Delta
7. THE Iteration_Comparator SHALL exclude unchanged files from the Change_Delta

### Requirement 4: Incremental Code Analysis

**User Story:** As a developer, I want the agent to review only my new changes, so that I don't receive duplicate comments on code that was already reviewed.

#### Acceptance Criteria

1. THE Code_Analyzer SHALL analyze only files included in the Change_Delta
2. THE Code_Analyzer SHALL analyze only line ranges included in the Change_Delta for modified files
3. THE Code_Analyzer SHALL skip analysis of unchanged code sections
4. WHEN a file is completely new, THE Code_Analyzer SHALL analyze the entire file
5. WHEN a file has partial changes, THE Code_Analyzer SHALL analyze only the changed line ranges with surrounding context

### Requirement 5: Comment Deduplication

**User Story:** As a developer, I want to avoid receiving duplicate review comments on the same code, so that I can focus on new feedback.

#### Acceptance Criteria

1. THE Comment_Publisher SHALL retrieve existing comment threads from the pull request before posting new comments
2. THE Comment_Publisher SHALL compare new comments against existing comments by file path and line number
3. WHEN a comment already exists for a specific file and line, THE Comment_Publisher SHALL skip posting the duplicate comment
4. THE Comment_Publisher SHALL post comments only for lines included in the Change_Delta
5. THE Comment_Publisher SHALL log skipped duplicate comments for observability

### Requirement 6: Iteration State Persistence

**User Story:** As a system administrator, I want the system to remember which iteration was last reviewed, so that incremental reviews work correctly across system restarts.

#### Acceptance Criteria

1. THE Review_Agent SHALL store the Last_Reviewed_Iteration ID in persistent storage after completing a review
2. THE Review_Agent SHALL associate the Last_Reviewed_Iteration with the specific pull request ID and repository ID
3. THE Review_Agent SHALL retrieve the Last_Reviewed_Iteration from persistent storage when processing a PR_Update_Event
4. WHEN persistent storage is unavailable, THE Review_Agent SHALL log an error and perform a full review of the current iteration
5. THE Review_Agent SHALL update the Last_Reviewed_Iteration atomically to prevent race conditions

### Requirement 7: Webhook Event Handling

**User Story:** As a system administrator, I want the webhook handler to process both PR creation and PR update events, so that the system handles the complete PR lifecycle.

#### Acceptance Criteria

1. THE PR_Monitor SHALL handle both `git.pullrequest.created` and `git.pullrequest.updated` events using the same webhook endpoint
2. WHEN a `git.pullrequest.created` event is received, THE PR_Monitor SHALL trigger a full review of all PR changes
3. WHEN a `git.pullrequest.updated` event is received, THE PR_Monitor SHALL trigger an Incremental_Review of new changes
4. THE PR_Monitor SHALL enqueue review jobs with metadata indicating whether the review is full or incremental
5. THE PR_Monitor SHALL prevent duplicate review jobs for the same PR and iteration

### Requirement 8: Error Handling for Iteration Comparison

**User Story:** As a system administrator, I want the system to handle errors gracefully during iteration comparison, so that PR reviews continue even when comparison fails.

#### Acceptance Criteria

1. WHEN iteration comparison fails, THE Review_Agent SHALL log the error with full context
2. IF iteration comparison fails, THEN THE Review_Agent SHALL fall back to performing a full review of the current iteration
3. WHEN the Last_Reviewed_Iteration no longer exists in Azure DevOps, THE Review_Agent SHALL perform a full review
4. WHEN Azure DevOps API returns an error during iteration retrieval, THE Review_Agent SHALL retry up to 3 times with exponential backoff
5. IF all retries fail, THEN THE Review_Agent SHALL log the error and skip the review

### Requirement 9: Logging and Observability for PR Updates

**User Story:** As a system administrator, I want comprehensive logging of PR update processing, so that I can troubleshoot issues and monitor incremental review performance.

#### Acceptance Criteria

1. THE PR_Monitor SHALL log all PR_Update_Event detections with timestamp, PR ID, and iteration ID
2. THE Iteration_Comparator SHALL log the number of files in the Change_Delta
3. THE Review_Agent SHALL log whether a review is full or incremental
4. THE Review_Agent SHALL log the Last_Reviewed_Iteration and current iteration IDs
5. THE System SHALL emit metrics including iteration comparison time, Change_Delta size, and number of comments posted
6. THE Comment_Publisher SHALL log the number of duplicate comments skipped

### Requirement 10: Backward Compatibility

**User Story:** As a system administrator, I want the PR update enhancement to work alongside existing PR creation functionality, so that no existing features are broken.

#### Acceptance Criteria

1. THE System SHALL continue to handle `git.pullrequest.created` events exactly as before
2. THE System SHALL maintain the existing webhook endpoint URL
3. THE System SHALL use the same Review_Agent, Code_Analyzer, and Comment_Publisher components for both PR creation and PR update events
4. THE System SHALL not require changes to existing Azure DevOps Service Hook configurations
5. WHEN processing a `git.pullrequest.created` event, THE System SHALL not perform iteration comparison

