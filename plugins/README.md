# Language Plugin Architecture

This directory contains the language plugin system for the Azure DevOps PR Review Agent. The plugin architecture enables extensible, language-specific code analysis without modifying core components.

## Architecture Overview

The plugin system consists of:

1. **LanguagePlugin Interface** (`base.py`): Abstract base class that all language plugins must implement
2. **PluginManager** (`manager.py`): Manages plugin registration, discovery, and selection
3. **Language Plugins** (subdirectories): Concrete implementations for specific languages

## Plugin Interface

Each language plugin must implement the `LanguagePlugin` interface:

```python
class LanguagePlugin(ABC):
    @property
    def language_name(self) -> str:
        """Return the language name (e.g., 'java', 'angular')"""
    
    @property
    def file_extensions(self) -> List[str]:
        """Return supported file extensions (e.g., ['.java'])"""
    
    async def parse_file(self, file_path: str, content: str) -> ASTNode:
        """Parse file content into AST using tree-sitter"""
    
    async def extract_context(self, line_number: int, ast: ASTNode, file_content: str) -> CodeContext:
        """Extract relevant context for a specific line"""
    
    async def get_analysis_rules(self) -> List[AnalysisRule]:
        """Return language-specific analysis rules"""
    
    async def format_suggestion(self, issue: CodeIssue, context: CodeContext) -> str:
        """Format code suggestion in language-specific syntax"""
    
    async def detect_patterns(self, ast: ASTNode) -> List[DesignPattern]:
        """Detect language-specific design patterns"""
```

## Plugin Configuration

Each plugin directory should contain a `config.yaml` file:

```yaml
name: java
version: 1.0.0
description: Java language analysis plugin

file_extensions:
  - .java

tree_sitter_grammar: tree-sitter-java

analysis_rules:
  - avoid_null_pointer
  - resource_leak
  - exception_handling

llm_prompts:
  system_prompt: |
    You are an expert Java code reviewer...
  
  context_template: |
    File: {file_path}
    Class: {enclosing_class}
    Method: {enclosing_method}
    Line {line_number}: {line_content}

design_patterns:
  - Singleton
  - Factory
  - Builder

rule_configs:
  code_complexity:
    max_method_lines: 50
    max_cyclomatic_complexity: 10
```

## Current Plugins

### Java Plugin (`java/`)
- **Status**: Configuration ready, implementation pending (Task 8.1)
- **Extensions**: `.java`
- **Features**: Null pointer detection, resource leak detection, SOLID principles, design patterns

### Angular Plugin (`angular/`)
- **Status**: Configuration ready, implementation pending (Task 9.1)
- **Extensions**: `.ts`, `.component.ts`, `.service.ts`, `.module.ts`, `.html`
- **Features**: Observable management, change detection, RxJS patterns, Angular best practices

## Using the Plugin Manager

```python
from plugins import PluginManager, LanguagePlugin

# Initialize plugin manager
manager = PluginManager()

# Register plugins
manager.register_plugin(JavaPlugin())
manager.register_plugin(AngularPlugin())

# Get plugin for a file
plugin = manager.get_plugin_for_file("src/Main.java")
if plugin:
    ast = await plugin.parse_file("src/Main.java", content)
    context = await plugin.extract_context(10, ast, content)
    rules = await plugin.get_analysis_rules()

# List supported languages
languages = manager.list_supported_languages()
print(f"Supported languages: {languages}")

# Get statistics
stats = manager.get_statistics()
print(f"Total plugins: {stats['total_plugins']}")
```

## Adding a New Language Plugin

To add support for a new language:

1. **Create plugin directory**: `plugins/your_language/`

2. **Create configuration**: `plugins/your_language/config.yaml`
   ```yaml
   name: your_language
   version: 1.0.0
   file_extensions:
     - .ext
   tree_sitter_grammar: tree-sitter-your-language
   ```

3. **Implement plugin class**: `plugins/your_language/plugin.py`
   ```python
   from plugins.base import LanguagePlugin
   
   class YourLanguagePlugin(LanguagePlugin):
       @property
       def language_name(self) -> str:
           return "your_language"
       
       # Implement remaining interface methods...
   ```

4. **Register plugin**: In your application initialization
   ```python
   manager.register_plugin(YourLanguagePlugin())
   ```

## Design Principles

- **Modularity**: Core components remain unchanged when adding languages
- **Extensibility**: New languages added via plugin implementation
- **Consistency**: All plugins follow same interface contract
- **Maintainability**: Language-specific logic isolated in plugins
- **Testability**: Plugins can be tested independently

## Dependencies

- `pyyaml>=6.0.1`: YAML configuration parsing
- `tree-sitter>=0.20.4`: AST parsing
- Language-specific tree-sitter grammars (built via `build_grammars.py`)

## Testing

Plugin tests are located in `tests/unit/test_plugin_manager.py`. Run tests with:

```bash
pytest tests/unit/test_plugin_manager.py -v
```

## Next Steps

- Task 7.2: Build tree-sitter grammars for Java and TypeScript
- Task 8.1: Implement Java plugin
- Task 9.1: Implement Angular plugin
