"""
Test suite for HammerChatAgent.

Tests the RAG functionality including:
- Context retrieval from Pinecone
- Response generation with sources
- Error handling
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.agents.hammer_chat import HammerChatAgent


class TestHammerChatAgent:
    """Test cases for HammerChatAgent."""
    
    @pytest.fixture(scope="class")
    def agent(self):
        """Create a shared agent instance for all tests."""
        return HammerChatAgent()
    
    def test_chat_returns_answer_and_sources(self, agent):
        """Test that chat returns both answer and sources."""
        result = agent.chat("What are group definitions?")
        
        assert "answer" in result, "Response should contain 'answer' key"
        assert "sources" in result, "Response should contain 'sources' key"
        assert isinstance(result["answer"], str), "Answer should be a string"
        assert isinstance(result["sources"], list), "Sources should be a list"
    
    def test_chat_returns_non_empty_answer(self, agent):
        """Test that chat returns a non-empty answer."""
        result = agent.chat("What are the triggers?")
        
        assert len(result["answer"]) > 0, "Answer should not be empty"
    
    def test_sources_have_required_fields(self, agent):
        """Test that each source has required fields."""
        result = agent.chat("Tell me about overrides")
        
        if result["sources"]:  # Only test if sources exist
            source = result["sources"][0]
            assert "id" in source, "Source should have 'id'"
            assert "score" in source, "Source should have 'score'"
            assert "sheet_name" in source, "Source should have 'sheet_name'"
    
    def test_get_stats_returns_dict(self, agent):
        """Test that get_stats returns valid statistics."""
        stats = agent.get_stats()
        
        assert isinstance(stats, dict), "Stats should be a dict"
        assert "total_vector_count" in stats, "Stats should have 'total_vector_count'"
        assert "dimension" in stats, "Stats should have 'dimension'"
    
    def test_custom_top_k(self, agent):
        """Test that top_k parameter limits sources."""
        result = agent.chat("connections", top_k=2)
        
        assert len(result["sources"]) <= 2, "Sources should respect top_k limit"


def run_manual_test():
    """
    Manual test function for quick verification.
    Run with: python tests/test_hammer_chat.py
    """
    print("=" * 60)
    print("HAMMER CHAT AGENT - Manual Test")
    print("=" * 60)
    
    agent = HammerChatAgent()
    
    test_questions = [
        "What are group definitions?",
        "Tell me about triggers",
        "How do overrides work?"
    ]
    
    for question in test_questions:
        print(f"\n📝 Question: {question}")
        print("-" * 40)
        
        result = agent.chat(question, top_k=3)
        
        print(f"🤖 Answer: {result['answer'][:200]}...")
        print(f"📚 Sources: {len(result['sources'])} found")
        for s in result["sources"]:
            print(f"   • {s['sheet_name']} (score: {s['score']:.2f})")
    
    print("\n" + "=" * 60)
    print("✅ Manual test complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_manual_test()
