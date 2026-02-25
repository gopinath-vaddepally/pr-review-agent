"""
Angular/TypeScript Language Plugin for code analysis.

This plugin provides Angular-specific code parsing, context extraction,
and analysis rule definitions using tree-sitter-typescript.
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


class AngularPlugin(LanguagePlugin):
    """Angular/TypeScript language analysis plugin using tree-sitter."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the Angular plugin.
        
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
        
        # Load TypeScript language
        typescript_language = tree_sitter.Language(str(lib_path), 'typescript')
        self._parser.set_language(typescript_language)
        
        logger.info("Angular plugin initialized successfully")
    
    @property
    def language_name(self) -> str:
        """Return the language name."""
        return "angular"
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return self._config.get('file_extensions', ['.ts', '.component.ts', '.service.ts'])
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """
        Parse Angular/TypeScript file using tree-sitter-typescript.
        
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
                raise ValueError(f"Failed to parse Angular/TypeScript file: {file_path}")
            
            # Convert tree-sitter node to our ASTNode model
            ast_node = self._convert_to_ast_node(tree.root_node, content)
            
            logger.debug(f"Successfully parsed Angular/TypeScript file: {file_path}")
            return ast_node
            
        except Exception as e:
            logger.error(f"Error parsing Angular/TypeScript file {file_path}: {e}")
            raise ValueError(f"Failed to parse Angular/TypeScript file: {e}")
    
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
        Extract Angular-specific context including component, service, decorators.
        
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
            ast, line_number, "method_definition"
        )
        
        # Extract decorators (@Component, @Injectable, etc.)
        decorators = []
        if enclosing_class:
            decorators = self._extract_decorators(enclosing_class)
        
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
            language="angular",
            file_path="",  # Will be set by caller
            line_number=line_number,
            enclosing_class=class_name,
            enclosing_method=method_signature,
            imports=imports,
            decorators=decorators,
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
    
    def _extract_decorators(self, class_node: ASTNode) -> List[str]:
        """
        Extract decorators from a class node.
        
        Args:
            class_node: Class declaration AST node
            
        Returns:
            List of decorator strings (e.g., ['@Component', '@Injectable'])
        """
        decorators = []
        
        def collect_decorators(node: ASTNode):
            if node.node_type == "decorator":
                # Extract the decorator text
                if node.text:
                    decorators.append(node.text.strip())
            
            # Recursively check children
            for child in node.children:
                collect_decorators(child)
        
        # Look for decorators in the class node and its immediate siblings
        # In TypeScript AST, decorators are typically siblings before the class
        collect_decorators(class_node)
        
        return decorators
    
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
            if node.node_type == "import_statement":
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
        Extract method signature from method definition node.
        
        Args:
            method_node: Method definition AST node
            
        Returns:
            Method signature string or None
        """
        if not method_node or method_node.node_type != "method_definition":
            return None
        
        # Look for method name and parameters
        method_name = None
        parameters = None
        
        for child in method_node.children:
            if child.node_type == "property_identifier":
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
        
        # Look for type_identifier child
        for child in class_node.children:
            if child.node_type == "type_identifier":
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
        Return Angular-specific analysis rules with detailed LLM prompts.
        
        Returns:
            List of AnalysisRule objects
        """
        rules = []
        
        # Get rule configurations
        rule_names = self._config.get('analysis_rules', [])
        llm_prompts = self._config.get('llm_prompts', {})
        
        # Define rules based on configuration
        rule_definitions = {
            'unsubscribe_observables': AnalysisRule(
                name='unsubscribe_observables',
                category=CommentCategory.BUG,
                severity=CommentSeverity.WARNING,
                pattern='Observable subscription without unsubscribe',
                llm_prompt=llm_prompts.get('unsubscribe_observables',
                    'Check if Angular Observable subscriptions are properly unsubscribed. '
                    'Look for subscriptions without takeUntil, async pipe, or ngOnDestroy cleanup.')
            ),
            'change_detection_performance': AnalysisRule(
                name='change_detection_performance',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern='Inefficient change detection strategy',
                llm_prompt=llm_prompts.get('change_detection_performance',
                    'Check if Angular component uses appropriate change detection strategy. '
                    'Consider OnPush strategy for better performance.')
            ),
            'dependency_injection': AnalysisRule(
                name='dependency_injection',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.WARNING,
                pattern='Improper dependency injection usage',
                llm_prompt=llm_prompts.get('dependency_injection',
                    'Check if Angular dependency injection follows best practices. '
                    'Services should be injected via constructor, not created manually.')
            ),
            'template_syntax': AnalysisRule(
                name='template_syntax',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern='Template syntax issues',
                llm_prompt=llm_prompts.get('template_syntax',
                    'Check Angular template syntax for best practices. '
                    'Use structural directives properly, avoid complex expressions in templates.')
            ),
            'rxjs_best_practices': AnalysisRule(
                name='rxjs_best_practices',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.WARNING,
                pattern='RxJS operator misuse',
                llm_prompt=llm_prompts.get('rxjs_best_practices',
                    'Check RxJS usage for best practices. '
                    'Use appropriate operators, avoid nested subscriptions, prefer higher-order operators.')
            ),
            'async_pipe_usage': AnalysisRule(
                name='async_pipe_usage',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern='Manual subscription instead of async pipe',
                llm_prompt=llm_prompts.get('async_pipe_usage',
                    'Check if async pipe could be used instead of manual subscription. '
                    'Async pipe automatically handles subscription lifecycle.')
            ),
            'memory_leaks': AnalysisRule(
                name='memory_leaks',
                category=CommentCategory.BUG,
                severity=CommentSeverity.ERROR,
                pattern='Potential memory leak',
                llm_prompt=llm_prompts.get('memory_leaks',
                    'Check for potential memory leaks in Angular components. '
                    'Look for event listeners, intervals, or subscriptions not cleaned up.')
            ),
            'component_communication': AnalysisRule(
                name='component_communication',
                category=CommentCategory.BEST_PRACTICE,
                severity=CommentSeverity.INFO,
                pattern='Improper component communication',
                llm_prompt=llm_prompts.get('component_communication',
                    'Check component communication patterns. '
                    'Use @Input/@Output for parent-child, services for sibling communication.')
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
        Format code suggestion in TypeScript/Angular syntax.
        
        Args:
            issue: Identified code issue
            context: Context where the issue was found
            
        Returns:
            Formatted suggestion string with code examples
        """
        # Basic formatting - can be enhanced with more sophisticated templates
        suggestion = f"{issue.message}\n\n"
        
        if context.decorators:
            suggestion += f"Decorators: {', '.join(context.decorators)}\n"
        
        if context.enclosing_class:
            suggestion += f"In class: {context.enclosing_class}\n"
        
        if context.enclosing_method:
            suggestion += f"In method: {context.enclosing_method}\n"
        
        suggestion += f"\nConsider reviewing the code at line {issue.line_number}."
        
        return suggestion
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """
        Detect Angular patterns (Service, Component, Directive, etc.).
        
        Args:
            ast: Parsed AST of the file
            
        Returns:
            List of detected DesignPattern objects
        """
        patterns = []
        
        # Detect Service pattern
        if self._has_decorator(ast, "Injectable"):
            patterns.append(DesignPattern(
                pattern_name="Service",
                pattern_type="structural",
                file_paths=[],  # Will be set by caller
                description="Angular Service pattern with @Injectable decorator"
            ))
        
        # Detect Component pattern
        if self._has_decorator(ast, "Component"):
            patterns.append(DesignPattern(
                pattern_name="Component",
                pattern_type="structural",
                file_paths=[],
                description="Angular Component pattern with @Component decorator"
            ))
        
        # Detect Directive pattern
        if self._has_decorator(ast, "Directive"):
            patterns.append(DesignPattern(
                pattern_name="Directive",
                pattern_type="structural",
                file_paths=[],
                description="Angular Directive pattern with @Directive decorator"
            ))
        
        # Detect Pipe pattern
        if self._has_decorator(ast, "Pipe"):
            patterns.append(DesignPattern(
                pattern_name="Pipe",
                pattern_type="structural",
                file_paths=[],
                description="Angular Pipe pattern with @Pipe decorator"
            ))
        
        # Detect Observable pattern usage
        if self._uses_observables(ast):
            patterns.append(DesignPattern(
                pattern_name="Observable",
                pattern_type="behavioral",
                file_paths=[],
                description="RxJS Observable pattern for reactive programming"
            ))
        
        return patterns
    
    def _has_decorator(self, ast: ASTNode, decorator_name: str) -> bool:
        """
        Check if the AST contains a specific decorator.
        
        Args:
            ast: Root AST node
            decorator_name: Name of the decorator to look for (without @)
            
        Returns:
            True if decorator is found, False otherwise
        """
        def check_node(node: ASTNode) -> bool:
            if node.node_type == "decorator":
                if node.text and decorator_name in node.text:
                    return True
            
            for child in node.children:
                if check_node(child):
                    return True
            
            return False
        
        return check_node(ast)
    
    def _uses_observables(self, ast: ASTNode) -> bool:
        """
        Check if the code uses RxJS Observables.
        
        Args:
            ast: Root AST node
            
        Returns:
            True if Observable usage is detected, False otherwise
        """
        def check_node(node: ASTNode) -> bool:
            # Check for Observable type annotations or imports
            if node.text:
                text = node.text
                if "Observable" in text or "Subject" in text or "BehaviorSubject" in text:
                    return True
            
            for child in node.children:
                if check_node(child):
                    return True
            
            return False
        
        return check_node(ast)
