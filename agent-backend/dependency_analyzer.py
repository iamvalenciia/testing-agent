"""
Dependency Analyzer Service.

This service is the brain of the "Production Mode" advisor.
It analyzes a Ticket (Goal/Description) and finds relationships in the Semantic Hammer Index.

Core Responsibilities:
1. Search Hammer Index for concepts in the Ticket
2. Traverse relationships (Group, Answer Key, Logic)
3. Generate a "Test Plan Guidance" report telling the user what to verify.
"""
from typing import List, Dict, Any, Optional
from pinecone_service import PineconeService, IndexType
from screenshot_embedder import get_embedder

class DependencyAnalyzer:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DependencyAnalyzer()
        return cls._instance
        
    def __init__(self):
        self.pinecone_service = PineconeService()
        self.embedder = get_embedder()
        
    async def analyze_ticket(self, ticket_text: str, top_k: int = 15) -> Dict[str, Any]:
        """
        Analyze a ticket description and find affected Hammer workflows.
        
        Args:
            ticket_text: The full text of the Jira ticket / User request
            top_k: Number of semantic matches to retrieve
            
        Returns:
            Dict containing:
            - related_nodes: List of Hammer rows found
            - suggested_actions: List of text actions (e.g. "Verify Group X")
            - questions_to_answer: specific questions found in the nodes
        """
        print(f"[DEP_ANALYZER] Analyzing ticket: {ticket_text[:50]}...")
        
        # 1. Search Hammer Index using existing hybrid search method
        # query_hammer handles embedding + hybrid search internally
        matches = self.pinecone_service.query_hammer(
            query_text=ticket_text,
            top_k=top_k,
            use_hybrid=True
        )
        
        if not matches:
             return {
                 "found": False,
                 "message": "No relevant Hammer configuration found."
             }
             
        # 3. Analyze & Group Results
        # We group by "Workflow/Group" to give coherent advice
        groups_found = {}
        
        nodes = []
        questions = []
        
        for match in matches:
            meta = match.get("metadata", {})
            score = match.get("score", 0)
            
            # Extract semantic fields we added in ETL
            group = meta.get("hammer_group", "General")
            q_id = meta.get("hammer_id", "Unknown")
            q_text = meta.get("hammer_question", "")
            ans_key = meta.get("hammer_answer_key", "")
            logic = meta.get("logic_summary", "")
            
            node_data = {
                "id": str(match.get("id")),
                "score": score,
                "group": group,
                "question_id": q_id,
                "question": q_text,
                "answer_key": ans_key,
                "logic": logic,
                "raw_text": meta.get("text", "")
            }
            nodes.append(node_data)
            
            if group not in groups_found:
                groups_found[group] = []
            groups_found[group].append(node_data)
            
        # 4. Synthesize Guidance
        guidance = []
        
        guidance.append(f"Found {len(matches)} relevant configuration points across {len(groups_found)} groups.")
        
        for group, group_nodes in groups_found.items():
            # Sort by relevance
            group_nodes.sort(key=lambda x: x["score"], reverse=True)
            top_node = group_nodes[0]
            
            guidance.append(f"\n### Group: {group}")
            guidance.append(f"Most relevant rule: {top_node['logic'] if top_node['logic'] else top_node['raw_text'][:100]}")
            
            # Check for Answer Keys dependencies
            keys = [n['answer_key'] for n in group_nodes if n['answer_key']]
            if keys:
                guidance.append(f"- Involves Answer Keys: {', '.join(set(keys))}")
                
            # Collect specific questions
            for n in group_nodes:
                if n['question']:
                    questions.append(f"[{group}] {n['question']} (Key: {n['answer_key']})")

        return {
            "found": True,
            "ticket_summary": ticket_text[:100],
            "relevant_groups": list(groups_found.keys()),
            "guidance_text": "\n".join(guidance),
            "questions_to_verify": list(set(questions)), # Dedup
            "raw_matches": nodes
        }

def get_dependency_analyzer():
    return DependencyAnalyzer.get_instance()
