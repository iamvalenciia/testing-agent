"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         DEPENDENCY RESOLVER                                  ║
║                                                                              ║
║  Recursively resolves answer_key dependencies to build complete             ║
║  condition trees from The Hammer data.                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

ARCHITECTURE
============

The resolver follows a BFS approach to build dependency trees:

┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESOLUTION FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Initial Results ──► Extract <ANSWER_KEY> refs ──► Queue unresolved keys   │
│                                                         │                   │
│                                              ┌──────────┴──────────┐        │
│                                              │   For each key:     │        │
│                                              │   1. Query Pinecone │        │
│                                              │   2. Build node     │        │
│                                              │   3. Find children  │        │
│                                              └──────────┬──────────┘        │
│                                                         │                   │
│                                              ┌──────────┴──────────┐        │
│                                              │  Until:             │        │
│                                              │  - Queue empty      │        │
│                                              │  - MAX_DEPTH hit    │        │
│                                              └─────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
"""
import re
from dataclasses import dataclass, field
from typing import Optional
from src.database.vector_store import PineconeService


@dataclass
class DependencyNode:
    """
    Node in the dependency tree.
    
    Represents a single answer_key with its associated metadata
    and child dependencies.
    
    Attributes:
        answer_key: The answer key identifier (e.g., "WESTERNDIGITAL_Enagagement_Type")
        label: Human-readable label for display
        condition: The condition expression (e.g., '= "engagement"')
        value: Default or current value if available
        source_sheet: Which Excel sheet this came from
        source_info: Additional context about the source
        children: List of dependent nodes (recursive)
        depth: Current depth in the tree
    """
    answer_key: str
    label: str = ""
    condition: str = ""
    value: str = ""
    source_sheet: str = ""
    source_info: str = ""
    children: list = field(default_factory=list)
    depth: int = 0


@dataclass
class DependencyTree:
    """
    Complete dependency tree structure.
    
    Contains the root nodes and metadata about the resolution process.
    """
    roots: list[DependencyNode] = field(default_factory=list)
    total_nodes: int = 0
    max_depth_reached: int = 0
    unresolved_keys: list[str] = field(default_factory=list)


class DependencyResolver:
    """
    Resolves answer_key dependencies recursively from Pinecone.
    
    This resolver extracts <ANSWER_KEY> references from query results
    and recursively queries Pinecone to build a complete dependency tree.
    
    Features:
    - Regex extraction of answer_key references
    - Cycle detection to prevent infinite loops
    - Depth limiting (MAX_DEPTH = 5)
    - BFS-style resolution for breadth coverage
    
    Example:
        >>> resolver = DependencyResolver(pinecone_service)
        >>> tree = resolver.resolve(initial_results)
        >>> print(format_tree(tree))
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════
    
    MAX_DEPTH = 5  # Maximum recursion depth
    TOP_K_PER_KEY = 3  # Results per answer_key query
    
    # Regex pattern to extract <ANSWER_KEY> references
    # Matches: <Some_Answer_Key>, <$Variable>, <Company_Field_Name>
    ANSWER_KEY_PATTERN = re.compile(r'<([A-Za-z_$][A-Za-z0-9_]*)>')
    
    # Condition pattern to extract operator and value
    # Matches: = "value", <> "value", = 'value'
    CONDITION_PATTERN = re.compile(r'([=<>!]+)\s*["\']?([^"\'<>\n]+)["\']?')
    
    def __init__(self, pinecone: PineconeService = None):
        """
        Initialize the dependency resolver.
        
        Args:
            pinecone: Optional PineconeService instance. 
                      Creates new one if not provided.
        """
        self.pinecone = pinecone or PineconeService()
        self._visited: set[str] = set()  # Cycle detection
        
    # ═══════════════════════════════════════════════════════════════════════
    # MAIN RESOLUTION API
    # ═══════════════════════════════════════════════════════════════════════
    
    def resolve(self, initial_results: list[dict], max_depth: int = None) -> DependencyTree:
        """
        Resolve dependencies from initial Pinecone results.
        
        Takes the initial query results and recursively resolves
        all <ANSWER_KEY> references found in metadata fields like
        Filter, UI Condition, Default, etc.
        
        Args:
            initial_results: List of Pinecone query results
            max_depth: Override MAX_DEPTH if needed
            
        Returns:
            DependencyTree: Complete resolved tree structure
        """
        max_depth = max_depth or self.MAX_DEPTH
        self._visited.clear()
        
        tree = DependencyTree()
        
        # Extract answer_keys and conditions from initial results
        root_keys = self._extract_keys_from_results(initial_results)
        
        # Build root nodes
        for key_info in root_keys:
            node = self._resolve_key(
                answer_key=key_info["key"],
                condition=key_info.get("condition", ""),
                source=key_info.get("source", "Initial Query"),
                depth=0,
                max_depth=max_depth
            )
            if node:
                tree.roots.append(node)
        
        # Calculate stats
        tree.total_nodes = self._count_nodes(tree.roots)
        tree.max_depth_reached = self._get_max_depth(tree.roots)
        tree.unresolved_keys = list(self._visited)
        
        return tree
    
    def resolve_single_key(self, answer_key: str, max_depth: int = None) -> Optional[DependencyNode]:
        """
        Resolve a single answer_key and its dependencies.
        
        Useful for targeted queries about specific fields.
        
        Args:
            answer_key: The answer key to resolve
            max_depth: Maximum resolution depth
            
        Returns:
            DependencyNode or None if not found
        """
        max_depth = max_depth or self.MAX_DEPTH
        self._visited.clear()
        
        return self._resolve_key(
            answer_key=answer_key,
            condition="",
            source="Direct Query",
            depth=0,
            max_depth=max_depth
        )
    
    # ═══════════════════════════════════════════════════════════════════════
    # EXTRACTION METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _extract_keys_from_results(self, results: list[dict]) -> list[dict]:
        """
        Extract answer_key references from Pinecone results.
        
        Searches through metadata fields that typically contain
        conditions: Filter, UI Condition, Default, Hide Unless, etc.
        
        Returns:
            List of dicts with 'key', 'condition', 'source'
        """
        extracted = []
        condition_fields = [
            "Filter", "UI Condition", "Default", "Hide Unless", 
            "Visibility Condition", "Editable", "Required Condition"
        ]
        
        for result in results:
            metadata = result.get("metadata", {})
            sheet_name = metadata.get("sheet_name", "Unknown")
            
            # Check each condition field
            for field_name in condition_fields:
                if field_name in metadata:
                    field_value = str(metadata[field_name])
                    keys_found = self._extract_answer_keys(field_value)
                    
                    for key in keys_found:
                        # Try to extract the condition for this key
                        condition = self._extract_condition_for_key(field_value, key)
                        extracted.append({
                            "key": key,
                            "condition": condition,
                            "source": f"{sheet_name}.{field_name}"
                        })
            
            # Also check Answer Key field directly
            if "Answer Key" in metadata:
                extracted.append({
                    "key": metadata["Answer Key"],
                    "condition": "",
                    "source": f"{sheet_name}.AnswerKey"
                })
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for item in extracted:
            if item["key"] not in seen:
                seen.add(item["key"])
                unique.append(item)
        
        return unique
    
    def _extract_answer_keys(self, text: str) -> list[str]:
        """
        Extract all <ANSWER_KEY> patterns from text.
        
        Args:
            text: String to search for answer_key references
            
        Returns:
            List of extracted answer_key names
        """
        if not text:
            return []
        return self.ANSWER_KEY_PATTERN.findall(text)
    
    def _extract_condition_for_key(self, text: str, key: str) -> str:
        """
        Extract the condition operator and value for a specific key.
        
        Example:
            text: "<Field_Name> = 'value'"
            key: "Field_Name"
            returns: "= 'value'"
        """
        # Find the key and what follows
        pattern = rf'<{re.escape(key)}>\s*([=<>!]+\s*["\']?[^"\'<>\n]+["\']?)'
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return ""
    
    # ═══════════════════════════════════════════════════════════════════════
    # RESOLUTION LOGIC
    # ═══════════════════════════════════════════════════════════════════════
    
    def _resolve_key(
        self, 
        answer_key: str, 
        condition: str,
        source: str,
        depth: int,
        max_depth: int
    ) -> Optional[DependencyNode]:
        """
        Resolve a single answer_key recursively.
        
        Args:
            answer_key: Key to resolve
            condition: Associated condition (e.g., "= 'value'")
            source: Where this key was found
            depth: Current depth level
            max_depth: Maximum allowed depth
            
        Returns:
            DependencyNode with resolved children, or None
        """
        # Stop conditions
        if depth >= max_depth:
            return DependencyNode(
                answer_key=answer_key,
                label=f"[MAX DEPTH] {answer_key}",
                condition=condition,
                depth=depth
            )
        
        if answer_key in self._visited:
            return DependencyNode(
                answer_key=answer_key,
                label=f"[CYCLE] {answer_key}",
                condition=condition,
                depth=depth
            )
        
        self._visited.add(answer_key)
        
        # Query Pinecone for this answer_key
        results = self._query_for_key(answer_key)
        
        if not results:
            return DependencyNode(
                answer_key=answer_key,
                label=answer_key,
                condition=condition,
                source_info=source,
                depth=depth
            )
        
        # Build node from best result
        best_result = results[0]
        metadata = best_result.get("metadata", {})
        
        node = DependencyNode(
            answer_key=answer_key,
            label=metadata.get("Question", metadata.get("Label", answer_key)),
            condition=condition,
            value=metadata.get("Default", metadata.get("Value", "")),
            source_sheet=metadata.get("sheet_name", ""),
            source_info=self._build_source_info(metadata),
            depth=depth
        )
        
        # Find child dependencies
        child_keys = self._extract_keys_from_results(results)
        
        for child_info in child_keys:
            if child_info["key"] != answer_key:  # Avoid self-reference
                child_node = self._resolve_key(
                    answer_key=child_info["key"],
                    condition=child_info.get("condition", ""),
                    source=child_info.get("source", ""),
                    depth=depth + 1,
                    max_depth=max_depth
                )
                if child_node:
                    node.children.append(child_node)
        
        return node
    
    def _query_for_key(self, answer_key: str) -> list[dict]:
        """
        Query Pinecone for information about an answer_key.
        
        Uses semantic search with the answer_key as query text.
        """
        # Query both by answer key name and semantically
        query = f"Answer Key: {answer_key}"
        return self.pinecone.query(query, top_k=self.TOP_K_PER_KEY)
    
    def _build_source_info(self, metadata: dict) -> str:
        """Build a summary of source information from metadata."""
        parts = []
        if metadata.get("Question Id"):
            parts.append(f"Question: {metadata['Question Id']}")
        if metadata.get("Group Definitions"):
            parts.append(f"Group: {metadata['Group Definitions']}")
        if metadata.get("Workflow ID"):
            parts.append(f"Workflow: {metadata['Workflow ID']}")
        return " | ".join(parts)
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════
    
    def _count_nodes(self, nodes: list[DependencyNode]) -> int:
        """Count total nodes in tree."""
        count = len(nodes)
        for node in nodes:
            count += self._count_nodes(node.children)
        return count
    
    def _get_max_depth(self, nodes: list[DependencyNode]) -> int:
        """Get maximum depth reached in tree."""
        if not nodes:
            return 0
        max_d = max(node.depth for node in nodes)
        for node in nodes:
            child_max = self._get_max_depth(node.children)
            max_d = max(max_d, child_max)
        return max_d
