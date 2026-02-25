-- MySQL initialization script for PR Review Agent
-- This script creates the database schema for repository configuration,
-- service hooks, and agent execution tracking.

-- Repository configuration table
CREATE TABLE IF NOT EXISTS repositories (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    organization VARCHAR(255) NOT NULL,
    project VARCHAR(255) NOT NULL,
    repository_name VARCHAR(255) NOT NULL,
    repository_url TEXT NOT NULL,
    service_hook_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT unique_repo UNIQUE (organization, project, repository_name),
    UNIQUE KEY unique_repository_url (repository_url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_repositories_url ON repositories(repository_url(255));
CREATE INDEX idx_repositories_org_project ON repositories(organization, project);

-- Service hook registration tracking
CREATE TABLE IF NOT EXISTS service_hooks (
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
CREATE TABLE IF NOT EXISTS agent_executions (
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
