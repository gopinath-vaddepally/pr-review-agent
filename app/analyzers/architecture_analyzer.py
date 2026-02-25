"""
Architecture Analyzer component.

Evaluates overall design and architectural patterns using LLM inference.
Analyzes all changed files as a cohesive unit to identify SOLID principle
violations, design patterns, and architectural issues.
"""

import logging
from typing import List, Dict, Optional
import json
from openai import AsyncOpenAI, AsyncAzureOpenAI

from app.models.comment import SummaryComment
from app.models.file_change import FileChange
from app.models.ast_node import ASTNode
from app.models.analysis import SOLIDViolation, DesignPattern, ArchitecturalIssue
from app.config import settings
from app.utils.resilience import CircuitBreaker, create_llm_circuit_breaker

logger = logging.getLogger(__name__)


class ArchitectureAnalyzer:
    """Analyzes overall architecture and design patterns using LLM."""
    
    def __init__(self, circuit_breaker: Optional[CircuitBreaker] = None):
        """Initialize the Architecture Analyzer with LLM client and circuit breaker."""
        # Initialize circuit breaker
        self.circuit_breaker = circuit_breaker or create_llm_circuit_breaker()
        
        if settings.azure_openai_endpoint:
            self._llm_client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-15-preview",
                azure_endpoint=settings.azure_openai_endpoint
            )
            self._model = settings.azure_openai_deployment
        else:
            self._llm_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self._model = "gpt-4"
    
    async def _call_llm_with_circuit_breaker(self, messages: list, max_tokens: int = 2000) -> str:
        """
        Call LLM with circuit breaker protection.
        
        Args:
            messages: List of message dictionaries for the LLM
            max_tokens: Maximum tokens in response
            
        Returns:
            LLM response content
        """
        async def _call():
            response = await self._llm_client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        
        return await self.circuit_breaker.call(_call)
    
    async def analyze_architecture(
        self,
        changed_files: List[FileChange],
        asts: Dict[str, ASTNode]
    ) -> SummaryComment:
        """
        Analyze overall architecture and return summary comment.
        
        Args:
            changed_files: List of changed files with content
            asts: Dictionary mapping file paths to their AST representations
            
        Returns:
            SummaryComment with architectural findings and recommendations
        """
        logger.info(f"Starting architectural analysis for {len(changed_files)} files")
        
        try:
            # Evaluate SOLID principles
            solid_violations = await self.evaluate_solid_principles(changed_files, asts)
            
            # Identify design patterns
            design_patterns = await self.identify_design_patterns(changed_files, asts)
            
            # Detect architectural issues
            architectural_issues = await self.detect_architectural_issues(changed_files, asts)
            
            # Generate summary message
            summary_message = self._generate_summary_message(
                solid_violations,
                design_patterns,
                architectural_issues
            )
            
            # Build SummaryComment
            summary_comment = SummaryComment(
                message=summary_message,
                solid_violations=[v.description for v in solid_violations],
                design_patterns_identified=[p.description for p in design_patterns],
                design_pattern_suggestions=self._generate_pattern_suggestions(changed_files, design_patterns),
                architectural_issues=[i.description for i in architectural_issues]
            )
            
            logger.info(f"Architectural analysis complete: {len(solid_violations)} SOLID violations, "
                       f"{len(design_patterns)} patterns identified, {len(architectural_issues)} issues")
            
            return summary_comment
            
        except Exception as e:
            logger.error(f"Error during architectural analysis: {e}", exc_info=True)
            # Return minimal summary on error
            return SummaryComment(
                message="Architectural analysis encountered an error. Please review manually.",
                solid_violations=[],
                design_patterns_identified=[],
                design_pattern_suggestions=[],
                architectural_issues=[]
            )
    
    async def evaluate_solid_principles(
        self,
        changed_files: List[FileChange],
        asts: Dict[str, ASTNode]
    ) -> List[SOLIDViolation]:
        """
        Evaluate adherence to SOLID principles.
        
        Args:
            changed_files: List of changed files
            asts: Dictionary mapping file paths to ASTs
            
        Returns:
            List of SOLID principle violations
        """
        logger.debug("Evaluating SOLID principles")
        
        # Prepare context for LLM
        files_context = self._prepare_files_context(changed_files)
        
        prompt = f"""Analyze the following code changes for SOLID principle violations.

SOLID Principles:
- SRP (Single Responsibility Principle): A class should have only one reason to change
- OCP (Open-Closed Principle): Software entities should be open for extension but closed for modification
- LSP (Liskov Substitution Principle): Derived classes must be substitutable for their base classes
- ISP (Interface Segregation Principle): Clients should not be forced to depend on interfaces they don't use
- DIP (Dependency Inversion Principle): Depend on abstractions, not concretions

Code Changes:
{files_context}

Identify any SOLID principle violations. For each violation, provide:
1. The principle violated (SRP, OCP, LSP, ISP, or DIP)
2. A clear description of the violation
3. The file path where it occurs
4. A specific suggestion for fixing it

Return your analysis as a JSON array of objects with fields: principle, description, file_path, suggestion.
If no violations are found, return an empty array.
"""
        
        try:
            content = await self._call_llm_with_circuit_breaker(
                messages=[
                    {"role": "system", "content": "You are an expert software architect specializing in SOLID principles and clean code design."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000
            )
            
            violations_data = self._extract_json_from_response(content)
            
            violations = [
                SOLIDViolation(**v) for v in violations_data
                if all(k in v for k in ['principle', 'description', 'file_path', 'suggestion'])
            ]
            
            logger.debug(f"Found {len(violations)} SOLID violations")
            return violations
            
        except Exception as e:
            logger.error(f"Error evaluating SOLID principles: {e}", exc_info=True)
            return []
    
    async def identify_design_patterns(
        self,
        changed_files: List[FileChange],
        asts: Dict[str, ASTNode]
    ) -> List[DesignPattern]:
        """
        Identify design patterns in the code.
        
        Args:
            changed_files: List of changed files
            asts: Dictionary mapping file paths to ASTs
            
        Returns:
            List of identified design patterns
        """
        logger.debug("Identifying design patterns")
        
        files_context = self._prepare_files_context(changed_files)
        
        prompt = f"""Analyze the following code changes to identify design patterns.

Consider these pattern categories:
- Creational: Singleton, Factory, Builder, Prototype, Abstract Factory
- Structural: Adapter, Bridge, Composite, Decorator, Facade, Proxy
- Behavioral: Observer, Strategy, Command, Template Method, Iterator, State

Code Changes:
{files_context}

Identify any design patterns present in the code. For each pattern, provide:
1. The pattern name
2. The pattern type (creational, structural, or behavioral)
3. The file paths where it's implemented
4. A description of how the pattern is used

Return your analysis as a JSON array of objects with fields: pattern_name, pattern_type, file_paths (array), description.
If no patterns are found, return an empty array.
"""
        
        try:
            content = await self._call_llm_with_circuit_breaker(
                messages=[
                    {"role": "system", "content": "You are an expert software architect specializing in design patterns and software architecture."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000
            )
            
            patterns_data = self._extract_json_from_response(content)
            
            patterns = [
                DesignPattern(**p) for p in patterns_data
                if all(k in p for k in ['pattern_name', 'pattern_type', 'file_paths', 'description'])
            ]
            
            logger.debug(f"Identified {len(patterns)} design patterns")
            return patterns
            
        except Exception as e:
            logger.error(f"Error identifying design patterns: {e}", exc_info=True)
            return []
    
    async def detect_architectural_issues(
        self,
        changed_files: List[FileChange],
        asts: Dict[str, ASTNode]
    ) -> List[ArchitecturalIssue]:
        """
        Detect architectural issues like layering violations and circular dependencies.
        
        Args:
            changed_files: List of changed files
            asts: Dictionary mapping file paths to ASTs
            
        Returns:
            List of architectural issues
        """
        logger.debug("Detecting architectural issues")
        
        files_context = self._prepare_files_context(changed_files)
        
        prompt = f"""Analyze the following code changes for architectural issues.

Look for:
- Layering violations (e.g., presentation layer directly accessing data layer)
- Circular dependencies between modules or classes
- Tight coupling between components
- Missing abstraction layers
- Violation of separation of concerns

Code Changes:
{files_context}

Identify any architectural issues. For each issue, provide:
1. The issue type (e.g., layering_violation, circular_dependency, tight_coupling)
2. A clear description of the issue
3. The affected file paths
4. A specific suggestion for resolving it

Return your analysis as a JSON array of objects with fields: issue_type, description, affected_files (array), suggestion.
If no issues are found, return an empty array.
"""
        
        try:
            content = await self._call_llm_with_circuit_breaker(
                messages=[
                    {"role": "system", "content": "You are an expert software architect specializing in software architecture and system design."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000
            )
            
            issues_data = self._extract_json_from_response(content)
            
            issues = [
                ArchitecturalIssue(**i) for i in issues_data
                if all(k in i for k in ['issue_type', 'description', 'affected_files', 'suggestion'])
            ]
            
            logger.debug(f"Detected {len(issues)} architectural issues")
            return issues
            
        except Exception as e:
            logger.error(f"Error detecting architectural issues: {e}", exc_info=True)
            return []
    
    def _prepare_files_context(self, changed_files: List[FileChange]) -> str:
        """
        Prepare a context string with file changes for LLM analysis.
        
        Args:
            changed_files: List of changed files
            
        Returns:
            Formatted string with file contents
        """
        context_parts = []
        
        for file_change in changed_files[:10]:  # Limit to 10 files to avoid token limits
            context_parts.append(f"\n--- File: {file_change.file_path} ---")
            
            if file_change.target_content:
                # Truncate very long files
                content = file_change.target_content
                if len(content) > 3000:
                    content = content[:3000] + "\n... (truncated)"
                context_parts.append(content)
            else:
                context_parts.append("(File content not available)")
        
        if len(changed_files) > 10:
            context_parts.append(f"\n... and {len(changed_files) - 10} more files")
        
        return "\n".join(context_parts)
    
    def _extract_json_from_response(self, content: str) -> List[Dict]:
        """
        Extract JSON array from LLM response, handling markdown code blocks.
        
        Args:
            content: LLM response content
            
        Returns:
            Parsed JSON array
        """
        try:
            # Try direct JSON parsing
            return json.loads(content)
        except json.JSONDecodeError:
            # Try extracting from markdown code block
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
                return json.loads(json_str)
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                json_str = content[start:end].strip()
                return json.loads(json_str)
            else:
                logger.warning("Could not extract JSON from LLM response")
                return []
    
    def _generate_summary_message(
        self,
        solid_violations: List[SOLIDViolation],
        design_patterns: List[DesignPattern],
        architectural_issues: List[ArchitecturalIssue]
    ) -> str:
        """
        Generate a human-readable summary message.
        
        Args:
            solid_violations: List of SOLID violations
            design_patterns: List of identified patterns
            architectural_issues: List of architectural issues
            
        Returns:
            Summary message string
        """
        parts = ["## Architectural Analysis Summary\n"]
        
        if solid_violations:
            parts.append(f"\n### SOLID Principle Violations ({len(solid_violations)})")
            for v in solid_violations:
                parts.append(f"- **{v.principle}**: {v.description}")
        
        if design_patterns:
            parts.append(f"\n### Design Patterns Identified ({len(design_patterns)})")
            for p in design_patterns:
                parts.append(f"- **{p.pattern_name}** ({p.pattern_type}): {p.description}")
        
        if architectural_issues:
            parts.append(f"\n### Architectural Issues ({len(architectural_issues)})")
            for i in architectural_issues:
                parts.append(f"- **{i.issue_type}**: {i.description}")
        
        if not solid_violations and not architectural_issues:
            parts.append("\n✅ No significant architectural issues detected.")
        
        return "\n".join(parts)
    
    def _generate_pattern_suggestions(
        self,
        changed_files: List[FileChange],
        identified_patterns: List[DesignPattern]
    ) -> List[str]:
        """
        Generate suggestions for design patterns that could improve the code.
        
        Args:
            changed_files: List of changed files
            identified_patterns: Already identified patterns
            
        Returns:
            List of pattern suggestions
        """
        # This is a simplified implementation
        # In a full implementation, this would use LLM to suggest patterns
        suggestions = []
        
        # Basic heuristics for pattern suggestions
        pattern_names = {p.pattern_name for p in identified_patterns}
        
        # Check for common scenarios where patterns could help
        for file_change in changed_files:
            if file_change.target_content:
                content = file_change.target_content.lower()
                
                # Suggest Factory if lots of object creation
                if "new " in content and "Factory" not in pattern_names:
                    suggestions.append("Consider using Factory pattern for object creation")
                
                # Suggest Strategy if lots of conditional logic
                if content.count("if ") > 5 and "Strategy" not in pattern_names:
                    suggestions.append("Consider using Strategy pattern to reduce conditional complexity")
        
        return list(set(suggestions))[:3]  # Return up to 3 unique suggestions
