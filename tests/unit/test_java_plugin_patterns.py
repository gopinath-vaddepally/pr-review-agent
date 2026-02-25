"""
Unit tests for Java plugin design pattern detection.
"""

import pytest
from pathlib import Path
from plugins.java.plugin import JavaPlugin


class TestJavaPluginPatternDetection:
    """Test Java plugin design pattern detection."""
    
    @pytest.fixture
    def java_plugin(self):
        """Create a Java plugin instance."""
        config_path = Path("plugins/java/config.yaml")
        return JavaPlugin(config_path=config_path)
    
    @pytest.mark.asyncio
    async def test_detect_singleton_pattern(self, java_plugin):
        """Test detection of Singleton pattern."""
        # Singleton pattern example
        singleton_code = """
        public class DatabaseConnection {
            private static DatabaseConnection instance;
            
            private DatabaseConnection() {
                // Private constructor
            }
            
            public static DatabaseConnection getInstance() {
                if (instance == null) {
                    instance = new DatabaseConnection();
                }
                return instance;
            }
        }
        """
        
        # Parse the code
        ast = await java_plugin.parse_file("DatabaseConnection.java", singleton_code)
        
        # Detect patterns
        patterns = await java_plugin.detect_patterns(ast)
        
        # Should detect Singleton pattern
        assert len(patterns) > 0
        singleton_patterns = [p for p in patterns if p.pattern_name == "Singleton"]
        assert len(singleton_patterns) == 1
        assert singleton_patterns[0].pattern_type == "creational"
        assert "private constructor" in singleton_patterns[0].description.lower()
    
    @pytest.mark.asyncio
    async def test_detect_factory_pattern(self, java_plugin):
        """Test detection of Factory pattern."""
        # Factory pattern example
        factory_code = """
        public class ShapeFactory {
            public Shape createShape(String type) {
                if (type.equals("circle")) {
                    return new Circle();
                } else if (type.equals("square")) {
                    return new Square();
                }
                return null;
            }
        }
        """
        
        # Parse the code
        ast = await java_plugin.parse_file("ShapeFactory.java", factory_code)
        
        # Detect patterns
        patterns = await java_plugin.detect_patterns(ast)
        
        # Should detect Factory pattern
        assert len(patterns) > 0
        factory_patterns = [p for p in patterns if p.pattern_name == "Factory"]
        assert len(factory_patterns) == 1
        assert factory_patterns[0].pattern_type == "creational"
        assert "factory method" in factory_patterns[0].description.lower()
    
    @pytest.mark.asyncio
    async def test_detect_builder_pattern(self, java_plugin):
        """Test detection of Builder pattern."""
        # Builder pattern example
        builder_code = """
        public class User {
            private String name;
            private int age;
            
            private User(Builder builder) {
                this.name = builder.name;
                this.age = builder.age;
            }
            
            public static class Builder {
                private String name;
                private int age;
                
                public Builder setName(String name) {
                    this.name = name;
                    return this;
                }
                
                public Builder setAge(int age) {
                    this.age = age;
                    return this;
                }
                
                public User build() {
                    return new User(this);
                }
            }
        }
        """
        
        # Parse the code
        ast = await java_plugin.parse_file("User.java", builder_code)
        
        # Detect patterns
        patterns = await java_plugin.detect_patterns(ast)
        
        # Should detect Builder pattern
        assert len(patterns) > 0
        builder_patterns = [p for p in patterns if p.pattern_name == "Builder"]
        assert len(builder_patterns) == 1
        assert builder_patterns[0].pattern_type == "creational"
        assert "fluent interface" in builder_patterns[0].description.lower()
    
    @pytest.mark.asyncio
    async def test_no_patterns_in_simple_class(self, java_plugin):
        """Test that simple classes don't trigger pattern detection."""
        # Simple class without patterns
        simple_code = """
        public class Calculator {
            public int add(int a, int b) {
                return a + b;
            }
            
            public int subtract(int a, int b) {
                return a - b;
            }
        }
        """
        
        # Parse the code
        ast = await java_plugin.parse_file("Calculator.java", simple_code)
        
        # Detect patterns
        patterns = await java_plugin.detect_patterns(ast)
        
        # Should not detect any patterns
        assert len(patterns) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_patterns_in_same_file(self, java_plugin):
        """Test detection of multiple patterns in the same file."""
        # Code with both Factory and Singleton patterns
        multi_pattern_code = """
        public class ConnectionFactory {
            private static ConnectionFactory instance;
            
            private ConnectionFactory() {
                // Private constructor
            }
            
            public static ConnectionFactory getInstance() {
                if (instance == null) {
                    instance = new ConnectionFactory();
                }
                return instance;
            }
            
            public Connection createConnection(String type) {
                if (type.equals("mysql")) {
                    return new MySQLConnection();
                } else if (type.equals("postgres")) {
                    return new PostgresConnection();
                }
                return null;
            }
        }
        """
        
        # Parse the code
        ast = await java_plugin.parse_file("ConnectionFactory.java", multi_pattern_code)
        
        # Detect patterns
        patterns = await java_plugin.detect_patterns(ast)
        
        # Should detect both Singleton and Factory patterns
        assert len(patterns) >= 2
        pattern_names = [p.pattern_name for p in patterns]
        assert "Singleton" in pattern_names
        assert "Factory" in pattern_names
    
    @pytest.mark.asyncio
    async def test_pattern_detection_returns_correct_structure(self, java_plugin):
        """Test that detected patterns have correct structure."""
        singleton_code = """
        public class Logger {
            private static Logger instance;
            
            private Logger() {}
            
            public static Logger getInstance() {
                return instance;
            }
        }
        """
        
        # Parse the code
        ast = await java_plugin.parse_file("Logger.java", singleton_code)
        
        # Detect patterns
        patterns = await java_plugin.detect_patterns(ast)
        
        # Verify structure
        for pattern in patterns:
            assert hasattr(pattern, 'pattern_name')
            assert hasattr(pattern, 'pattern_type')
            assert hasattr(pattern, 'file_paths')
            assert hasattr(pattern, 'description')
            
            assert pattern.pattern_name is not None
            assert pattern.pattern_type in ['creational', 'structural', 'behavioral']
            assert isinstance(pattern.file_paths, list)
            assert pattern.description is not None and len(pattern.description) > 0
