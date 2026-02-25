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
    
    async def review_pr(self, repository_id: str, pr_id: int, project_id: str):
        """
        Review a PR: fetch changes, analyze with AI, post comments.
        
        Args:
            repository_id: Azure DevOps repository ID
            pr_id: Pull request ID
            project_id: Azure DevOps project ID
        """
        logger.info(f"Starting review for PR {pr_id} in repository {repository_id}")
        
        try:
            # Step 1: Get PR details
            logger.info(f"[Step 1/5] Fetching PR details...")
            pr = self.git_client.get_pull_request(repository_id, pr_id)
            logger.info(f"PR Title: {pr.title}")
            logger.info(f"Author: {pr.created_by.display_name}")
            logger.info(f"Source: {pr.source_ref_name} -> Target: {pr.target_ref_name}")
            
            # Step 2: Get changed files from PR
            logger.info(f"[Step 2/5] Fetching changed files...")
            
            changed_files = []
            
            try:
                # Method 1: Try getting files directly from PR
                logger.info("Trying to get files from PR directly...")
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
                                    # Changes are dictionaries, not objects
                                    logger.info(f"  Change {idx + 1}:")
                                    logger.info(f"    - Keys: {list(change.keys())}")
                                    
                                    # Log first change in detail
                                    if idx == 0:
                                        logger.info(f"    - Full content: {change}")
                                    
                                    file_path = None
                                    
                                    # Access as dictionary
                                    if 'item' in change and change['item'] and 'path' in change['item']:
                                        file_path = change['item']['path']
                                        logger.info(f"    - Got path from item['path']: {file_path}")
                                    elif 'path' in change:
                                        file_path = change['path']
                                        logger.info(f"    - Got path from ['path']: {file_path}")
                                    
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
                                            logger.info(f"    ✓ Added: {file_path}")
                                        else:
                                            if is_folder:
                                                logger.info(f"    ✗ Skipped (folder): {file_path}")
                                            elif file_path in seen_files:
                                                logger.info(f"    ✗ Skipped (duplicate): {file_path}")
                                            elif self._is_binary_file(file_path):
                                                logger.info(f"    ✗ Skipped (binary): {file_path}")
                                    else:
                                        logger.info(f"    ✗ No path found")
                                        
                                except Exception as e:
                                    logger.warning(f"    Error processing change: {e}", exc_info=True)
                                    continue
                    except Exception as e:
                        logger.warning(f"Error processing commit: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error getting PR files: {e}", exc_info=True)
            
            logger.info(f"Found {len(changed_files)} changed files")
            
            # Step 3: Get file contents
            logger.info(f"[Step 3/5] Fetching file contents...")
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
            
            # Step 4: Analyze with AI
            logger.info(f"[Step 4/5] Analyzing code with AI...")
            comments = []
            
            if self.ai_client and file_contents:
                for file_path, content in file_contents.items():
                    logger.info(f"  - Analyzing {file_path}...")
                    file_comments = await self._analyze_file_with_ai(file_path, content)
                    comments.extend(file_comments)
                    logger.info(f"    Found {len(file_comments)} issues")
            else:
                logger.warning("Skipping AI analysis (no AI key or no files)")
                # Add a simple comment
                comments.append({
                    "content": "✅ PR received and processed! (AI analysis disabled - add GROQ_API_KEY or ANTHROPIC_API_KEY to enable)",
                    "file_path": None,
                    "line": None
                })
            
            logger.info(f"Total comments to post: {len(comments)}")
            
            # Step 5: Post comments
            logger.info(f"[Step 5/5] Posting comments to PR...")
            for i, comment in enumerate(comments, 1):
                try:
                    self._post_comment(repository_id, pr_id, comment)
                    logger.info(f"  - Posted comment {i}/{len(comments)}")
                except Exception as e:
                    logger.error(f"  - Failed to post comment {i}: {e}")
            
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

                prompt = f"""Review this code and identify specific issues with line numbers:

    File: {file_path}

    Code (with line numbers):
    ```
    {numbered_content}
    ```

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

    
    def _post_comment(self, repository_id: str, pr_id: int, comment: Dict):
        """Post a comment to the PR with inline positioning."""
        from azure.devops.v7_1.git.models import Comment, CommentThread, CommentThreadContext, CommentPosition
        
        # Create comment thread
        thread = CommentThread()
        thread.comments = [Comment(content=comment["content"])]
        
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
            
            logger.info(f"Posting inline comment on {file_path}:{line_num}")
        
        elif comment.get("file_path"):
            # File-level comment (no specific line)
            file_path = comment.get("file_path")
            if not file_path.startswith('/'):
                file_path = '/' + file_path
                
            thread.thread_context = CommentThreadContext(
                file_path=file_path
            )
            logger.info(f"Posting file-level comment on {file_path}")
        else:
            # General PR comment
            logger.info("Posting general PR comment")
        
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
