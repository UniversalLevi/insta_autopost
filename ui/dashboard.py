"""InstaForge Terminal Dashboard - Main UI Entry Point"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.align import Align
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn
import yaml

from src.app import InstaForgeApp
from src.models.post import PostMedia
from pydantic import HttpUrl
from .image_fetcher import ImageFetcher

console = Console()


class InstaForgeDashboard:
    """Main dashboard class for InstaForge UI"""
    
    def __init__(self):
        self.app: Optional[InstaForgeApp] = None
        self.image_fetcher = ImageFetcher()
        self.saved_images: List[Dict[str, Any]] = []
        self.running = True
        
    def initialize_app(self):
        """Initialize the InstaForge application"""
        try:
            console.print("[bold blue]Initializing InstaForge...[/bold blue]")
            self.app = InstaForgeApp()
            self.app.initialize()
            console.print("[bold green]✓ Application initialized[/bold green]\n")
            return True
        except Exception as e:
            console.print(f"[bold red]✗ Initialization failed: {e}[/bold red]\n")
            return False
    
    def show_dashboard(self):
        """Display main dashboard with status information"""
        console.clear()
        
        if not self.app:
            if not self.initialize_app():
                return
        
        accounts = self.app.account_service.list_accounts()
        if not accounts:
            console.print("[bold red]No accounts configured![/bold red]")
            return
        
        account = accounts[0]
        config = self.app.config
        
        # Get warming status
        warming_enabled = account.warming.enabled if account.warming else False
        warming_schedule = config.warming.schedule_time if config else "09:00"
        
        # Create dashboard layout
        header = Panel(
            Align.center(Text("InstaForge Dashboard", style="bold white")),
            style="bold blue",
            box=box.DOUBLE
        )
        
        # Status table
        status_table = Table(title="System Status", box=box.ROUNDED, show_header=True)
        status_table.add_column("Metric", style="cyan", width=25)
        status_table.add_column("Value", style="green", width=30)
        
        status_table.add_row("App Status", "[green]Running[/green]")
        status_table.add_row("Instagram Account", account.username)
        status_table.add_row("Account ID", account.account_id)
        status_table.add_row("Warming Status", "[green]Enabled[/green]" if warming_enabled else "[red]Disabled[/red]")
        status_table.add_row("Warming Schedule", warming_schedule)
        status_table.add_row("Daily Actions", str(account.warming.daily_actions) if account.warming else "0")
        
        # Action types
        action_types = ", ".join(account.warming.action_types) if account.warming else "None"
        status_table.add_row("Action Types", action_types)
        
        # Layout
        console.print(header)
        console.print()
        console.print(status_table)
        console.print()
        
        # Menu
        self.show_menu()
    
    def show_menu(self):
        """Display main menu"""
        menu_text = """
[bold cyan]Main Menu:[/bold cyan]

[1] Trending Images - Fetch and save images for posting
[2] Post to Instagram - Create and publish a post
[3] Warming Control - Manage warming actions
[4] Activity Logs - View recent activity
[5] Refresh Dashboard - Update status
[Q] Quit

