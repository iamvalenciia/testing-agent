"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           HAMMER CHAT AGENT                                  ║
║                                                                              ║
║  RAG-powered conversational agent that:                                      ║
║    1. Receives user questions about The Hammer data                          ║
║    2. Queries Pinecone for relevant context                                  ║
║    3. Generates intelligent responses using Gemini 2.5 Flash                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

ARCHITECTURE
============

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  User Question  │────▶│  Pinecone Query  │────▶│  Gemini 2.5     │
│  "What is X?"   │     │  (top_k=5)       │     │  Flash Response │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                        │
                               ▼                        ▼
                        Relevant context          Final answer with
                        from The Hammer           source citations

"""
from google import genai
from src.database.vector_store import PineconeService
from src.config import Config
from src.agents.dependency_resolver import DependencyResolver, DependencyTree
from src.utils.tree_formatter import format_dependency_tree, format_compact_tree


class HammerChatAgent:
    """
    Chat agent with RAG capabilities for The Hammer data.
    
    This agent uses Retrieval Augmented Generation (RAG) to answer
    questions about The Hammer Excel data stored in Pinecone.
    
    Key features:
    - Semantic search over all Hammer sheets
    - Context-aware response generation
    - Source citation for transparency
    
    Attributes:
        MODEL (str): Gemini model for response generation
        pinecone (PineconeService): Vector store for context retrieval
        client (genai.Client): Gemini API client
        
    Example:
        >>> agent = HammerChatAgent()
        >>> result = agent.chat("What are group definitions?")
        >>> print(result["answer"])
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════
    
    MODEL = "gemini-2.5-flash"  # Gemini 2.5 Flash
    DEFAULT_TOP_K = 5  # Number of context chunks to retrieve
    
    # System prompt for RAG responses
    SYSTEM_PROMPT = """You are an expert assistant for "The Hammer" - a comprehensive 
Excel-based configuration system for Graphi Connect. Your role is to help users 
understand the data, configurations, and relationships within The Hammer.

INSTRUCTIONS:
1. Answer questions ONLY based on the provided context from The Hammer
2. If the context doesn't contain enough information, say so clearly
3. Reference specific sheets and data when possible
4. Be concise but thorough
5. Use bullet points for lists and structured data
6. If asked about something not in the context, politely indicate the limitation

CONTEXT FORMAT:
Each context chunk includes:
- Sheet Name: Which Excel sheet the data comes from
- Row Data: The actual content from that row
- Relevance Score: How closely it matches the query (higher = more relevant)
"""

    def __init__(self):
        """
        Initialize the Hammer Chat Agent.
        
        Connects to:
        - Pinecone for semantic search
        - Gemini API for response generation
        - DependencyResolver for tree building
        """
        Config.validate()
        self.pinecone = PineconeService()
        self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        self.resolver = DependencyResolver(self.pinecone)
    
    # ═══════════════════════════════════════════════════════════════════════
    # CORE CHAT FUNCTIONALITY
    # ═══════════════════════════════════════════════════════════════════════
    
    def chat(self, question: str, top_k: int = None) -> dict:
        """
        Process a user question and generate a RAG-powered response.
        
        Process:
        1. Query Pinecone for relevant context chunks
        2. Format context for the LLM prompt
        3. Generate response using Gemini 2.5 Flash
        4. Return answer with source citations
        
        Args:
            question: User's natural language question
            top_k: Number of context chunks to retrieve (default: 5)
            
        Returns:
            dict: Response containing:
                - answer (str): Generated response
                - sources (list[dict]): Context chunks used
                    - id: Vector ID
                    - score: Relevance score
                    - sheet_name: Source Excel sheet
                    - preview: First 100 chars of content
                    
        Example:
            >>> result = agent.chat("What triggers are available?")
            >>> print(result["answer"])
            >>> for source in result["sources"]:
            ...     print(f"{source['sheet_name']}: {source['score']:.2f}")
        """
        top_k = top_k or self.DEFAULT_TOP_K
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 1: Retrieve relevant context from Pinecone
        # ─────────────────────────────────────────────────────────────────
        context_results = self.pinecone.query(question, top_k=top_k)
        
        if not context_results:
            return {
                "answer": "I couldn't find any relevant information in The Hammer for your question. Please try rephrasing or ask about a different topic.",
                "sources": []
            }
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 2: Format context for the prompt
        # ─────────────────────────────────────────────────────────────────
        context_text = self._format_context(context_results)
        sources = self._extract_sources(context_results)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 3: Generate response with Gemini
        # ─────────────────────────────────────────────────────────────────
        prompt = self._build_prompt(question, context_text)
        
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
            config={
                "system_instruction": self.SYSTEM_PROMPT,
                "temperature": 0.7,
                "max_output_tokens": 4096,
            }
        )
        
        answer = response.text if response.text else "I was unable to generate a response. Please try again."
        
        return {
            "answer": answer,
            "sources": sources
        }
    
    def chat_with_tree(self, question: str, top_k: int = None, max_depth: int = 5) -> dict:
        """
        Process a question and resolve ALL dependency trees.
        
        This enhanced chat method:
        1. Queries Pinecone for relevant context
        2. Builds a complete dependency tree by recursively resolving answer_keys
        3. Generates a response that includes the full tree structure
        
        Use this for questions about workflow conditions, activations, or any
        query where understanding the complete chain of dependencies is important.
        
        Args:
            question: User's natural language question
            top_k: Number of initial context chunks to retrieve (default: 5)
            max_depth: Maximum depth for dependency resolution (default: 5)
            
        Returns:
            dict: Response containing:
                - answer (str): Generated response with tree
                - sources (list[dict]): Context chunks used
                - tree (DependencyTree): Resolved dependency tree object
                - tree_text (str): Formatted ASCII tree string
                
        Example:
            >>> result = agent.chat_with_tree("What activates Product Integrations?")
            >>> print(result["tree_text"])
        """
        top_k = top_k or self.DEFAULT_TOP_K
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 1: Retrieve relevant context from Pinecone
        # ─────────────────────────────────────────────────────────────────
        context_results = self.pinecone.query(question, top_k=top_k)
        
        if not context_results:
            return {
                "answer": "I couldn't find any relevant information in The Hammer for your question. Please try rephrasing or ask about a different topic.",
                "sources": [],
                "tree": DependencyTree(),
                "tree_text": ""
            }
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 2: Build dependency tree
        # ─────────────────────────────────────────────────────────────────
        dependency_tree = self.resolver.resolve(context_results, max_depth=max_depth)
        tree_text = format_dependency_tree(dependency_tree)
        compact_tree = format_compact_tree(dependency_tree)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 3: Format context with tree for the prompt
        # ─────────────────────────────────────────────────────────────────
        context_text = self._format_context(context_results)
        sources = self._extract_sources(context_results)
        
        # ─────────────────────────────────────────────────────────────────
        # STEP 4: Generate response with tree-aware prompt
        # ─────────────────────────────────────────────────────────────────
        prompt = self._build_tree_prompt(question, context_text, compact_tree)
        
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
            config={
                "system_instruction": self._get_tree_system_prompt(),
                "temperature": 0.5,  # Lower temp for more structured output
                "max_output_tokens": 8192,
            }
        )
        
        answer = response.text if response.text else "I was unable to generate a response. Please try again."
        
        # Append tree to answer
        full_answer = f"{answer}\n\n## 🌳 Complete Dependency Tree\n```\n{tree_text}\n```"
        
        return {
            "answer": full_answer,
            "sources": sources,
            "tree": dependency_tree,
            "tree_text": tree_text
        }
    
    def _build_tree_prompt(self, question: str, context: str, tree: str) -> str:
        """Build prompt that includes dependency tree context."""
        return f"""Based on the following context from The Hammer and the resolved dependency tree, 
please answer the user's question about workflow conditions and activations.

===== CONTEXT FROM THE HAMMER =====
{context}
===================================

===== RESOLVED DEPENDENCY TREE =====
{tree}
====================================

USER QUESTION: {question}

Please provide:
1. A clear explanation of the activation/display conditions
2. The complete chain of dependencies (what triggers what)
3. Any default values and when they apply
4. Use the Label (Answer Key) format when referencing fields"""
    
    def _get_tree_system_prompt(self) -> str:
        """Get system prompt optimized for tree-based responses."""
        return """You are an expert assistant for "The Hammer" - a comprehensive 
Excel-based configuration system for Graphi Connect. You specialize in explaining
workflow conditions and dependency chains.

INSTRUCTIONS:
1. Answer questions based on the provided context AND dependency tree
2. Always show BOTH the Label AND the Answer Key: "Label Name (Answer Key: field_name)"
3. Explain the complete chain of conditions from first to last
4. Use clear formatting with bullet points and indentation
5. Include operators (=, <>, etc.) and values for conditions
6. If a field has a default value, explain when it applies

FORMAT EXAMPLE:
• Product Integrations (Answer Key: Company_Product_Integrations)
  - Activation: WESTERNDIGITAL_Enagagement_Type = "engagement"
    - This is set when: $ConnectionStage <> "invite"
  - Display: Company_Product_Integrations_FINAL_SOT <> "Off"
    - Default is "On" when: [list conditions]"""
    
    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _format_context(self, results: list[dict]) -> str:
        """
        Format Pinecone results into a readable context string.
        
        Args:
            results: List of query results from Pinecone
            
        Returns:
            str: Formatted context for the LLM prompt
        """
        context_parts = []
        
        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            sheet_name = metadata.get("sheet_name", "Unknown")
            score = result.get("score", 0)
            
            # Build content from metadata (excluding system fields)
            content_fields = []
            for key, value in metadata.items():
                if key not in ["source", "sheet_name", "row_index"] and value:
                    content_fields.append(f"  • {key}: {value}")
            
            content = "\n".join(content_fields) if content_fields else "  (No content available)"
            
            context_parts.append(
                f"[Source {i}] Sheet: {sheet_name} | Relevance: {score:.2f}\n{content}"
            )
        
        return "\n\n".join(context_parts)
    
    def _extract_sources(self, results: list[dict]) -> list[dict]:
        """
        Extract source citations from Pinecone results.
        
        Args:
            results: List of query results from Pinecone
            
        Returns:
            list[dict]: Simplified source information for display
        """
        sources = []
        
        for result in results:
            metadata = result.get("metadata", {})
            
            # Create a preview of the content
            preview_parts = []
            for key, value in metadata.items():
                if key not in ["source", "sheet_name", "row_index"] and value:
                    preview_parts.append(f"{key}: {str(value)[:50]}")
                    if len(preview_parts) >= 2:
                        break
            
            preview = " | ".join(preview_parts)[:100]
            
            sources.append({
                "id": result.get("id", "unknown"),
                "score": result.get("score", 0),
                "sheet_name": metadata.get("sheet_name", "Unknown"),
                "preview": preview
            })
        
        return sources
    
    def _build_prompt(self, question: str, context: str) -> str:
        """
        Build the complete prompt for Gemini.
        
        Args:
            question: User's question
            context: Formatted context from Pinecone
            
        Returns:
            str: Complete prompt for the LLM
        """
        return f"""Based on the following context from The Hammer, please answer the user's question.

===== CONTEXT FROM THE HAMMER =====
{context}
===================================

USER QUESTION: {question}

Please provide a clear, helpful answer based on the context above."""
    
    def get_stats(self) -> dict:
        """
        Get current statistics about the knowledge base.
        
        Returns:
            dict: Pinecone index statistics
        """
        return self.pinecone.get_index_stats()
