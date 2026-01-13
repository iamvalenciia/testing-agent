"""Tests for Goal Decomposer module."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent-backend'))


class TestGoalDecomposerQuickDecompose:
    """Test the quick pattern-based decomposition."""
    
    def test_decompose_login_and_download(self):
        """Test decomposing 'login and download' into two tasks."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        goal = "login and download the hammer file from western"
        
        subtasks = decomposer._quick_decompose(goal)
        
        assert len(subtasks) == 2
        assert subtasks[0].action == "login"
        assert "download" in subtasks[1].action or "download" in subtasks[1].target
    
    def test_decompose_single_task_returns_empty(self):
        """Single task should return empty list (no decomposition needed)."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        goal = "download the hammer file"
        
        subtasks = decomposer._quick_decompose(goal)
        
        assert len(subtasks) == 0  # No obvious decomposition
    
    def test_decompose_with_then(self):
        """Test decomposing with 'then' separator."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        goal = "login to the system then download the report"
        
        subtasks = decomposer._quick_decompose(goal)
        
        assert len(subtasks) == 2
    
    def test_decompose_with_comma(self):
        """Test decomposing with comma separator."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        goal = "open browser, go to admin page, download file"
        
        subtasks = decomposer._quick_decompose(goal)
        
        assert len(subtasks) == 3


class TestKeywordExtraction:
    """Test keyword extraction for fallback matching."""
    
    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        text = "download the hammer file from western"
        
        keywords = decomposer._extract_keywords(text)
        
        assert "download" in keywords
        assert "hammer" in keywords
        assert "western" in keywords
        assert "the" not in keywords  # Stop word
        assert "from" not in keywords  # Stop word
    
    def test_extract_keywords_with_ids(self):
        """Test that IDs are preserved as keywords."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        text = "find supplier US66254 in the system"
        
        keywords = decomposer._extract_keywords(text)
        
        assert "us66254" in keywords  # Lowercase
        assert "supplier" in keywords
        assert "find" in keywords


class TestExecutionPlan:
    """Test the complete execution plan generation."""
    
    def test_single_task_not_decomposed(self):
        """Single task should not be marked as decomposed."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        goal = "login to the test environment"
        
        plan = decomposer.get_execution_plan(goal)
        
        assert plan["subtask_count"] == 1
        assert plan["is_decomposed"] == False
    
    def test_multi_task_is_decomposed(self):
        """Multiple tasks should be marked as decomposed."""
        from goal_decomposer import GoalDecomposer
        
        decomposer = GoalDecomposer()
        goal = "login and download hammer from western"
        
        plan = decomposer.get_execution_plan(goal)
        
        assert plan["subtask_count"] >= 2
        assert plan["is_decomposed"] == True


class TestTieredMatching:
    """Test the tiered threshold matching in PineconeService."""
    
    def test_tiered_thresholds_default(self):
        """Test that default thresholds are applied correctly."""
        # This is more of an integration test - would need mock Pinecone
        pass  # Skip for unit tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