"""
        console.print(Panel(menu_text, title="Menu", border_style="cyan"))
        
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "q", "Q"], default="5")
        
        if choice == "1":
            self.trending_images_menu()
        elif choice == "2":
            self.posting_menu()
        elif choice == "3":
            self.warming_control_menu()
        elif choice == "4":
            self.view_logs()
        elif choice == "5":
            self.show_dashboard()
        elif choice.lower() == "q":
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)
    
    def trending_images_menu(self):
        """Trending images fetcher menu"""
        console.clear()
        console.print(Panel("Trending Images Fetcher", title="Menu", border_style="green"))
        console.print()
        
        # Source selection
        source = Prompt.ask(
            "Select image source",
            choices=["reddit", "unsplash", "pexels"],
            default="reddit"
        )
        
        if source == "reddit":
            subreddit = Prompt.ask("Enter subreddit name", default="pics")
            limit = int(Prompt.ask("Number of images", default="10"))
            
            console.print(f"\n[bold blue]Fetching images from r/{subreddit}...[/bold blue]")
            images = self.image_fetcher.fetch_reddit_images(subreddit, limit)
        
        elif source == "unsplash":
            query = Prompt.ask("Enter search query", default="nature")
            limit = int(Prompt.ask("Number of images", default="10"))
            
            console.print(f"\n[bold blue]Fetching images from Unsplash...[/bold blue]")
            images = self.image_fetcher.fetch_unsplash_images(query, limit)
        
        elif source == "pexels":
            query = Prompt.ask("Enter search query", default="nature")
            limit = int(Prompt.ask("Number of images", default="10"))
            
            console.print(f"\n[bold blue]Fetching images from Pexels...[/bold blue]")
            images = self.image_fetcher.fetch_pexels_images(query, limit)
        
        # Display images
        if not images or (images and images[0].get("url") is None):
            console.print("[yellow]No images found or API key required.[/yellow]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        console.print(f"\n[bold green]Found {len(images)} images:[/bold green]\n")
        
        # Display image table
        img_table = Table(title="Available Images", box=box.ROUNDED)
        img_table.add_column("#", style="cyan", width=4)
        img_table.add_column("Title", style="white", width=40)
        img_table.add_column("Author", style="yellow", width=20)
        img_table.add_column("Source", style="green", width=10)
        
        for idx, img in enumerate(images, 1):
            title = img.get("title", "No title")[:37] + "..." if len(img.get("title", "")) > 40 else img.get("title", "No title")
            img_table.add_row(
                str(idx),
                title,
                img.get("author", "Unknown"),
                img.get("source", "unknown")
            )
        
        console.print(img_table)
        console.print()
        
        # Select image to save
        selection = Prompt.ask("Select image number to save (or 'all' for all, 'back' to return)", default="back")
        
        if selection.lower() == "back":
            self.show_dashboard()
            return
        elif selection.lower() == "all":
            self.saved_images.extend(images)
            console.print(f"[green]✓ Saved {len(images)} images[/green]")
        elif selection.isdigit():
            idx = int(selection) - 1
            if 0 <= idx < len(images):
                self.saved_images.append(images[idx])
                console.print(f"[green]✓ Saved image: {images[idx].get('title', 'Unknown')}[/green]")
            else:
                console.print("[red]Invalid selection[/red]")
        
        input("\nPress Enter to continue...")
        self.show_dashboard()
    
    def posting_menu(self):
        """Daily posting control menu"""
        console.clear()
        console.print(Panel("Daily Posting Control", title="Menu", border_style="green"))
        console.print()
        
        if not self.app:
            console.print("[red]Application not initialized[/red]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        accounts = self.app.account_service.list_accounts()
        if not accounts:
            console.print("[red]No accounts configured[/red]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        account = accounts[0]
        
        # Show saved images
        if self.saved_images:
            console.print("[bold cyan]Saved Images:[/bold cyan]\n")
            for idx, img in enumerate(self.saved_images, 1):
                console.print(f"  [{idx}] {img.get('title', 'No title')[:50]}")
            console.print()
        
        # Get image URL
        use_saved = False
        if self.saved_images:
            use_saved = Confirm.ask("Use a saved image?", default=False)
        
        if use_saved:
            idx = int(Prompt.ask("Select saved image number", default="1")) - 1
            if 0 <= idx < len(self.saved_images):
                image_url = self.saved_images[idx].get("url")
                console.print(f"[green]Using: {self.saved_images[idx].get('title', 'Unknown')}[/green]\n")
            else:
                console.print("[red]Invalid selection[/red]")
                image_url = Prompt.ask("Enter image URL")
        else:
            image_url = Prompt.ask("Enter image URL (must be HTTPS and publicly accessible)")
        
        if not image_url or not image_url.startswith("https://"):
            console.print("[red]Invalid image URL! Must use HTTPS[/red]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        # Get caption
        caption = Prompt.ask("Enter caption (optional)", default="")
        
        # Get hashtags
        hashtags_input = Prompt.ask("Enter hashtags (comma-separated, optional)", default="")
        hashtags = [tag.strip().replace("#", "") for tag in hashtags_input.split(",") if tag.strip()] if hashtags_input else []
        
        # Post now or schedule
        post_now = Confirm.ask("Post immediately? (Yes) or Schedule later (No)", default=True)
        
        try:
            # Create media object
            media = PostMedia(
                media_type="image",
                url=HttpUrl(image_url),
            )
            
            # Create post
            post = self.app.posting_service.create_post(
                account_id=account.account_id,
                media=media,
                caption=caption,
            )
            
            # Add hashtags
            post.hashtags = hashtags
            
            if post_now:
                console.print("\n[bold blue]Publishing post...[/bold blue]")
                
                try:
                    published_post = self.app.posting_service.publish_post_with_retry(post)
                    
                    console.print(f"\n[bold green]✓ Post published successfully![/bold green]")
                    console.print(f"  Instagram Media ID: {published_post.instagram_media_id}")
                    console.print(f"  Published at: {published_post.published_at}")
                    
                except Exception as e:
                    console.print(f"\n[bold red]✗ Posting failed: {e}[/bold red]")
            else:
                console.print(f"\n[green]Post created (not published yet)[/green]")
                console.print(f"  Post ID: {post.post_id}")
                console.print(f"  Status: {post.status}")
        
        except Exception as e:
            console.print(f"\n[bold red]✗ Error: {e}[/bold red]")
        
        input("\nPress Enter to continue...")
        self.show_dashboard()
    
    def warming_control_menu(self):
        """Warming control menu"""
        console.clear()
        console.print(Panel("Warming Control", title="Menu", border_style="green"))
        console.print()
        
        if not self.app:
            console.print("[red]Application not initialized[/red]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        accounts = self.app.account_service.list_accounts()
        if not accounts:
            console.print("[red]No accounts configured[/red]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        account = accounts[0]
        warming_enabled = account.warming.enabled if account.warming else False
        
        # Show current status
        status_table = Table(title="Warming Status", box=box.ROUNDED)
        status_table.add_column("Setting", style="cyan")
        status_table.add_column("Value", style="green")
        
        status_table.add_row("Enabled", "[green]Yes[/green]" if warming_enabled else "[red]No[/red]")
        status_table.add_row("Daily Actions", str(account.warming.daily_actions) if account.warming else "0")
        status_table.add_row("Action Types", ", ".join(account.warming.action_types) if account.warming else "None")
        status_table.add_row("Schedule Time", self.app.config.warming.schedule_time if self.app.config else "N/A")
        
        console.print(status_table)
        console.print()
        
        # Menu options
        console.print("[1] Run warming now (manual trigger)")
        console.print("[2] Toggle warming (requires config edit)")
        console.print("[3] View warming statistics")
        console.print("[B] Back to main menu")
        console.print()
        
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "b", "B"], default="B")
        
        if choice == "1":
            console.print("\n[bold blue]Running warming actions now...[/bold blue]")
            try:
                results = self.app.run_warming_now()
                console.print("[green]✓ Warming actions completed[/green]")
                console.print(f"  Results: {json.dumps(results, indent=2, default=str)}")
            except Exception as e:
                console.print(f"[red]✗ Warming failed: {e}[/red]")
            input("\nPress Enter to continue...")
            self.warming_control_menu()
        
        elif choice == "2":
            console.print("\n[yellow]To toggle warming, edit config/accounts.yaml[/yellow]")
            console.print("  Set 'warming.enabled: true/false'")
            input("\nPress Enter to continue...")
            self.warming_control_menu()
        
        elif choice == "3":
            # Show statistics (placeholder - would need to track actual stats)
            console.print("\n[yellow]Warming Statistics:[/yellow]")
            console.print("  Daily actions configured: ", account.warming.daily_actions if account.warming else 0)
            console.print("  Action types: ", ", ".join(account.warming.action_types) if account.warming else "None")
            input("\nPress Enter to continue...")
            self.warming_control_menu()
        
        else:
            self.show_dashboard()
    
    def view_logs(self, lines: int = 50):
        """View activity logs from log file"""
        console.clear()
        console.print(Panel("Activity Log Viewer", title="Menu", border_style="green"))
        console.print()
        
        log_path = Path("logs/instaforge.log")
        
        if not log_path.exists():
            console.print("[yellow]No log file found at logs/instaforge.log[/yellow]")
            input("\nPress Enter to continue...")
            self.show_dashboard()
            return
        
        try:
            # Read last N lines
            with open(log_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            # Display logs
            console.print(f"[cyan]Last {len(recent_lines)} log entries:[/cyan]\n")
            
            log_table = Table(box=box.SIMPLE, show_header=False)
            log_table.add_column("Log Entry", style="white")
            
            for line in recent_lines:
                # Try to parse JSON log entries
                try:
                    log_data = json.loads(line.strip())
                    event = log_data.get("event", "Unknown")
                    level = log_data.get("level", "info").upper()
                    
                    if level == "ERROR":
                        style = "red"
                    elif level == "WARNING":
                        style = "yellow"
                    elif level == "INFO":
                        style = "cyan"
                    else:
                        style = "white"
                    
                    timestamp = log_data.get("timestamp", "")[:19]  # ISO format
                    log_entry = f"[{style}]{timestamp} [{level}] {event}[/{style}]"
                    
                    log_table.add_row(log_entry)
                except Exception:
                    # Plain text log entry
                    log_table.add_row(line.strip()[:100])
            
            console.print(log_table)
        
        except Exception as e:
            console.print(f"[red]Error reading logs: {e}[/red]")
        
        console.print("\n[R]efresh | [B]ack")
        choice = Prompt.ask("Select option", choices=["r", "R", "b", "B"], default="B")
        
        if choice.lower() == "r":
            self.view_logs(lines)
        else:
            self.show_dashboard()


def main():
    """Main entry point for dashboard"""
    dashboard = InstaForgeDashboard()
    
    try:
        # Show dashboard loop
        while dashboard.running:
            dashboard.show_dashboard()
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting dashboard...[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    main()
