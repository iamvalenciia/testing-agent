"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         HAMMER CHAT CLI                                      ║
║                                                                              ║
║  Interactive command-line interface for chatting with The Hammer data.      ║
║  Uses Rich for beautiful colored output.                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt
from rich import box

from src.agents.hammer_chat import HammerChatAgent


class HammerChatCLI:
    """
    Interactive CLI for the Hammer Chat Agent.
    
    Features:
    - Colored output with Rich
    - Source citations with relevance scores
    - Help command
    - Index statistics command
    """
    
    def __init__(self):
        """Initialize the CLI with console and chat agent."""
        self.console = Console()
        self.agent = None  # Lazy initialization
        
    def _init_agent(self):
        """Initialize the chat agent (lazy loading)."""
        if self.agent is None:
            with self.console.status("[bold cyan]Connecting to The Hammer knowledge base...[/]"):
                self.agent = HammerChatAgent()
    
    def print_banner(self):
        """Display the welcome banner."""
        banner = """
[bold cyan]🔨 HAMMER CHAT[/bold cyan]
[dim]Ask questions about The Hammer data[/dim]
[dim]Commands: [bold]help[/bold] | [bold]stats[/bold] | [bold]tree[/bold] | [bold]exit[/bold][/dim]
"""
        self.console.print(Panel(banner, box=box.DOUBLE_EDGE, border_style="cyan"))
    
    def print_help(self):
        """Display help information."""
        help_table = Table(title="Available Commands", box=box.ROUNDED)
        help_table.add_column("Command", style="cyan", no_wrap=True)
        help_table.add_column("Description", style="white")
        
        help_table.add_row("help", "Show this help message")
        help_table.add_row("stats", "Show knowledge base statistics")
        help_table.add_row("tree", "Enable tree mode (resolves dependency chains)")
        help_table.add_row("exit / quit", "Exit the chat")
        help_table.add_row("<your question>", "Ask anything about The Hammer")
        
        self.console.print(help_table)
        self.console.print()
    
    def print_stats(self):
        """Display knowledge base statistics."""
        self._init_agent()
        stats = self.agent.get_stats()
        
        stats_table = Table(title="📊 Knowledge Base Statistics", box=box.ROUNDED)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Total Vectors", f"{stats.get('total_vector_count', 0):,}")
        stats_table.add_row("Dimension", str(stats.get('dimension', 'N/A')))
        stats_table.add_row("Index Fullness", f"{stats.get('index_fullness', 0):.2%}")
        
        self.console.print(stats_table)
        self.console.print()
    
    def print_response(self, result: dict):
        """
        Display the chat response with sources.
        
        Args:
            result: Response dict with 'answer' and 'sources'
        """
        # Print the answer
        self.console.print()
        self.console.print("[bold green]🤖 Assistant:[/bold green]")
        self.console.print(Markdown(result["answer"]))
        
        # Print sources if available
        if result.get("sources"):
            self.console.print()
            sources_table = Table(
                title="📚 Sources",
                box=box.SIMPLE,
                show_header=True,
                header_style="bold magenta"
            )
            sources_table.add_column("Sheet", style="cyan", no_wrap=True)
            sources_table.add_column("Score", style="green", justify="right")
            sources_table.add_column("Preview", style="dim", max_width=50)
            
            for source in result["sources"][:5]:  # Show top 5 sources
                score_str = f"{source['score']:.2f}"
                sources_table.add_row(
                    source["sheet_name"],
                    score_str,
                    source.get("preview", "")[:50]
                )
            
            self.console.print(sources_table)
        
        self.console.print()
    
    def run(self):
        """Run the interactive chat loop."""
        self.print_banner()
        tree_mode = False  # Track tree mode state
        
        while True:
            try:
                # Show mode indicator in prompt
                mode_indicator = "[bold green][TREE][/bold green] " if tree_mode else ""
                user_input = Prompt.ask(f"{mode_indicator}[bold yellow]You[/bold yellow]")
                
                # Handle empty input
                if not user_input.strip():
                    continue
                
                # Handle commands
                command = user_input.strip().lower()
                
                if command in ["exit", "quit", "q"]:
                    self.console.print("[dim]Goodbye! 👋[/dim]")
                    break
                
                elif command == "help":
                    self.print_help()
                    continue
                
                elif command == "stats":
                    self.print_stats()
                    continue
                
                elif command == "tree":
                    tree_mode = not tree_mode
                    status = "[bold green]ENABLED[/bold green]" if tree_mode else "[bold red]DISABLED[/bold red]"
                    self.console.print(f"🌳 Tree mode {status} - Dependency resolution {'active' if tree_mode else 'inactive'}")
                    continue
                
                # Process as a question
                self._init_agent()
                
                if tree_mode:
                    with self.console.status("[bold cyan]Building dependency tree...[/]"):
                        result = self.agent.chat_with_tree(user_input)
                else:
                    with self.console.status("[bold cyan]Searching The Hammer...[/]"):
                        result = self.agent.chat(user_input)
                
                self.print_response(result)
                
            except KeyboardInterrupt:
                self.console.print("\n[dim]Interrupted. Goodbye! 👋[/dim]")
                break
            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
                continue


def main():
    """Entry point for the CLI."""
    cli = HammerChatCLI()
    cli.run()


if __name__ == "__main__":
    main()
