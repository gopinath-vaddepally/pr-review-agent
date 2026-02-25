"""
Java Language Plugin for code analysis.

This plugin provides Java-specific code parsing, context extraction,
and analysis rule definitions using tree-sitter-java.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import tree_sitter
import yaml

from plugins.base import LanguagePlugin
from app.models.analysis import (
    ASTNode,
    CodeContext,
    AnalysisRule,
    CodeIssue,
    DesignPattern
)
from app.models.comment import CommentSeverity, CommentCategory

logger = logging.getLogger(__name__)


class JavaPlugin(LanguagePlugin):
    """Java language analysis plugin using tree-sitter."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the Java plugin.
        
        Args:
            config_path: Path to config.yaml file. If None, uses default location.
        """
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        # Initialize tree-sitter parser
        self._parser = tree_sitter.Parser()
        
        # Determine library path based on platform
        import sys
        if sys.platform == "darwin":
            lib_extension = "dylib"
        elif sys.platform == "win32":
            lib_extension = "dll"
        else:
            lib_extension = "so"
        
        lib_path = Path("build") / f"languages.{lib_extension}"
        
        if not lib_path.exists():
            raise FileNotFoundError(
                f"Tree-sitter library not found at {lib_path}. "
                "Please run build_grammars.py first."
            )
        
        # Load Java language
        java_language = tree_sitter.Language(str(lib_path), 'java')
        self._parser.set_language(java_language)
        
        logger.info("Java plugin initialized successfully")
    
    @property
    def language_name(self) -> str:
        """Return the language name."""
        return "java"
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return self._config.get('file_extensions', ['.java'])
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """
        Parse Java file using tree-sitter-java.
        
        Args:
            file_path: Path to the file being parsed
            content: File content as string
            
        Returns:
            ASTNode representing the root of the parsed AST
            
        Raises:
            ValueError: If the file cannot be parsed
        """
        try:
            # Parse the content
            tree = self._parser.parse(bytes(content, "utf8"))
            
            if tree.root_node is None:
                raise ValueError(f"Failed to parse Java file: {file_path}")
            
            # Convert tree-sitter node to our ASTNode model
            ast_node = self._convert_to_ast_node(tree.root_node, content)
            
            logger.debug(f"Successfully parsed Java file: {file_path}")
            return ast_node
            
        except Exception as e:
            logger.error(f"Error parsing Java file {file_path}: {e}")
            raise ValueError(f"Failed to parse Java file: {e}")
    
    def _convert_to_ast_node(
        self, 
        ts_node: tree_sitter.Node, 
        content: str
    ) -> ASTNode:
        """
        Convert tree-sitter Node to ASTNode model.
        
        Args:
            ts_node: tree-sitter Node
            content: Original file content
            
        Returns:
            ASTNode model instance
        """
        # Extract text for the node
        node_text = content[ts_node.start_byte:ts_node.end_byte]
        
        # Recursively convert children
        children = [
            self._convert_to_ast_node(child, content)
            for child in ts_node.children
        ]
        
        return ASTNode(
            node_type=ts_node.type,
            start_line=ts_node.start_point[0] + 1,  # Convert to 1-indexed
            end_line=ts_node.end_point[0] + 1,
            start_column=ts_node.start_point[1],
            end_column=ts_node.end_point[1],
            children=children,
            text=node_text if len(node_text) < 1000 else node_text[:1000] + "..."
        )
    
    async def extract_context(
        self, 
        line_number: int, 
        ast: ASTNode, 
        file_content: str
    ) -> CodeContext:
        """
        Extract Java-specific context including class, method, and imports.
        
        Args:
            line_number: Line number to extract context for (1-indexed)
            ast: Parsed AST of the file
            file_content: Complete file content
            
        Returns:
            CodeContext containing relevant contextual information
        """
        # Find enclosing class
        enclosing_class = self._find_enclosing_node(
            ast, line_number, "class_declaration"
        )
        
        # Find enclosing method
        enclosing_method = self._find_enclosing_node(
            ast, line_number, "method_declaration"
        )
        
        # Extract imports
        imports = self._extract_imports(ast)
        
        # Extract method signature if method found
        method_signature = None
        if enclosing_method:
            method_signature = self._extract_method_signature(enclosing_method)
        
        # Get surrounding lines
        surrounding_lines = self._get_surrounding_lines(file_content, line_number, 3)
        
        # Extract class name
        class_name = None
        if enclosing_class:
            class_name = self._extract_class_name(enclosing_class)
        
        return CodeContext(
            language="java",
            file_path="",  # Will be set by caller
            line_number=line_number,
            enclosing_class=class_name,
            enclosing_method=method_signature,
            imports=imports,
            surrounding_lines=surrounding_lines
        )
    
    def _find_enclosing_node(
        self, 
        ast: ASTNode, 
        line_number: int, 
        node_type: str
    ) -> Optional[ASTNode]:
        """
        Find the most specific (innermost) enclosing node of a specific type for a given line.
        
        Args:
            ast: Root AST node
            line_number: Target line number (1-indexed)
            node_type: Type of node to find (e.g., 'class_declaration')
            
        Returns:
            ASTNode if found, None otherwise
        """
        # First, recursively search children to find the most specific match
        for child in ast.children:
            result = self._find_enclosing_node(child, line_number, node_type)
            if result:
                return result
        
        # If no child matched, check if current node matches and contains the line
        if (ast.node_type == node_type and 
            ast.start_line <= line_number <= ast.end_line):
            return ast
        
        return None
    
    def _extract_imports(self, ast: ASTNode) -> List[str]:
        """
        Extract import statements from the AST.
        
        Args:
            ast: Root AST node
            
        Returns:
            List of import statement strings
        """
        imports = []
        
        def collect_imports(node: ASTNode):
            if node.node_type == "import_declaration":
                # Extract the import text
                if node.text:
                    imports.append(node.text.strip())
            
            # Recursively check children
            for child in node.children:
                collect_imports(child)
        
        collect_imports(ast)
        return imports
    
    def _extract_method_signature(self, method_node: ASTNode) -> Optional[str]:
        """
        Extract method signature from method declaration node.
        
        Args:
            method_node: Method declaration AST node
            
        Returns:
            Method signature string or None
        """
        if not method_node or method_node.node_type != "method_declaration":
            return None
        
        # Look for method name and parameters
        method_name = None
        parameters = None
        
        for child in method_node.children:
            if child.node_type == "identifier":
                method_name = child.text
            elif child.node_type == "formal_parameters":
                parameters = child.text
        
        if method_name:
            params = parameters if parameters else "()"
            return f"{method_name}{params}"
        
        return None
    
    def _extract_class_name(self, class_node: ASTNode) -> Optional[str]:
        """
        Extract class name from class declaration node.
        
        Args:
            class_node: Class declaration AST node
            
        Returns:
            Class name string or None
        """
        if not class_node or class_node.node_type != "class_declaration":
            return None
        
        # Look for identifier child
        for child in class_node.children:
            if child.node_type == "identifier":
                return child.text
        
        return None
    
    def _get_surrounding_lines(
        self, 
        content: str, 
        line_number: int, 
        context_size: int = 3
    ) -> List[str]:
        """
        Get lines surrounding the target line.
        
        Args:
            content: File content
            line_number: Target line number (1-indexed)
            context_size: Number of lines before and after to include
            
        Returns:
            List of surrounding line strings
        """
        lines = content.split('\n')
        
        # Calculate range (convert to 0-indexed)
        start = max(0, line_number - context_size - 1)
        end = min(len(lines), line_number + context_size)
        
        return lines[start:end]
    
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        """
        Return Java-specific analysis rules with detailed LLM prompts.
        
        Returns:
            List of AnalysisRule objects
        """
        rules = []
        
        # Get rule configurations
        rule_names = self._config.get('analysis_rules', [])
        llm_prompts = self._config.get('llm_prompts', {})
        
        # Define rules based on configuration
        # Use detailed prompts from config if available, otherwise use defaults
        rule_definitions = {
            'avoid_null_pointer': AnalysisRule(
                name='avoid_null_pointer',
                category=CommentCategory.BUG,
                severity=CommentSeverity.ERROR,
                pattern='Potential null pointer dereference',
                llm_prompt=llm_prompts.get('avoid_null_pointer', 
                    'Check if this Java code properly handles null values. '
                    'Look for potential NullPointerException risks.')
            ),
            'resource_leak': AnalysisRule(
                name='resource_leak',
                category=CommentCategory.BUG,
                severity=CommentSeverity.WARNING,
                pattern='Resource not closed in try-with-resources',
                llm_prompt=llm_prompts.get('resource_leak',
                    'Check if Java resources (streams, connections, readers) '
                    'are properly closed using try-with-resources or finally blocks.')
            ),
            'exception_handling': AnalysisRule(
                name='exception_handling',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.WARNING,
                pattern='Empty catch block or generic exception catching',
                llm_prompt=llm_prompts.get('exception_handling',
                    'Check if Java exception handling follows best practices. '
                    'Avoid empty catch blocks and catching generic Exception.')
            ),
            'naming_conventions': AnalysisRule(
                name='naming_conventions',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern='Naming convention violation',
                llm_prompt=llm_prompts.get('naming_conventions',
                    'Check if Java naming conventions are followed: '
                    'classes (PascalCase), methods (camelCase), constants (UPPER_SNAKE_CASE).')
            ),
            'code_complexity': AnalysisRule(
                name='code_complexity',
                category=CommentCategory.CODE_SMELL,
                severity=CommentSeverity.WARNING,
                pattern='High code complexity',
                llm_prompt=llm_prompts.get('code_complexity',
                    'Check for code complexity issues: long methods, deep nesting, '
                    'high cyclomatic complexity.')
            ),
            'unused_imports': AnalysisRule(
                name='unused_imports',
                category=CommentCategory.CODE_SMELL,
                severity=CommentSeverity.INFO,
                pattern='Unused import statement',
                llm_prompt=llm_prompts.get('unused_imports',
                    'Check if import statements are actually used in the code.')
            ),
            'magic_numbers': AnalysisRule(
                name='magic_numbers',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern='Magic number without explanation',
                llm_prompt=llm_prompts.get('magic_numbers',
                    'Check for magic numbers that should be named constants.')
            ),
            'long_methods': AnalysisRule(
                name='long_methods',
                category=CommentCategory.CODE_SMELL,
                severity=CommentSeverity.WARNING,
                pattern='Method is too long',
                llm_prompt=llm_prompts.get('long_methods',
                    'Check if method exceeds recommended length (50 lines). '
                    'Consider breaking into smaller methods.')
            ),
        }
        
        # Add configured rules
        for rule_name in rule_names:
            if rule_name in rule_definitions:
                rules.append(rule_definitions[rule_name])
        
        return rules
    
    async def format_suggestion(
        self, 
        issue: CodeIssue, 
        context: CodeContext
    ) -> str:
        """
        Format code suggestion in Java syntax.
        
        Args:
            issue: Identified code issue
            context: Context where the issue was found
            
        Returns:
            Formatted suggestion string with code examples
        """
        # Basic formatting - can be enhanced with more sophisticated templates
        suggestion = f"{issue.message}\n\n"
        
        if context.enclosing_class:
            suggestion += f"In class: {context.enclosing_class}\n"
        
        if context.enclosing_method:
            suggestion += f"In method: {context.enclosing_method}\n"
        
        suggestion += f"\nConsider reviewing the code at line {issue.line_number}."
        
        return suggestion
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """
        Detect Java design patterns (Singleton, Factory, Builder, etc.).
        
        Args:
            ast: Parsed AST of the file
            
        Returns:
            List of detected DesignPattern objects
        """
        patterns = []
        
        # Detect Singleton pattern
        if self._is_singleton_pattern(ast):
            patterns.append(DesignPattern(
                pattern_name="Singleton",
                pattern_type="creational",
                file_paths=[],  # Will be set by caller
                description="Singleton pattern detected with private constructor and static instance"
            ))
        
        # Detect Factory pattern
        if self._is_factory_pattern(ast):
            patterns.append(DesignPattern(
                pattern_name="Factory",
                pattern_type="creational",
                file_paths=[],
                description="Factory pattern detected with factory method for object creation"
            ))
        
        # Detect Builder pattern
        if self._is_builder_pattern(ast):
            patterns.append(DesignPattern(
                pattern_name="Builder",
                pattern_type="creational",
                file_paths=[],
                description="Builder pattern detected with fluent interface for object construction"
            ))
        
        return patterns
    
    def _is_singleton_pattern(self, ast: ASTNode) -> bool:
        """
        Check if the AST represents a Singleton pattern.
        
        A Singleton typically has:
        - Private static instance field
        - Private constructor
        - Public static getInstance() method
        """
        has_private_static_instance = False
        has_private_constructor = False
        has_get_instance = False
        
        def check_node(node: ASTNode):
            nonlocal has_private_static_instance, has_private_constructor, has_get_instance
            
            # Check for private static field
            if node.node_type == "field_declaration":
                if node.text and "private" in node.text and "static" in node.text:
                    has_private_static_instance = True
            
            # Check for private constructor
            if node.node_type == "constructor_declaration":
                if node.text and "private" in node.text:
                    has_private_constructor = True
            
            # Check for getInstance method
            if node.node_type == "method_declaration":
                if node.text and "getInstance" in node.text and "static" in node.text:
                    has_get_instance = True
            
            for child in node.children:
                check_node(child)
        
        check_node(ast)
        
        return has_private_static_instance and has_private_constructor and has_get_instance
    
    def _is_factory_pattern(self, ast: ASTNode) -> bool:
        """
        Check if the AST represents a Factory pattern.
        
        A Factory typically has:
        - Method name containing "create" or "factory"
        - Returns an interface or abstract class type
        """
        def check_node(node: ASTNode) -> bool:
            if node.node_type == "method_declaration":
                if node.text:
                    text_lower = node.text.lower()
                    if "create" in text_lower or "factory" in text_lower:
                        return True
            
            for child in node.children:
                if check_node(child):
                    return True
            
            return False
        
        return check_node(ast)
    
    def _is_builder_pattern(self, ast: ASTNode) -> bool:
        """
        Check if the AST represents a Builder pattern.
        
        A Builder typically has:
        - Inner static Builder class
        - Methods that return 'this' (fluent interface)
        - build() method
        """
        has_builder_class = False
        has_build_method = False
        
        def check_node(node: ASTNode):
            nonlocal has_builder_class, has_build_method
            
            # Check for Builder class
            if node.node_type == "class_declaration":
                if node.text and "Builder" in node.text:
                    has_builder_class = True
            
            # Check for build method
            if node.node_type == "method_declaration":
                if node.text and "build()" in node.text:
                    has_build_method = True
            
            for child in node.children:
                check_node(child)
        
        check_node(ast)
        
        return has_builder_class and has_build_method
