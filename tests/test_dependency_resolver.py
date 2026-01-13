"""
Test suite for DependencyResolver and tree formatting.

Tests the recursive dependency resolution functionality including:
- Answer key extraction from text
- Condition parsing
- Tree building
- Formatting output
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.agents.dependency_resolver import (
    DependencyResolver, 
    DependencyNode, 
    DependencyTree
)
from src.utils.tree_formatter import (
    format_dependency_tree,
    format_compact_tree,
    format_node_simple,
    tree_to_dict
)


class TestDependencyResolver:
    """Test cases for DependencyResolver."""
    
    @pytest.fixture
    def resolver(self):
        """Create a resolver instance."""
        return DependencyResolver()
    
    def test_extract_answer_keys_single(self, resolver):
        """Test extracting a single answer key."""
        text = "<WESTERNDIGITAL_Enagagement_Type> = 'engagement'"
        keys = resolver._extract_answer_keys(text)
        
        assert len(keys) == 1
        assert "WESTERNDIGITAL_Enagagement_Type" in keys
    
    def test_extract_answer_keys_multiple(self, resolver):
        """Test extracting multiple answer keys."""
        text = "<Field_A> = 'value' AND <Field_B> <> 'other'"
        keys = resolver._extract_answer_keys(text)
        
        assert len(keys) == 2
        assert "Field_A" in keys
        assert "Field_B" in keys
    
    def test_extract_answer_keys_with_dollar_sign(self, resolver):
        """Test extracting keys with $ prefix like $ConnectionStage."""
        text = "<$ConnectionStage> <> 'invite'"
        keys = resolver._extract_answer_keys(text)
        
        assert len(keys) == 1
        assert "$ConnectionStage" in keys
    
    def test_extract_answer_keys_empty_text(self, resolver):
        """Test extraction from empty text."""
        keys = resolver._extract_answer_keys("")
        assert keys == []
        
        keys = resolver._extract_answer_keys(None)
        assert keys == []
    
    def test_extract_condition_for_key(self, resolver):
        """Test extracting condition for specific key."""
        text = "<Field_Name> = 'active'"
        condition = resolver._extract_condition_for_key(text, "Field_Name")
        
        assert "=" in condition
        assert "active" in condition
    
    def test_extract_condition_not_equal(self, resolver):
        """Test extracting <> condition."""
        text = "<Some_Field> <> 'Off'"
        condition = resolver._extract_condition_for_key(text, "Some_Field")
        
        assert "<>" in condition or "Off" in condition
    
    def test_max_depth_limit(self, resolver):
        """Test that max depth is respected."""
        # Create a mock that would recurse infinitely
        node = resolver._resolve_key(
            answer_key="test_key",
            condition="= 'test'",
            source="test",
            depth=resolver.MAX_DEPTH,  # Start at max depth
            max_depth=resolver.MAX_DEPTH
        )
        
        assert node is not None
        assert "[MAX DEPTH]" in node.label
    
    def test_cycle_detection(self, resolver):
        """Test that cycles are detected."""
        # First resolve a key
        resolver._visited.add("cyclic_key")
        
        node = resolver._resolve_key(
            answer_key="cyclic_key",
            condition="= 'value'",
            source="test",
            depth=0,
            max_depth=5
        )
        
        assert node is not None
        assert "[CYCLE]" in node.label


class TestDependencyNode:
    """Test cases for DependencyNode dataclass."""
    
    def test_node_creation(self):
        """Test creating a dependency node."""
        node = DependencyNode(
            answer_key="Test_Key",
            label="Test Label",
            condition="= 'value'",
            depth=0
        )
        
        assert node.answer_key == "Test_Key"
        assert node.label == "Test Label"
        assert node.condition == "= 'value'"
        assert node.depth == 0
        assert node.children == []
    
    def test_node_with_children(self):
        """Test node with child nodes."""
        child = DependencyNode(answer_key="Child_Key", depth=1)
        parent = DependencyNode(
            answer_key="Parent_Key",
            depth=0,
            children=[child]
        )
        
        assert len(parent.children) == 1
        assert parent.children[0].answer_key == "Child_Key"


class TestTreeFormatter:
    """Test cases for tree formatting functions."""
    
    @pytest.fixture
    def sample_tree(self):
        """Create a sample tree for testing."""
        child = DependencyNode(
            answer_key="Child_Key",
            label="Child Label",
            condition="<> 'Off'",
            source_sheet="Master Question List",
            depth=1
        )
        root = DependencyNode(
            answer_key="Root_Key",
            label="Root Label",
            condition="= 'active'",
            source_sheet="Workflow",
            depth=0,
            children=[child]
        )
        return DependencyTree(roots=[root], total_nodes=2, max_depth_reached=1)
    
    def test_format_dependency_tree(self, sample_tree):
        """Test formatting complete tree."""
        output = format_dependency_tree(sample_tree)
        
        assert "Root_Key" in output
        assert "Child_Key" in output
        assert "└──" in output or "├──" in output
    
    def test_format_compact_tree(self, sample_tree):
        """Test compact formatting."""
        output = format_compact_tree(sample_tree)
        
        assert "Root_Key" in output
        assert "Child_Key" in output
        assert "•" in output
    
    def test_format_node_simple(self):
        """Test simple node formatting."""
        node = DependencyNode(
            answer_key="Test_Key",
            label="Test Label",
            condition="= 'value'"
        )
        
        output = format_node_simple(node)
        
        assert "Test Label" in output
        assert "Test_Key" in output
    
    def test_tree_to_dict(self, sample_tree):
        """Test converting tree to dictionary."""
        result = tree_to_dict(sample_tree)
        
        assert isinstance(result, dict)
        assert "roots" in result
        assert "total_nodes" in result
        assert result["total_nodes"] == 2


class TestIntegration:
    """Integration tests with actual Pinecone queries."""
    
    @pytest.fixture(scope="class")
    def resolver(self):
        """Create resolver with real Pinecone connection."""
        return DependencyResolver()
    
    @pytest.mark.integration
    def test_resolve_real_query(self, resolver):
        """Test resolving dependencies from real Pinecone data."""
        # This requires actual data in Pinecone
        results = resolver.pinecone.query(
            "Product Integrations workflow",
            top_k=3
        )
        
        if results:
            tree = resolver.resolve(results, max_depth=2)
            
            assert isinstance(tree, DependencyTree)
            assert tree.total_nodes >= 0


def run_manual_test():
    """Manual test function for quick verification."""
    print("=" * 60)
    print("DEPENDENCY RESOLVER - Manual Test")
    print("=" * 60)
    
    resolver = DependencyResolver()
    
    # Test answer key extraction
    test_text = "<WESTERNDIGITAL_Enagagement_Type> = 'engagement' AND <$ConnectionStage> <> 'invite'"
    keys = resolver._extract_answer_keys(test_text)
    print(f"\nExtracted keys from: {test_text}")
    print(f"Keys found: {keys}")
    
    # Test tree building from real query
    print("\nQuerying Pinecone for 'Product Integrations'...")
    results = resolver.pinecone.query("Product Integrations workflow activation", top_k=5)
    
    if results:
        print(f"Found {len(results)} results")
        
        print("\nBuilding dependency tree...")
        tree = resolver.resolve(results, max_depth=3)
        
        print(f"\nTree stats: {tree.total_nodes} nodes, max depth {tree.max_depth_reached}")
        
        print("\n" + "=" * 60)
        print("FORMATTED TREE:")
        print("=" * 60)
        print(format_dependency_tree(tree))
    else:
        print("No results found. Is Pinecone indexed?")
    
    print("\n" + "=" * 60)
    print("✅ Manual test complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_manual_test()
