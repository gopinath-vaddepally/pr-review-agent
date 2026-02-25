"""
Data models for code analysis components.

This module defines models used by language plugins and analyzers for
code context, analysis rules, and detected issues.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.comment import CommentSeverity, CommentCategory
from app.models.ast_node import ASTNode


class CodeContext(BaseModel):
    """Context information for a specific line of code."""
    
    language: str = Field(..., description="Programming language")
    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Line number (1-indexed)")
    enclosing_class: Optional[str] = Field(None, description="Name of enclosing class")
    enclosing_method: Optional[str] = Field(None, description="Signature of enclosing method")
    imports: List[str] = Field(default_factory=list, description="Import statements")
    decorators: List[str] = Field(default_factory=list, description="Decorators (for languages that support them)")
    surrounding_lines: List[str] = Field(default_factory=list, description="Lines surrounding the target line")


class AnalysisRule(BaseModel):
    """Defines a rule for code analysis."""
    
    name: str = Field(..., description="Unique rule identifier")
    category: CommentCategory = Field(..., description="Category of issue this rule detects")
    severity: CommentSeverity = Field(..., description="Severity level of issues found by this rule")
    pattern: str = Field(..., description="Description of the pattern to detect")
    llm_prompt: str = Field(..., description="Prompt template for LLM analysis")


class CodeIssue(BaseModel):
    """Represents a detected code issue."""
    
    rule_name: str = Field(..., description="Name of the rule that detected this issue")
    message: str = Field(..., description="Description of the issue")
    severity: CommentSeverity = Field(..., description="Severity level")
    category: CommentCategory = Field(..., description="Issue category")
    line_number: int = Field(..., description="Line number where issue was found")
    file_path: str = Field(..., description="Path to the file")


class DesignPattern(BaseModel):
    """Represents a detected design pattern."""
    
    pattern_name: str = Field(..., description="Name of the design pattern")
    pattern_type: str = Field(..., description="Type: 'creational', 'structural', or 'behavioral'")
    file_paths: List[str] = Field(..., description="Files where the pattern is implemented")
    description: str = Field(..., description="Description of how the pattern is used")



class SOLIDViolation(BaseModel):
    """Represents a SOLID principle violation."""
    
    principle: str = Field(..., description="SOLID principle violated: 'SRP', 'OCP', 'LSP', 'ISP', or 'DIP'")
    description: str = Field(..., description="Description of the violation")
    file_path: str = Field(..., description="Path to the file where violation was found")
    suggestion: str = Field(..., description="Suggestion for fixing the violation")


class ArchitecturalIssue(BaseModel):
    """Represents an architectural issue."""
    
    issue_type: str = Field(..., description="Type of issue: 'layering_violation', 'circular_dependency', etc.")
    description: str = Field(..., description="Description of the architectural issue")
    affected_files: List[str] = Field(..., description="Files affected by this issue")
    suggestion: str = Field(..., description="Suggestion for resolving the issue")
