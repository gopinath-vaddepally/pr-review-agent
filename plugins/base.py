"""
Base interface for language-specific analysis plugins.

This module defines the abstract base class that all language plugins must implement
to provide language-specific code analysis capabilities.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from app.models.analysis import ASTNode, CodeContext, AnalysisRule, CodeIssue, DesignPattern


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
        """
        Parse file content into AST using language-specific parser.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            ASTNode representing the root of the parsed AST
            
        Raises:
            ParseError: If the file cannot be parsed
        """
        pass
    
    @abstractmethod
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        """
        Extract relevant context for a specific line.
        
        This includes enclosing class, method, imports, and surrounding lines
        that provide context for analysis.
        
        Args:
            line_number: Line number to extract context for (1-indexed)
            ast: Parsed AST of the file
            file_content: Complete file content
            
        Returns:
            CodeContext containing relevant contextual information
        """
        pass
    
    @abstractmethod
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        """
        Return language-specific analysis rules.
        
        Rules define what to look for in code analysis, including:
        - Code smells
        - Potential bugs
        - Security vulnerabilities
        - Best practice violations
        
        Returns:
            List of AnalysisRule objects
        """
        pass
    
    @abstractmethod
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        """
        Format code suggestion in language-specific syntax.
        
        Args:
            issue: Identified code issue
            context: Context where the issue was found
            
        Returns:
            Formatted suggestion string with code examples
        """
        pass
    
    @abstractmethod
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """
        Detect language-specific design patterns.
        
        Args:
            ast: Parsed AST of the file
            
        Returns:
            List of detected DesignPattern objects
        """
        pass
