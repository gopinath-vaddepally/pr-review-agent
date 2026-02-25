"""
Basic tests for Angular plugin functionality.

Tests the core functionality of the Angular plugin including:
- Plugin initialization
- File parsing
- Context extraction
- Decorator detection
"""

import pytest
from pathlib import Path
from plugins.angular.plugin import AngularPlugin


@pytest.fixture
def angular_plugin():
    """Create an Angular plugin instance."""
    return AngularPlugin()


@pytest.fixture
def sample_angular_component():
    """Sample Angular component code."""
    return """
import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-test',
  templateUrl: './test.component.html',
  styleUrls: ['./test.component.css']
})
export class TestComponent implements OnInit {
  title: string = 'Test Component';
  data$: Observable<any>;

  constructor() {}

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    // Load data logic
  }
}
"""


@pytest.fixture
def sample_angular_service():
    """Sample Angular service code."""
    return """
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class DataService {
  private apiUrl = 'https://api.example.com';

  constructor(private http: HttpClient) {}

  getData(): Observable<any> {
    return this.http.get(this.apiUrl);
  }
}
"""


class TestAngularPluginBasic:
    """Test basic Angular plugin functionality."""
    
    def test_plugin_initialization(self, angular_plugin):
        """Test that the plugin initializes correctly."""
        assert angular_plugin.language_name == "angular"
        assert ".ts" in angular_plugin.file_extensions
        assert ".component.ts" in angular_plugin.file_extensions
        assert ".service.ts" in angular_plugin.file_extensions
    
    @pytest.mark.asyncio
    async def test_parse_component_file(self, angular_plugin, sample_angular_component):
        """Test parsing an Angular component file."""
        ast = await angular_plugin.parse_file("test.component.ts", sample_angular_component)
        
        assert ast is not None
        assert ast.node_type == "program"
        assert len(ast.children) > 0
    
    @pytest.mark.asyncio
    async def test_parse_service_file(self, angular_plugin, sample_angular_service):
        """Test parsing an Angular service file."""
        ast = await angular_plugin.parse_file("data.service.ts", sample_angular_service)
        
        assert ast is not None
        assert ast.node_type == "program"
        assert len(ast.children) > 0
    
    @pytest.mark.asyncio
    async def test_extract_context_from_component(self, angular_plugin, sample_angular_component):
        """Test extracting context from a component method."""
        ast = await angular_plugin.parse_file("test.component.ts", sample_angular_component)
        
        # Extract context for line in ngOnInit method (around line 15)
        context = await angular_plugin.extract_context(15, ast, sample_angular_component)
        
        assert context.language == "angular"
        assert context.line_number == 15
        assert context.enclosing_class == "TestComponent"
        assert len(context.imports) > 0
        assert len(context.surrounding_lines) > 0
    
    @pytest.mark.asyncio
    async def test_detect_component_decorator(self, angular_plugin, sample_angular_component):
        """Test detecting @Component decorator."""
        ast = await angular_plugin.parse_file("test.component.ts", sample_angular_component)
        
        # Check if Component decorator is detected
        has_component = angular_plugin._has_decorator(ast, "Component")
        assert has_component is True
    
    @pytest.mark.asyncio
    async def test_detect_injectable_decorator(self, angular_plugin, sample_angular_service):
        """Test detecting @Injectable decorator."""
        ast = await angular_plugin.parse_file("data.service.ts", sample_angular_service)
        
        # Check if Injectable decorator is detected
        has_injectable = angular_plugin._has_decorator(ast, "Injectable")
        assert has_injectable is True
    
    @pytest.mark.asyncio
    async def test_detect_observable_usage(self, angular_plugin, sample_angular_service):
        """Test detecting Observable usage."""
        ast = await angular_plugin.parse_file("data.service.ts", sample_angular_service)
        
        # Check if Observable usage is detected
        uses_observables = angular_plugin._uses_observables(ast)
        assert uses_observables is True
    
    @pytest.mark.asyncio
    async def test_get_analysis_rules(self, angular_plugin):
        """Test getting Angular-specific analysis rules."""
        rules = await angular_plugin.get_analysis_rules()
        
        assert len(rules) > 0
        
        # Check for specific rules
        rule_names = [rule.name for rule in rules]
        assert "unsubscribe_observables" in rule_names
        assert "dependency_injection" in rule_names
        assert "rxjs_best_practices" in rule_names
    
    @pytest.mark.asyncio
    async def test_detect_patterns_component(self, angular_plugin, sample_angular_component):
        """Test detecting Angular component pattern."""
        ast = await angular_plugin.parse_file("test.component.ts", sample_angular_component)
        
        patterns = await angular_plugin.detect_patterns(ast)
        
        assert len(patterns) > 0
        pattern_names = [p.pattern_name for p in patterns]
        assert "Component" in pattern_names
        assert "Observable" in pattern_names
    
    @pytest.mark.asyncio
    async def test_detect_patterns_service(self, angular_plugin, sample_angular_service):
        """Test detecting Angular service pattern."""
        ast = await angular_plugin.parse_file("data.service.ts", sample_angular_service)
        
        patterns = await angular_plugin.detect_patterns(ast)
        
        assert len(patterns) > 0
        pattern_names = [p.pattern_name for p in patterns]
        assert "Service" in pattern_names
        assert "Observable" in pattern_names
    
    @pytest.mark.asyncio
    async def test_extract_imports(self, angular_plugin, sample_angular_component):
        """Test extracting import statements."""
        ast = await angular_plugin.parse_file("test.component.ts", sample_angular_component)
        
        imports = angular_plugin._extract_imports(ast)
        
        assert len(imports) > 0
        # Check that imports contain expected modules
        import_text = " ".join(imports)
        assert "@angular/core" in import_text or "Component" in import_text
    
    @pytest.mark.asyncio
    async def test_extract_class_name(self, angular_plugin, sample_angular_component):
        """Test extracting class name from AST."""
        ast = await angular_plugin.parse_file("test.component.ts", sample_angular_component)
        
        # Find the class declaration
        class_node = angular_plugin._find_enclosing_node(ast, 10, "class_declaration")
        
        assert class_node is not None
        
        class_name = angular_plugin._extract_class_name(class_node)
        assert class_name == "TestComponent"
