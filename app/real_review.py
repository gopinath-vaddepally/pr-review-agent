"""
Real PR review implementation using Azure DevOps and AI (Groq/Anthropic/Ollama).
"""

import os
import logging
from typing import List, Dict
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Load environment variables - try multiple locations
env_files = ['.env.local', '.env']
for env_file in env_files:
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path, override=True)
        logger.info(f"Loaded environment from {env_file}")
        break


class PRReviewer:
    """Real PR reviewer that fetches code and posts comments."""
    
    def __init__(self):
        # Debug: Print all env vars starting with AI keys
        logger.info("=== Environment Variables Debug ===")
        for key, value in os.environ.items():
            if key.startswith(('GROQ', 'ANTHROPIC', 'AZURE', 'OPENAI')):
                masked_value = value[:10] + '...' if len(value) > 10 else value
                logger.info(f"  {key} = {masked_value}")
        
        self.azure_pat = os.getenv("AZURE_DEVOPS_PAT")
        self.azure_org = os.getenv("AZURE_DEVOPS_ORG")
        
        # Try different AI API keys (priority: Groq > Anthropic > OpenAI)
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        logger.info(f"Environment check:")
        logger.info(f"  - AZURE_DEVOPS_PAT: {'✓ Set' if self.azure_pat else '✗ Missing'}")
        logger.info(f"  - AZURE_DEVOPS_ORG: {self.azure_org if self.azure_org else '✗ Missing'}")
        logger.info(f"  - GROQ_API_KEY: {'✓ Set' if self.groq_key else '✗ Missing'}")
        logger.info(f"  - ANTHROPIC_API_KEY: {'✓ Set' if self.anthropic_key else '✗ Missing'}")
        
        if not self.azure_pat or not self.azure_org:
            raise ValueError("AZURE_DEVOPS_PAT and AZURE_DEVOPS_ORG must be set")
        
        # Initialize Azure DevOps connection
        self.organization_url = f"https://dev.azure.com/{self.azure_org}"
        credentials = BasicAuthentication('', self.azure_pat)
        self.connection = Connection(base_url=self.organization_url, creds=credentials)
        self.git_client = self.connection.clients.get_git_client()
        
        # Initialize AI client (priority: Groq > Anthropic > Ollama)
        self.ai_client = None
        self.ai_type = None
        
        if self.groq_key:
            try:
                from groq import Groq
                import httpx
                
                # Create httpx client with SSL verification disabled (for corporate firewalls)
                http_client = httpx.Client(verify=False, timeout=30.0)
                
                self.ai_client = Groq(
                    api_key=self.groq_key,
                    http_client=http_client
                )
                self.ai_type = "groq"
                logger.info("✅ Groq AI client initialized successfully (PRIMARY, FREE, SSL disabled)")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Groq client: {e}")
                logger.info("Falling back to Anthropic...")
        
        if not self.ai_client and self.anthropic_key:
            try:
                from anthropic import Anthropic
                import httpx
                
                # Create httpx client with SSL verification disabled (for corporate firewalls)
                http_client = httpx.Client(verify=False, timeout=30.0)
                
                self.ai_client = Anthropic(
                    api_key=self.anthropic_key,
                    http_client=http_client
                )
                self.ai_type = "anthropic"
                logger.info("✅ Anthropic Claude client initialized successfully (FALLBACK, SSL disabled)")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Anthropic client: {e}")
        
        if not self.ai_client:
            # Try Ollama (local, free, no API key needed)
            try:
                import httpx
                response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
                if response.status_code == 200:
                    self.ai_client = "ollama"
                    self.ai_type = "ollama"
                    logger.info("✅ Ollama (local LLM) detected and ready (FALLBACK)")
            except Exception:
                logger.warning("⚠️ No AI available. Add GROQ_API_KEY or ANTHROPIC_API_KEY")
    
    async def review_pr(self, repository_id: str, pr_id: int, project_id: str, is_update: bool = False):
        """
        Review a PR: fetch changes, analyze with AI, post comments.
        
        Args:
            repository_id: Azure DevOps repository ID
            pr_id: Pull request ID
            project_id: Azure DevOps project ID
            is_update: If True, perform incremental review of new changes only
        """
        logger.info(f"Starting {'incremental' if is_update else 'full'} review for PR {pr_id} in repository {repository_id}")
        
        try:
            # Step 1: Get PR details
            logger.info(f"[Step 1/6] Fetching PR details...")
            pr = self.git_client.get_pull_request(repository_id, pr_id)
            logger.info(f"PR Title: {pr.title}")
            logger.info(f"Author: {pr.created_by.display_name}")
            logger.info(f"Source: {pr.source_ref_name} -> Target: {pr.target_ref_name}")
            
            # Step 2: Handle iteration tracking for incremental reviews
            last_reviewed_iteration = None
            current_iteration_id = None
            
            if is_update:
                logger.info(f"[Step 2/6] Checking PR iterations for incremental review...")
                try:
                    # Get all PR iterations
                    iterations = self.git_client.get_pull_request_iterations(repository_id, pr_id)
                    
                    if iterations and len(iterations) > 0:
                        # Current iteration is the latest
                        current_iteration_id = len(iterations)
                        logger.info(f"Current iteration: {current_iteration_id}")
                        
                        # Get last reviewed iteration from file storage
                        last_reviewed_iteration = self._get_last_reviewed_iteration(repository_id, pr_id)
                        
                        if last_reviewed_iteration:
                            logger.info(f"Last reviewed iteration: {last_reviewed_iteration}")
                            logger.info(f"Will review changes from iteration {last_reviewed_iteration} to {current_iteration_id}")
                        else:
                            logger.info(f"No previous review found, performing full review")
                            is_update = False  # Fall back to full review
                    else:
                        logger.warning("Could not retrieve iterations, performing full review")
                        is_update = False
                        
                except Exception as e:
                    logger.warning(f"Error checking iterations: {e}, falling back to full review")
                    is_update = False
            else:
                logger.info(f"[Step 2/6] Skipping iteration check (full review)")
            
            # Step 3: Get changed files
            logger.info(f"[Step 3/6] Fetching changed files...")
            
            changed_files = []
            
            if is_update and last_reviewed_iteration:
                # Get only files changed since last review
                changed_files = await self._get_iteration_changes(
                    repository_id, 
                    pr_id, 
                    last_reviewed_iteration, 
                    current_iteration_id
                )
                logger.info(f"Found {len(changed_files)} files changed since iteration {last_reviewed_iteration}")
            else:
                # Get all changed files (full review)
                changed_files = await self._get_all_pr_changes(repository_id, pr_id)
                logger.info(f"Found {len(changed_files)} total changed files")
            
            # Step 4: Get file contents
            logger.info(f"[Step 4/6] Fetching file contents...")
            file_contents = {}
            for file_path in changed_files[:5]:  # Limit to 5 files for now
                try:
                    content = self._get_file_content(
                        repository_id,
                        file_path,
                        pr.last_merge_source_commit.commit_id
                    )
                    if content:
                        file_contents[file_path] = content
                        logger.info(f"  - Retrieved {file_path} ({len(content)} bytes)")
                except Exception as e:
                    logger.warning(f"  - Could not retrieve {file_path}: {e}")
            
            # Step 5: Analyze with AI
            logger.info(f"[Step 5/6] Analyzing code with AI...")
            comments = []
            
            if self.ai_client and file_contents:
                # Always check for existing comments and resolve fixed issues
                # (even on full reviews, in case this is a re-review)
                logger.info("Checking if previous issues were resolved...")
                await self._check_and_resolve_previous_issues(repository_id, pr_id, file_contents)
                
                # Now analyze all changes
                for file_path, content in file_contents.items():
                    logger.info(f"  - Analyzing {file_path}...")
                    file_comments = await self._analyze_file_with_ai(file_path, content)
                    
                    # Filter out duplicate comments
                    file_comments = await self._filter_duplicate_comments(
                        repository_id, pr_id, file_comments
                    )
                    
                    comments.extend(file_comments)
                    logger.info(f"    Found {len(file_comments)} new issues")
            else:
                logger.warning("Skipping AI analysis (no AI key or no files)")
                # Add a simple comment
                comments.append({
                    "content": "✅ PR received and processed! (AI analysis disabled - add GROQ_API_KEY or ANTHROPIC_API_KEY to enable)",
                    "file_path": None,
                    "line": None
                })
            
            logger.info(f"Total comments to post: {len(comments)}")
            
            # Step 6: Post comments
            logger.info(f"[Step 6/6] Posting comments to PR...")
            for i, comment in enumerate(comments, 1):
                try:
                    self._post_comment(repository_id, pr_id, comment)
                    logger.info(f"  - Posted comment {i}/{len(comments)}")
                except Exception as e:
                    logger.error(f"  - Failed to post comment {i}: {e}")
            
            # Save current iteration as last reviewed
            if is_update and current_iteration_id:
                self._save_last_reviewed_iteration(repository_id, pr_id, current_iteration_id)
                logger.info(f"Saved iteration {current_iteration_id} as last reviewed")
            
            logger.info(f"✅ Review complete for PR {pr_id}!")
            
        except Exception as e:
            logger.error(f"❌ Error reviewing PR {pr_id}: {e}", exc_info=True)
            raise
    
    def _get_file_content(self, repository_id: str, file_path: str, commit_id: str) -> str:
        """Get file content from Azure DevOps."""
        try:
            from azure.devops.v7_1.git.models import GitVersionDescriptor
            
            content_stream = self.git_client.get_item_content(
                repository_id=repository_id,
                path=file_path,
                version_descriptor=GitVersionDescriptor(
                    version=commit_id,
                    version_type="commit"
                )
            )
            
            content = b''.join(content_stream).decode('utf-8', errors='ignore')
            return content
        except Exception as e:
            logger.warning(f"Could not get content for {file_path}: {e}")
            return None
    
    async def _analyze_file_with_ai(self, file_path: str, content: str) -> List[Dict]:
            """Analyze file with AI and return line-specific comments."""
            if not self.ai_client:
                return []

            try:
                # Truncate content if too long
                max_chars = 8000
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n... (truncated)"

                # Add line numbers to the code for AI to reference
                lines = content.split('\n')
                numbered_content = '\n'.join([f"{i+1:4d} | {line}" for i, line in enumerate(lines)])

                # Load language-specific rules from plugin config
                rules_guidance = self._get_language_rules(file_path)

                prompt = f"""Review this code and identify specific issues with line numbers:

    File: {file_path}

    Code (with line numbers):
    ```
    {numbered_content}
    ```

    {rules_guidance}

    For each issue, provide line number, issue description, and fix.
    Format as JSON array:
    [
      {{"line": 15, "issue": "SQL injection vulnerability", "fix": "Use parameterized queries"}},
      {{"line": 23, "issue": "Hardcoded API key", "fix": "Move to environment variable"}}
    ]

    Focus on security, code quality, and best practices. Return 2-5 critical issues.
    Return ONLY the JSON array, no other text."""

                review_text = ""

                # Try Groq first (primary)
                if self.ai_type == "groq":
                    response = self.ai_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": "You are a code reviewer. Return only valid JSON array."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=1000,
                        temperature=0.3
                    )
                    review_text = response.choices[0].message.content.strip()
                    logger.info(f"✓ Groq analysis complete for {file_path}")

                # Try Anthropic Claude (fallback)
                elif self.ai_type == "anthropic":
                    response = self.ai_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        temperature=0.3,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    review_text = response.content[0].text.strip()
                    logger.info(f"✓ Claude analysis complete for {file_path}")

                elif self.ai_type == "ollama":
                    import httpx
                    response = httpx.post(
                        "http://localhost:11434/api/generate",
                        json={"model": "codellama", "prompt": prompt, "stream": False},
                        timeout=60.0
                    )
                    if response.status_code == 200:
                        review_text = response.json().get("response", "").strip()

                # Parse JSON response
                import json
                import re

                # Extract JSON from response
                json_match = re.search(r'\[.*\]', review_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        issues = json.loads(json_str)
                        comments = []

                        for issue in issues:
                            if isinstance(issue, dict) and 'line' in issue and 'issue' in issue:
                                line_num = issue.get('line')
                                issue_text = issue.get('issue', '')
                                fix_text = issue.get('fix', '')

                                comment_text = f"**Issue:** {issue_text}"
                                if fix_text:
                                    comment_text += f"\n\n**Suggested Fix:** {fix_text}"

                                comments.append({
                                    "content": comment_text,
                                    "file_path": file_path,
                                    "line": line_num
                                })

                        logger.info(f"Parsed {len(comments)} line-specific comments")
                        return comments

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON: {e}")

                # Fallback: general comment
                return [{
                    "content": f"**{file_path}**\n\n{review_text}",
                    "file_path": file_path,
                    "line": None
                }]

            except Exception as e:
                logger.error(f"AI analysis failed for {file_path}: {e}", exc_info=True)
                return []
    
    def _get_language_rules(self, file_path: str) -> str:
        """
        Get language-specific review rules from plugin config.
        
        Args:
            file_path: Path to the file being analyzed
            
        Returns:
            Formatted rules guidance for AI prompt
        """
        try:
            import yaml
            
            # Determine language from file extension
            ext = Path(file_path).suffix.lower()
            
            # Map extensions to plugin configs
            plugin_map = {
                '.java': 'plugins/java/config.yaml',
                '.ts': 'plugins/angular/config.yaml',
                '.js': 'plugins/angular/config.yaml',
            }
            
            config_path = plugin_map.get(ext)
            if not config_path or not Path(config_path).exists():
                return "Focus on security, code quality, and best practices."
            
            # Load plugin config
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Get system prompt and rules
            system_prompt = config.get('llm_prompts', {}).get('system_prompt', '')
            rules = config.get('analysis_rules', [])
            
            # Format rules guidance
            guidance = f"{system_prompt}\n\n"
            guidance += "Specifically check for:\n"
            
            # Add rule descriptions
            rule_descriptions = {
                'avoid_null_pointer': '- Null pointer exceptions and missing null checks',
                'resource_leak': '- Resource leaks (unclosed streams, connections)',
                'exception_handling': '- Poor exception handling (empty catch blocks, generic exceptions)',
                'naming_conventions': '- Naming convention violations (PascalCase, camelCase)',
                'code_complexity': '- High complexity (long methods, deep nesting)',
                'unused_imports': '- Unused import statements',
                'magic_numbers': '- Magic numbers that should be constants',
                'long_methods': '- Methods exceeding 50 lines',
                'observable_unsubscribe': '- Missing unsubscribe for Observables',
                'change_detection': '- Inefficient change detection strategies',
                'dependency_injection': '- Improper dependency injection',
            }
            
            for rule in rules:
                if rule in rule_descriptions:
                    guidance += f"{rule_descriptions[rule]}\n"
            
            return guidance.strip()
            
        except Exception as e:
            logger.warning(f"Could not load language rules: {e}")
            return "Focus on security, code quality, and best practices."

    
    def _post_comment(self, repository_id: str, pr_id: int, comment: Dict):
        """Post a comment to the PR with inline positioning."""
        from azure.devops.v7_1.git.models import Comment, CommentThread, CommentThreadContext, CommentPosition
        
        # Create comment thread
        thread = CommentThread()
        thread.comments = [Comment(content=comment["content"])]
        thread.status = 1  # 1 = Active status
        
        # If file-specific with line number, add context for inline comment
        if comment.get("file_path") and comment.get("line"):
            line_num = comment.get("line")
            file_path = comment.get("file_path")
            
            # Ensure path starts with / for Azure DevOps
            if not file_path.startswith('/'):
                file_path = '/' + file_path
            
            # Create CommentPosition for the line
            right_position = CommentPosition(line=line_num, offset=1)
            
            # Create thread context with file path and line position
            thread.thread_context = CommentThreadContext(
                file_path=file_path,
                right_file_start=right_position,
                right_file_end=right_position  # Same line for single-line comment
            )
            
            logger.info(f"Posting inline comment on {file_path}:{line_num} (Status: Active)")
        
        elif comment.get("file_path"):
            # File-level comment (no specific line)
            file_path = comment.get("file_path")
            if not file_path.startswith('/'):
                file_path = '/' + file_path
                
            thread.thread_context = CommentThreadContext(
                file_path=file_path
            )
            logger.info(f"Posting file-level comment on {file_path} (Status: Active)")
        else:
            # General PR comment
            logger.info("Posting general PR comment (Status: Active)")
        
        # Post the thread
        try:
            self.git_client.create_thread(
                comment_thread=thread,
                repository_id=repository_id,
                pull_request_id=pr_id
            )
        except Exception as e:
            logger.error(f"Failed to post comment: {e}")
            logger.debug(f"Comment details: file_path={comment.get('file_path')}, line={comment.get('line')}")
            raise
    
    def _is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary."""
        binary_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
            '.pdf', '.zip', '.tar', '.gz', '.rar', '.7z',
            '.exe', '.dll', '.so', '.dylib',
            '.class', '.jar', '.war',
            '.woff', '.woff2', '.ttf', '.eot',
        }
        return any(file_path.lower().endswith(ext) for ext in binary_extensions)
    
    def _get_last_reviewed_iteration(self, repository_id: str, pr_id: int) -> int:
        """Get the last reviewed iteration from file storage."""
        try:
            import json
            state_file = Path(f".pr_state_{repository_id}_{pr_id}.json")
            
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('last_reviewed_iteration')
            return None
        except Exception as e:
            logger.warning(f"Could not load last reviewed iteration: {e}")
            return None
    
    def _save_last_reviewed_iteration(self, repository_id: str, pr_id: int, iteration_id: int):
        """Save the last reviewed iteration to file storage."""
        try:
            import json
            state_file = Path(f".pr_state_{repository_id}_{pr_id}.json")
            
            state = {
                'last_reviewed_iteration': iteration_id,
                'repository_id': repository_id,
                'pr_id': pr_id,
                'timestamp': str(Path(__file__).stat().st_mtime)
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
            logger.info(f"Saved state to {state_file}")
        except Exception as e:
            logger.error(f"Could not save last reviewed iteration: {e}")
    
    async def _get_iteration_changes(self, repository_id: str, pr_id: int, from_iteration: int, to_iteration: int) -> List[str]:
        """Get files that changed between two iterations."""
        try:
            logger.info(f"Comparing iterations {from_iteration} to {to_iteration}")
            
            # Get changes for the iteration range
            iteration_changes = self.git_client.get_pull_request_iteration_changes(
                repository_id=repository_id,
                pull_request_id=pr_id,
                iteration_id=to_iteration
            )
            
            changed_files = set()
            
            if iteration_changes and hasattr(iteration_changes, 'change_entries'):
                for change in iteration_changes.change_entries:
                    try:
                        if hasattr(change, 'item') and change.item:
                            file_path = change.item.path
                            
                            # Clean up path
                            if file_path and file_path.startswith('/'):
                                file_path = file_path[1:]
                            
                            # Skip folders and binary files
                            is_folder = getattr(change.item, 'is_folder', False)
                            if not is_folder and file_path and not self._is_binary_file(file_path):
                                changed_files.add(file_path)
                                logger.info(f"  ✓ Changed: {file_path}")
                    except Exception as e:
                        logger.warning(f"Error processing iteration change: {e}")
                        continue
            
            return list(changed_files)
            
        except Exception as e:
            logger.error(f"Error getting iteration changes: {e}", exc_info=True)
            # Fall back to getting all changes
            return await self._get_all_pr_changes(repository_id, pr_id)
    
    async def _get_all_pr_changes(self, repository_id: str, pr_id: int) -> List[str]:
        """Get all changed files in the PR (for full review)."""
        changed_files = []
        
        try:
            logger.info("Getting all PR changes...")
            pr_files = self.git_client.get_pull_request_commits(
                repository_id=repository_id,
                pull_request_id=pr_id
            )
            
            logger.info(f"Found {len(pr_files) if pr_files else 0} commits in PR")
            
            # Get changes from each commit
            seen_files = set()
            for commit in pr_files:
                try:
                    commit_id = commit.commit_id
                    logger.info(f"Getting changes for commit {commit_id[:8]}...")
                    
                    changes = self.git_client.get_changes(
                        commit_id=commit_id,
                        repository_id=repository_id
                    )
                    
                    if changes and hasattr(changes, 'changes'):
                        logger.info(f"  Found {len(changes.changes)} changes in commit")
                        for idx, change in enumerate(changes.changes):
                            try:
                                file_path = None
                                
                                # Access as dictionary
                                if 'item' in change and change['item'] and 'path' in change['item']:
                                    file_path = change['item']['path']
                                elif 'path' in change:
                                    file_path = change['path']
                                
                                if file_path:
                                    # Clean up path
                                    if file_path.startswith('/'):
                                        file_path = file_path[1:]
                                    
                                    # Check if it's a file (not a folder)
                                    is_folder = False
                                    if 'item' in change and change['item']:
                                        if 'isFolder' in change['item']:
                                            is_folder = change['item']['isFolder']
                                        elif 'gitObjectType' in change['item']:
                                            is_folder = change['item']['gitObjectType'] != 'blob'
                                    
                                    # Skip folders, binary files and duplicates
                                    if not is_folder and file_path and file_path not in seen_files and not self._is_binary_file(file_path):
                                        changed_files.append(file_path)
                                        seen_files.add(file_path)
                                        
                            except Exception as e:
                                logger.warning(f"    Error processing change: {e}")
                                continue
                except Exception as e:
                    logger.warning(f"Error processing commit: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error getting PR files: {e}", exc_info=True)
        
        return changed_files
    
    async def _filter_duplicate_comments(self, repository_id: str, pr_id: int, new_comments: List[Dict]) -> List[Dict]:
        """Filter out comments that already exist on the PR."""
        try:
            # Get existing comment threads
            existing_threads = self.git_client.get_threads(repository_id, pr_id)
            
            # Build a set of (file_path, line) tuples for existing comments
            existing_locations = set()
            
            for thread in existing_threads:
                if thread.thread_context and thread.thread_context.file_path:
                    file_path = thread.thread_context.file_path
                    if file_path.startswith('/'):
                        file_path = file_path[1:]
                    
                    # Get line number if available
                    line = None
                    if thread.thread_context.right_file_start:
                        line = thread.thread_context.right_file_start.line
                    
                    existing_locations.add((file_path, line))
            
            # Filter out duplicates
            filtered_comments = []
            skipped_count = 0
            
            for comment in new_comments:
                file_path = comment.get('file_path')
                line = comment.get('line')
                
                if file_path and (file_path, line) in existing_locations:
                    skipped_count += 1
                    logger.info(f"  ⊘ Skipping duplicate comment on {file_path}:{line}")
                else:
                    filtered_comments.append(comment)
            
            if skipped_count > 0:
                logger.info(f"Filtered out {skipped_count} duplicate comments")
            
            return filtered_comments
            
        except Exception as e:
            logger.warning(f"Could not filter duplicates: {e}, posting all comments")
            return new_comments
    
    async def _check_and_resolve_previous_issues(self, repository_id: str, pr_id: int, current_file_contents: Dict[str, str]):
        """
        Check if previous issues were fixed and mark threads as resolved.
        
        Strategy:
        1. Get all existing open comment threads
        2. For each thread, check if the file was changed
        3. Re-analyze the code at that location
        4. If the issue is no longer present, mark as resolved
        
        Thread Status Values:
        - 0 = Unknown
        - 1 = Active
        - 2 = Pending
        - 3 = Fixed
        - 4 = Won't Fix
        - 5 = Closed
        """
        try:
            from azure.devops.v7_1.git.models import Comment
            
            logger.info("Checking previous issues for resolution...")
            
            # Get all existing comment threads
            existing_threads = self.git_client.get_threads(repository_id, pr_id)
            
            resolved_count = 0
            kept_count = 0
            checked_count = 0
            
            for thread in existing_threads:
                # Skip if thread is already resolved or closed (status 3, 4, or 5)
                if thread.status in [3, 4, 5]:
                    continue
                
                # Skip if no file context (general PR comments)
                if not thread.thread_context or not thread.thread_context.file_path:
                    continue
                
                file_path = thread.thread_context.file_path
                if file_path.startswith('/'):
                    file_path = file_path[1:]
                
                # Get line number
                line_num = None
                if thread.thread_context.right_file_start:
                    line_num = thread.thread_context.right_file_start.line
                
                # Get the original issue description from the thread
                original_issue = None
                if thread.comments and len(thread.comments) > 0:
                    original_issue = thread.comments[0].content
                
                if not original_issue or not line_num:
                    kept_count += 1
                    continue
                
                # Check if this file is in the current review
                if file_path not in current_file_contents:
                    # File not changed in this update, keep the comment
                    kept_count += 1
                    logger.debug(f"  ⊙ File not in update: {file_path}:{line_num}")
                    continue
                
                checked_count += 1
                
                # Get the current content
                content = current_file_contents[file_path]
                
                # Ask AI if the issue still exists
                is_fixed = await self._check_if_issue_fixed(
                    file_path, 
                    content, 
                    line_num, 
                    original_issue
                )
                
                if is_fixed:
                    # Mark thread as resolved
                    try:
                        thread.status = 3  # 3 = Fixed status
                        
                        # Add a comment saying it's fixed
                        resolution_comment = Comment(
                            content="✅ **Issue Resolved** - This issue has been fixed in the latest update."
                        )
                        
                        # Update the thread status
                        self.git_client.update_thread(
                            comment_thread=thread,
                            repository_id=repository_id,
                            pull_request_id=pr_id,
                            thread_id=thread.id
                        )
                        
                        # Add resolution comment
                        self.git_client.create_comment(
                            comment=resolution_comment,
                            repository_id=repository_id,
                            pull_request_id=pr_id,
                            thread_id=thread.id
                        )
                        
                        resolved_count += 1
                        logger.info(f"  ✅ Resolved: {file_path}:{line_num} (Status: Fixed)")
                        
                    except Exception as e:
                        logger.warning(f"Could not mark thread as resolved: {e}")
                else:
                    # Issue still exists, keep the comment visible
                    kept_count += 1
                    logger.info(f"  ⚠️  Still unresolved: {file_path}:{line_num}")
            
            logger.info(f"Issue resolution check complete: checked {checked_count}, resolved {resolved_count}, kept {kept_count} open")
            
        except Exception as e:
            logger.error(f"Error checking previous issues: {e}", exc_info=True)
    
    async def _check_if_issue_fixed(self, file_path: str, content: str, line_num: int, original_issue: str) -> bool:
        """
        Use AI to check if a previously reported issue has been fixed.
        
        Args:
            file_path: Path to the file
            content: Current file content
            line_num: Line number where issue was reported
            original_issue: Original issue description
            
        Returns:
            True if issue is fixed, False otherwise
        """
        try:
            # Get the relevant section of code around the line
            lines = content.split('\n')
            start_line = max(0, line_num - 5)
            end_line = min(len(lines), line_num + 5)
            
            code_section = '\n'.join([
                f"{i+1:4d} | {line}" 
                for i, line in enumerate(lines[start_line:end_line], start=start_line)
            ])
            
            prompt = f"""Check if a previously reported issue has been fixed.

File: {file_path}
Line: {line_num}

Original Issue:
{original_issue}

Current Code (around line {line_num}):
```
{code_section}
```

Has this issue been fixed? Reply with ONLY "FIXED" or "NOT_FIXED".
- Reply "FIXED" if the code no longer has the issue
- Reply "NOT_FIXED" if the issue still exists or if you're unsure"""

            response_text = ""
            
            # Try Groq first
            if self.ai_type == "groq":
                response = self.ai_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a code reviewer. Reply with only FIXED or NOT_FIXED."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=10,
                    temperature=0.1
                )
                response_text = response.choices[0].message.content.strip().upper()
            
            # Try Anthropic Claude
            elif self.ai_type == "anthropic":
                response = self.ai_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=10,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text.strip().upper()
            
            # Check response
            is_fixed = "FIXED" in response_text and "NOT_FIXED" not in response_text
            
            logger.debug(f"Issue check for {file_path}:{line_num} - AI response: {response_text} -> {'FIXED' if is_fixed else 'NOT_FIXED'}")
            
            return is_fixed
            
        except Exception as e:
            logger.warning(f"Could not check if issue was fixed: {e}")
            # If we can't check, assume it's not fixed (keep the comment)
            return False
