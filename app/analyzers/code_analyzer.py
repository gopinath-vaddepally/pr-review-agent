"""
Code Analyzer component for line-level code quality analysis.

This module provides the CodeAnalyzer class that uses language plugins to analyze
code changes and generate review comments using LLM inference.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI, AsyncAzureOpenAI

from app.models import (
    FileChange,
    LineComment,
    CommentSeverity,
    CommentCategory,
    ASTNode,
    CodeContext,
    AnalysisRule,
    CodeIssue,
)
from plugins.manager import PluginManager
from app.utils.resilience import CircuitBreaker, create_llm_circuit_breaker

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper for OpenAI/Azure OpenAI API client."""
    
    def __init__(self, settings=None, circuit_breaker: Optional[CircuitBreaker] = None):
        """Initialize LLM client based on configuration."""
        if settings is None:
            from app.config import settings as app_settings
            settings = app_settings
        
        # Initialize circuit breaker
        self.circuit_breaker = circuit_breaker or create_llm_circuit_breaker()
        
        if settings.azure_openai_endpoint and settings.azure_openai_api_key:
            # Use Azure OpenAI
            self.client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-15-preview",
                azure_endpoint=settings.azure_openai_endpoint,
            )
            self.deployment = settings.azure_openai_deployment or "gpt-4"
            self.is_azure = True
            logger.info("Initialized Azure OpenAI client")
        else:
            # Use OpenAI
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.deployment = "gpt-4"
            self.is_azure = False
            logger.info("Initialized OpenAI client")
    
    async def analyze_code(
        self,
        line_content: str,
        context: CodeContext,
        rule: AnalysisRule,
    ) -> Optional[str]:
        """
        Analyze a line of code using LLM with circuit breaker protection.
        
        Args:
            line_content: The line of code to analyze
            context: Context information for the line
            rule: Analysis rule to apply
            
        Returns:
            Analysis result as string, or None if no issue found
        """
        async def _call_llm():
            # Build the prompt
            system_prompt = self._build_system_prompt(context.language)
            user_prompt = self._build_user_prompt(line_content, context, rule)
            
            # Call LLM API
            response = await self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            
            result = response.choices[0].message.content.strip()
            
            # Check if LLM found an issue
            if result.lower().startswith("no issue") or result.lower().startswith("looks good"):
                return None
            
            return result
        
        try:
            # Execute with circuit breaker protection
            return await self.circuit_breaker.call(_call_llm)
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}", exc_info=True)
            return None
    
    def _build_system_prompt(self, language: str) -> str:
        """Build system prompt for LLM."""
        return f"""You are an expert {language} code reviewer. Analyze code for:
- Potential bugs (null pointer risks, resource leaks, boundary errors)
- Code smells (long methods, deep nesting, duplication)
- Security vulnerabilities (injection risks, insecure data handling)
- Best practice violations (naming conventions, error handling, documentation)

If you find an issue, provide:
1. A clear description of the problem
2. Why it's problematic
3. A specific suggestion for improvement

If the code looks good, respond with "No issue found."
Be concise and actionable."""
    
    def _build_user_prompt(
        self,
        line_content: str,
        context: CodeContext,
        rule: AnalysisRule,
    ) -> str:
        """Build user prompt with code context."""
        prompt_parts = [
            f"Analyze this {context.language} code for: {rule.pattern}",
            f"\nFile: {context.file_path}",
        ]
        
        if context.enclosing_class:
            prompt_parts.append(f"Class: {context.enclosing_class}")
        
        if context.enclosing_method:
            prompt_parts.append(f"Method: {context.enclosing_method}")
        
        if context.imports:
            prompt_parts.append(f"Imports: {', '.join(context.imports[:5])}")
        
        prompt_parts.append(f"\nLine {context.line_number}: {line_content}")
        
        if context.surrounding_lines:
            prompt_parts.append("\nContext:")
            for i, line in enumerate(context.surrounding_lines):
                prompt_parts.append(f"  {line}")
        
        prompt_parts.append(f"\n{rule.llm_prompt}")
        
        return "\n".join(prompt_parts)


