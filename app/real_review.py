"""
Real PR review implementation using Azure DevOps and OpenAI.
"""

import os
import logging
from typing import List, Dict
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from openai import OpenAI

logger = logging.getLogger(__name__)


class PRReviewer:
    """Real PR reviewer that fetches code and posts comments."""
    
    def __init__(self):
        self.azure_pat = os.getenv("AZURE_DEVOPS_PAT")
        self.azure_org = os.getenv("AZURE_DEVOPS_ORG")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        
        if not self.azure_pat or not self.azure_org:
            raise ValueError("AZURE_DEVOPS_PAT and AZURE_DEVOPS_ORG must be set")
        
        # Initialize Azure DevOps connection
        self.organization_url = f"https://dev.azure.com/{self.azure_org}"
        credentials = BasicAuthentication('', self.azure_pat)
        self.connection = Connection(base_url=self.organization_url, creds=credentials)
        self.git_client = self.connection.clients.get_git_client()
        
        # Initialize OpenAI client
        if self.openai_key:
            self.openai_client = OpenAI(api_key=self.openai_key)
        else:
            self.openai_client = None
            logger.warning("OpenAI API key not set - will skip AI analysis")
    
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
            
            # Step 2: Get changed files
            logger.info(f"[Step 2/5] Fetching changed files...")
            changes = self.git_client.get_pull_request_iteration_changes(
                repository_id=repository_id,
                pull_request_id=pr_id,
                iteration_id=1
            )
            
            changed_files = []
            for change in changes.change_entries:
                if change.item and hasattr(change.item, 'path'):
                    file_path = change.item.path
                    if not self._is_binary_file(file_path):
                        changed_files.append(file_path)
                        logger.info(f"  - {file_path}")
            
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
            
            if self.openai_client and file_contents:
                for file_path, content in file_contents.items():
                    logger.info(f"  - Analyzing {file_path}...")
                    file_comments = await self._analyze_file_with_ai(file_path, content)
                    comments.extend(file_comments)
                    logger.info(f"    Found {len(file_comments)} issues")
            else:
                logger.warning("Skipping AI analysis (no OpenAI key or no files)")
                # Add a simple comment
                comments.append({
                    "content": "✅ PR received and processed! (AI analysis disabled - add OPENAI_API_KEY to enable)",
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
        """Analyze file with OpenAI and return comments."""
        if not self.openai_client:
            return []
        
        try:
            # Truncate content if too long
            max_chars = 4000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n... (truncated)"
            
            prompt = f"""Review this code file and identify issues:

File: {file_path}

Code:
```
{content}
```

Provide a brief review focusing on:
1. Security vulnerabilities
2. Code quality issues
3. Best practice violations

Format: List 2-3 most important issues, each on a new line starting with "- "
Keep it concise and actionable."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a code reviewer. Be concise and focus on important issues."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            review_text = response.choices[0].message.content.strip()
            
            # Create a comment for this file
            return [{
                "content": f"**{file_path}**\n\n{review_text}",
                "file_path": file_path,
                "line": None
            }]
            
        except Exception as e:
            logger.error(f"AI analysis failed for {file_path}: {e}")
            return []
    
    def _post_comment(self, repository_id: str, pr_id: int, comment: Dict):
        """Post a comment to the PR."""
        from azure.devops.v7_1.git.models import Comment, CommentThread, CommentThreadContext
        
        # Create comment thread
        thread = CommentThread()
        thread.comments = [Comment(content=comment["content"])]
        
        # If file-specific, add context
        if comment.get("file_path"):
            thread.thread_context = CommentThreadContext(
                file_path=comment["file_path"],
                right_file_start={"line": comment.get("line", 1), "offset": 1} if comment.get("line") else None
            )
        
        # Post the thread
        self.git_client.create_thread(
            comment_thread=thread,
            repository_id=repository_id,
            pull_request_id=pr_id
        )
    
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
