"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           TREE FORMATTER                                     ║
║                                                                              ║
║  Formats DependencyTree structures into readable ASCII tree output.         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from src.agents.dependency_resolver import DependencyTree, DependencyNode


def format_dependency_tree(tree: DependencyTree, show_stats: bool = True) -> str:
    """
    Format a DependencyTree into a readable ASCII tree string.
    
    Args:
        tree: The DependencyTree to format
        show_stats: Whether to include statistics at the end
        
    Returns:
        str: Formatted tree as ASCII art
        
    Example output:
        └── Product Integrations (Key: Company_Product_Integrations)
            ├── Condition: WESTERNDIGITAL_Enagagement_Type = "engagement"
            │   └── Set when: $ConnectionStage <> "invite"
            └── Display: Company_Product_Integrations_FINAL_SOT <> "Off"
                └── Default "On" when: ...
    """
    lines = []
    
    for i, root in enumerate(tree.roots):
        is_last = (i == len(tree.roots) - 1)
        lines.extend(_format_node(root, "", is_last))
    
    if show_stats:
        lines.append("")
        lines.append(f"─── Stats: {tree.total_nodes} nodes | Max depth: {tree.max_depth_reached} ───")
    
    return "\n".join(lines)


def format_node_simple(node: DependencyNode) -> str:
    """
    Format a single node into a simple one-line string.
    
    Format: "Label (Key: answer_key) condition"
    """
    parts = []
    
    if node.label and node.label != node.answer_key:
        parts.append(node.label)
        parts.append(f"(Key: {node.answer_key})")
    else:
        parts.append(f"Key: {node.answer_key}")
    
    if node.condition:
        parts.append(node.condition)
    
    return " ".join(parts)


def _format_node(
    node: DependencyNode, 
    prefix: str, 
    is_last: bool
) -> list[str]:
    """
    Recursively format a node and its children.
    
    Args:
        node: The node to format
        prefix: Current line prefix (indentation + connectors)
        is_last: Whether this is the last sibling
        
    Returns:
        List of formatted lines
    """
    lines = []
    
    # Determine connector
    connector = "└── " if is_last else "├── "
    
    # Build node label
    label_parts = []
    
    # Main label
    if node.label and node.label != node.answer_key:
        if "[CYCLE]" in node.label or "[MAX DEPTH]" in node.label:
            label_parts.append(node.label)
        else:
            label_parts.append(f"{node.label}")
            label_parts.append(f"(Key: {node.answer_key})")
    else:
        label_parts.append(f"Key: {node.answer_key}")
    
    # Add condition if present
    if node.condition:
        label_parts.append(f"[{node.condition}]")
    
    # Add source sheet
    if node.source_sheet:
        label_parts.append(f"← {node.source_sheet}")
    
    lines.append(f"{prefix}{connector}{' '.join(label_parts)}")
    
    # Add value line if present
    child_prefix = prefix + ("    " if is_last else "│   ")
    
    if node.value and node.value.strip():
        lines.append(f"{child_prefix}→ Value/Default: {node.value[:80]}")
    
    if node.source_info:
        lines.append(f"{child_prefix}→ Source: {node.source_info}")
    
    # Format children
    for i, child in enumerate(node.children):
        child_is_last = (i == len(node.children) - 1)
        lines.extend(_format_node(child, child_prefix, child_is_last))
    
    return lines


def format_compact_tree(tree: DependencyTree) -> str:
    """
    Format tree in a more compact single-line-per-node style.
    
    Useful for embedding in LLM prompts.
    """
    lines = []
    
    def _format_compact(node: DependencyNode, indent: int = 0):
        prefix = "  " * indent + "• "
        line = f"{prefix}{node.answer_key}"
        if node.condition:
            line += f" {node.condition}"
        if node.label and node.label != node.answer_key:
            line += f" ({node.label})"
        lines.append(line)
        
        for child in node.children:
            _format_compact(child, indent + 1)
    
    for root in tree.roots:
        _format_compact(root)
    
    return "\n".join(lines)


def tree_to_dict(tree: DependencyTree) -> dict:
    """
    Convert DependencyTree to a dictionary for JSON serialization.
    """
    def node_to_dict(node: DependencyNode) -> dict:
        return {
            "answer_key": node.answer_key,
            "label": node.label,
            "condition": node.condition,
            "value": node.value,
            "source_sheet": node.source_sheet,
            "source_info": node.source_info,
            "depth": node.depth,
            "children": [node_to_dict(c) for c in node.children]
        }
    
    return {
        "roots": [node_to_dict(r) for r in tree.roots],
        "total_nodes": tree.total_nodes,
        "max_depth_reached": tree.max_depth_reached,
        "unresolved_keys": tree.unresolved_keys
    }