class CodeAnalyzer:
    """
    Code Analyzer for line-level code quality analysis.
    
    Uses language plugins to parse files and extract context, then uses LLM
    to analyze each modified line for potential issues.
    """
    
    def __init__(self, plugin_manager: PluginManager, llm_client: Optional[LLMClient] = None):
        """
        Initialize Code Analyzer.
        
        Args:
            plugin_manager: PluginManager instance for language-specific analysis
            llm_client: Optional LLMClient instance (will be created if not provided)
        """
        self.plugin_manager = plugin_manager
        self.llm_client = llm_client if llm_client is not None else LLMClient()
        self._batch_size = 5  # Number of concurrent LLM requests
    
    async def analyze_file(
        self,
        file_change: FileChange,
    ) -> List[LineComment]:
        """
        Analyze a single file and return line-level comments.
        
        Args:
            file_change: FileChange object with file content and changes
            
        Returns:
            List of LineComment objects for identified issues
        """
        # Get plugin for file
        plugin = self.plugin_manager.get_plugin_for_file(file_change.file_path)
        if not plugin:
            logger.warning(f"No plugin found for {file_change.file_path}, skipping")
            return []
        
        # Skip deleted files
        if file_change.change_type == "delete":
            logger.debug(f"Skipping deleted file: {file_change.file_path}")
            return []
        
        # Parse file to get AST
        try:
            ast = await self.parse_file(
                file_change.file_path,
                file_change.target_content or "",
                plugin
            )
        except Exception as e:
            logger.error(f"Failed to parse {file_change.file_path}: {e}", exc_info=True)
            return []
        
        # Get analysis rules for this language
        try:
            rules = await plugin.get_analysis_rules()
        except Exception as e:
            logger.error(f"Failed to get analysis rules for {plugin.language_name}: {e}")
            return []
        
        # Analyze modified and added lines
        lines_to_analyze = file_change.modified_lines + file_change.added_lines
        
        if not lines_to_analyze:
            logger.debug(f"No lines to analyze in {file_change.file_path}")
            return []
        
        logger.info(
            f"Analyzing {len(lines_to_analyze)} lines in {file_change.file_path} "
            f"with {len(rules)} rules"
        )
        
        # Analyze lines in batches for efficiency
        comments = []
        for i in range(0, len(lines_to_analyze), self._batch_size):
            batch = lines_to_analyze[i:i + self._batch_size]
            batch_comments = await self._analyze_line_batch(
                batch,
                file_change,
                ast,
                rules,
                plugin
            )
            comments.extend(batch_comments)
        
        logger.info(f"Generated {len(comments)} comments for {file_change.file_path}")
        return comments
    
    async def parse_file(
        self,
        file_path: str,
        content: str,
        plugin=None,
    ) -> ASTNode:
        """
        Parse file content into AST.
        
        Args:
            file_path: Path to the file
            content: File content as string
            plugin: Optional LanguagePlugin instance (will be auto-detected if not provided)
            
        Returns:
            ASTNode representing the parsed AST
            
        Raises:
            ValueError: If no plugin found for file
            Exception: If parsing fails
        """
        if plugin is None:
            plugin = self.plugin_manager.get_plugin_for_file(file_path)
            if not plugin:
                raise ValueError(f"No plugin found for file: {file_path}")
        
        try:
            ast = await plugin.parse_file(file_path, content)
            logger.debug(f"Successfully parsed {file_path}")
            return ast
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}", exc_info=True)
            raise
    
    async def analyze_line(
        self,
        line_content: str,
        line_number: int,
        file_change: FileChange,
        ast: ASTNode,
        rule: AnalysisRule,
        plugin,
    ) -> Optional[LineComment]:
        """
        Analyze a single line of code.
        
        Args:
            line_content: The line of code to analyze
            line_number: Line number in the file
            file_change: FileChange object containing file context
            ast: Parsed AST of the file
            rule: Analysis rule to apply
            plugin: LanguagePlugin instance
            
        Returns:
            LineComment if issue found, None otherwise
        """
        try:
            # Extract context for the line
            context = await plugin.extract_context(
                line_number,
                ast,
                file_change.target_content or ""
            )
            
            # Analyze with LLM
            analysis_result = await self.llm_client.analyze_code(
                line_content,
                context,
                rule
            )
            
            if not analysis_result:
                return None
            
            # Parse LLM response and create comment
            # Try to extract suggestion from the response
            suggestion = None
            message = analysis_result
            
            # Simple heuristic: if response contains "Suggestion:" or similar
            if "suggestion:" in analysis_result.lower():
                parts = analysis_result.split("Suggestion:", 1)
                if len(parts) == 2:
                    message = parts[0].strip()
                    suggestion = parts[1].strip()
            elif "fix:" in analysis_result.lower():
                parts = analysis_result.split("Fix:", 1)
                if len(parts) == 2:
                    message = parts[0].strip()
                    suggestion = parts[1].strip()
            
            return LineComment(
                file_path=file_change.file_path,
                line_number=line_number,
                severity=rule.severity,
                category=rule.category,
                message=message,
                suggestion=suggestion,
            )
            
        except Exception as e:
            logger.error(
                f"Failed to analyze line {line_number} in {file_change.file_path}: {e}",
                exc_info=True
            )
            return None
    
    async def _analyze_line_batch(
        self,
        lines: List,
        file_change: FileChange,
        ast: ASTNode,
        rules: List[AnalysisRule],
        plugin,
    ) -> List[LineComment]:
        """
        Analyze a batch of lines concurrently.
        
        Args:
            lines: List of LineChange objects to analyze
            file_change: FileChange object
            ast: Parsed AST
            rules: List of analysis rules
            plugin: LanguagePlugin instance
            
        Returns:
            List of LineComment objects
        """
        tasks = []
        
        for line_change in lines:
            for rule in rules:
                task = self.analyze_line(
                    line_change.content,
                    line_change.line_number,
                    file_change,
                    ast,
                    rule,
                    plugin
                )
                tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None values and exceptions
        comments = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
            elif result is not None:
                comments.append(result)
        
        return comments
