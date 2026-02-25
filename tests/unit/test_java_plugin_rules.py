"""
Unit tests for Java plugin analysis rules and LLM prompts.
"""

import pytest
from pathlib import Path
from plugins.java.plugin import JavaPlugin
from app.models.comment import CommentCategory, CommentSeverity


class TestJavaPluginRules:
    """Test Java plugin analysis rules configuration."""
    
    @pytest.fixture
    def java_plugin(self):
        """Create a Java plugin instance."""
        config_path = Path("plugins/java/config.yaml")
        return JavaPlugin(config_path=config_path)
    
    @pytest.mark.asyncio
    async def test_get_analysis_rules_returns_all_configured_rules(self, java_plugin):
        """Test that all configured rules are returned."""
        rules = await java_plugin.get_analysis_rules()
        
        # Should have 8 rules as configured
        assert len(rules) == 8
        
        # Check rule names
        rule_names = [rule.name for rule in rules]
        expected_rules = [
            'avoid_null_pointer',
            'resource_leak',
            'exception_handling',
            'naming_conventions',
            'code_complexity',
            'unused_imports',
            'magic_numbers',
            'long_methods'
        ]
        
        for expected_rule in expected_rules:
            assert expected_rule in rule_names
    
    @pytest.mark.asyncio
    async def test_null_pointer_rule_has_detailed_prompt(self, java_plugin):
        """Test that null pointer rule has detailed LLM prompt."""
        rules = await java_plugin.get_analysis_rules()
        
        null_pointer_rule = next(
            (r for r in rules if r.name == 'avoid_null_pointer'),
            None
        )
        
        assert null_pointer_rule is not None
        assert null_pointer_rule.category == CommentCategory.BUG
        assert null_pointer_rule.severity == CommentSeverity.ERROR
        
        # Check that the prompt is detailed (not just the default)
        assert 'Dereferencing variables' in null_pointer_rule.llm_prompt
        assert 'null checks' in null_pointer_rule.llm_prompt
        assert 'Optional usage' in null_pointer_rule.llm_prompt
    
    @pytest.mark.asyncio
    async def test_resource_leak_rule_has_detailed_prompt(self, java_plugin):
        """Test that resource leak rule has detailed LLM prompt."""
        rules = await java_plugin.get_analysis_rules()
        
        resource_leak_rule = next(
            (r for r in rules if r.name == 'resource_leak'),
            None
        )
        
        assert resource_leak_rule is not None
        assert resource_leak_rule.category == CommentCategory.BUG
        assert resource_leak_rule.severity == CommentSeverity.WARNING
        
        # Check that the prompt is detailed
        assert 'try-with-resources' in resource_leak_rule.llm_prompt
        assert 'InputStream' in resource_leak_rule.llm_prompt
        assert 'Connection' in resource_leak_rule.llm_prompt
    
    @pytest.mark.asyncio
    async def test_exception_handling_rule_has_detailed_prompt(self, java_plugin):
        """Test that exception handling rule has detailed LLM prompt."""
        rules = await java_plugin.get_analysis_rules()
        
        exception_rule = next(
            (r for r in rules if r.name == 'exception_handling'),
            None
        )
        
        assert exception_rule is not None
        assert exception_rule.category == CommentCategory.BEST_PRACTICE
        assert exception_rule.severity == CommentSeverity.WARNING
        
        # Check that the prompt is detailed
        assert 'Empty catch blocks' in exception_rule.llm_prompt
        assert 'generic Exception' in exception_rule.llm_prompt
        assert 'Throwable' in exception_rule.llm_prompt
    
    @pytest.mark.asyncio
    async def test_naming_conventions_rule_has_detailed_prompt(self, java_plugin):
        """Test that naming conventions rule has detailed LLM prompt."""
        rules = await java_plugin.get_analysis_rules()
        
        naming_rule = next(
            (r for r in rules if r.name == 'naming_conventions'),
            None
        )
        
        assert naming_rule is not None
        assert naming_rule.category == CommentCategory.BEST_PRACTICE
        assert naming_rule.severity == CommentSeverity.INFO
        
        # Check that the prompt is detailed
        assert 'PascalCase' in naming_rule.llm_prompt
        assert 'camelCase' in naming_rule.llm_prompt
        assert 'UPPER_SNAKE_CASE' in naming_rule.llm_prompt
    
    @pytest.mark.asyncio
    async def test_all_rules_have_required_fields(self, java_plugin):
        """Test that all rules have required fields populated."""
        rules = await java_plugin.get_analysis_rules()
        
        for rule in rules:
            assert rule.name is not None and rule.name != ""
            assert rule.category is not None
            assert rule.severity is not None
            assert rule.pattern is not None and rule.pattern != ""
            assert rule.llm_prompt is not None and rule.llm_prompt != ""
            
            # Check that prompts are substantial (not just defaults)
            assert len(rule.llm_prompt) > 100, f"Rule {rule.name} has too short prompt"
    
    @pytest.mark.asyncio
    async def test_rule_categories_are_appropriate(self, java_plugin):
        """Test that rules have appropriate categories."""
        rules = await java_plugin.get_analysis_rules()
        
        # Bug category rules
        bug_rules = [r for r in rules if r.category == CommentCategory.BUG]
        bug_rule_names = [r.name for r in bug_rules]
        assert 'avoid_null_pointer' in bug_rule_names
        assert 'resource_leak' in bug_rule_names
        
        # Best practice rules
        best_practice_rules = [r for r in rules if r.category == CommentCategory.BEST_PRACTICE]
        best_practice_names = [r.name for r in best_practice_rules]
        assert 'exception_handling' in best_practice_names
        assert 'naming_conventions' in best_practice_names
        
        # Code smell rules
        code_smell_rules = [r for r in rules if r.category == CommentCategory.CODE_SMELL]
        code_smell_names = [r.name for r in code_smell_rules]
        assert 'code_complexity' in code_smell_names
        assert 'long_methods' in code_smell_names
    
    @pytest.mark.asyncio
    async def test_rule_severities_are_appropriate(self, java_plugin):
        """Test that rules have appropriate severity levels."""
        rules = await java_plugin.get_analysis_rules()
        
        # Error severity (critical bugs)
        error_rules = [r for r in rules if r.severity == CommentSeverity.ERROR]
        assert len(error_rules) > 0
        assert any(r.name == 'avoid_null_pointer' for r in error_rules)
        
        # Warning severity (important issues)
        warning_rules = [r for r in rules if r.severity == CommentSeverity.WARNING]
        assert len(warning_rules) > 0
        
        # Info severity (suggestions)
        info_rules = [r for r in rules if r.severity == CommentSeverity.INFO]
        assert len(info_rules) > 0
