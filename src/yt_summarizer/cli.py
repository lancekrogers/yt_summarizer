"""
Interactive CLI with TUI for YouTube video summarization.

Provides user-friendly prompts for input selection, progress display, and post-run actions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import questionary
from yaspin import yaspin

from .config import config
from .llm import LLMConnectionError, ensure_connection
from .pipeline import check_prerequisites, process_video_list, process_single_video
from .transcript import clear_cache, get_cache_stats, extract_video_id, TranscriptError
from .utils import read_video_list, format_file_size


def startup_check() -> bool:
    """
    Perform startup checks and display results.
    
    Returns:
        True if all checks pass, False otherwise.
    """
    print("🚀 YouTube Summarizer Starting Up...")
    
    try:
        return check_prerequisites()
    except LLMConnectionError as e:
        print(f"❌ {e}")
        print("\n💡 Make sure Ollama is running:")
        print("   ollama serve")
        return False
    except Exception as e:
        print(f"❌ Unexpected startup error: {e}")
        return False


def get_input_source() -> tuple[str, List[str]]:
    """
    Prompt user to select input source and return video list.
    
    Returns:
        Tuple of (source_type, video_list).
    """
    # Check if default video list exists
    default_file = Path(config.DEFAULT_VIDEO_LIST)
    
    choices = ["📄 Custom file", "🔗 Single URL"]
    if default_file.exists():
        choices.insert(0, f"📋 Default file ({config.DEFAULT_VIDEO_LIST})")
    
    source = questionary.select(
        "Choose input source:",
        choices=choices
    ).ask()
    
    if not source:  # User cancelled
        sys.exit(0)
    
    if "Default file" in source:
        videos = read_video_list(default_file)
        return "default_file", videos
    
    elif "Custom file" in source:
        def get_compatible_files(directory: Path = None) -> List[str]:
            """Get list of compatible video list files in the given directory."""
            if directory is None:
                directory = Path.cwd()
            
            supported_extensions = {'.txt', '.list', '.urls', '.csv'}
            compatible_files = []
            
            try:
                for file_path in directory.iterdir():
                    if (file_path.is_file() and 
                        file_path.suffix.lower() in supported_extensions):
                        compatible_files.append(str(file_path))
                
                # Sort by name for consistent ordering
                compatible_files.sort()
                
            except PermissionError:
                pass  # Skip directories we can't read
            
            return compatible_files
        
        # Get compatible files in current directory
        current_dir_files = get_compatible_files()
        
        choices = []
        if current_dir_files:
            choices.extend([f"📄 {Path(f).name}" for f in current_dir_files])
        
        choices.extend([
            "📁 Browse other directory",
            "✏️  Enter path manually"
        ])
        
        if not choices or len(choices) == 2:  # Only browse/manual options
            choices = [
                "📁 Browse other directory", 
                "✏️  Enter path manually"
            ]
        
        selection = questionary.select(
            "Select video list file:",
            choices=choices
        ).ask()
        
        if not selection:
            sys.exit(0)
        
        if "Browse other directory" in selection:
            # Let user pick a directory first
            dir_path = questionary.path(
                "Enter directory to browse:",
                only_directories=True
            ).ask()
            
            if not dir_path:
                sys.exit(0)
            
            # Get compatible files in selected directory
            dir_files = get_compatible_files(Path(dir_path))
            
            if not dir_files:
                print(f"❌ No compatible files (.txt, .list, .urls, .csv) found in {dir_path}")
                sys.exit(1)
            
            file_selection = questionary.select(
                f"Select file from {dir_path}:",
                choices=[f"📄 {Path(f).name}" for f in dir_files]
            ).ask()
            
            if not file_selection:
                sys.exit(0)
            
            # Extract filename and construct full path
            filename = file_selection.replace("📄 ", "")
            file_path = str(Path(dir_path) / filename)
            
        elif "Enter path manually" in selection:
            def validate_video_list_file(path_str: str) -> bool | str:
                """Validate that the file exists and is a supported format."""
                if not path_str.strip():
                    return "Please enter a file path"
                
                path = Path(path_str.strip())
                if not path.exists():
                    return "File does not exist"
                
                if not path.is_file():
                    return "Path is not a file"
                
                # Check file extension
                supported_extensions = {'.txt', '.list', '.urls', '.csv'}
                if path.suffix.lower() not in supported_extensions:
                    return f"Unsupported file type. Use: {', '.join(sorted(supported_extensions))}"
                
                return True
            
            file_path = questionary.path(
                "Enter path to video list file (.txt, .list, .urls, .csv):",
                validate=validate_video_list_file
            ).ask()
            
            if not file_path:
                sys.exit(0)
        
        else:
            # User selected a file from current directory
            filename = selection.replace("📄 ", "")
            file_path = filename  # It's already the filename from current directory
        
        videos = read_video_list(Path(file_path))
        return "custom_file", videos
    
    elif "Single URL" in source:
        url = questionary.text(
            "Enter YouTube URL or video ID:"
        ).ask()
        
        if not url:
            sys.exit(0)
        
        # Validate the URL/ID
        try:
            extract_video_id(url.strip())
        except TranscriptError as e:
            print(f"❌ Invalid URL/ID: {e}")
            sys.exit(1)
        
        return "single_url", [url.strip()]
    
    else:
        sys.exit(0)


def get_processing_options() -> dict:
    """
    Get processing options from user.
    
    Returns:
        Dictionary with processing options.
    """
    # Model selection
    model = questionary.text(
        "Ollama model to use:",
        default=config.OLLAMA_MODEL
    ).ask()
    
    if not model:
        model = config.OLLAMA_MODEL
    
    # Cache option
    use_cache = questionary.confirm(
        "Use cached transcripts if available?",
        default=True
    ).ask()
    
    return {
        "model": model.strip(),
        "use_cache": use_cache
    }


def handle_file_conflicts(video_count: int) -> bool:
    """
    Ask user how to handle existing files.
    
    Args:
        video_count: Number of videos to process.
        
    Returns:
        True to auto-overwrite, False to handle individually.
    """
    if video_count == 1:
        return False  # Handle individually for single video
    
    choice = questionary.select(
        "How to handle existing summary files?",
        choices=[
            "🤔 Ask for each file",
            "🔄 Overwrite all existing files",
            "📝 Create new versions (file_v2.md)"
        ]
    ).ask()
    
    if "Overwrite all" in choice:
        return True
    else:
        return False


def post_run_menu() -> bool:
    """
    Show post-run menu and handle user choice.
    
    Returns:
        True to continue running, False to exit.
    """
    cache_stats = get_cache_stats()
    cache_info = f"({cache_stats['total_files']} files, {format_file_size(cache_stats['total_size_bytes'])})"
    
    choice = questionary.select(
        "\nWhat would you like to do next?",
        choices=[
            "➕ Summarize more videos",
            f"🧹 Clean transcript cache {cache_info}",
            "🚪 Quit"
        ]
    ).ask()
    
    if not choice or "Quit" in choice:
        return False
    
    elif "Clean transcript cache" in choice:
        confirm = questionary.confirm(
            f"Delete {cache_stats['total_files']} cached transcript files?",
            default=False
        ).ask()
        
        if confirm:
            deleted = clear_cache()
            print(f"✓ Deleted {deleted} cached files")
        
        return post_run_menu()  # Show menu again
    
    elif "Summarize more" in choice:
        return True
    
    else:
        return False


def interactive_main() -> None:
    """Main interactive CLI entry point."""
    print("📼→📝 YouTube Summarizer")
    print("=" * 50)
    
    # Startup checks
    if not startup_check():
        choice = questionary.confirm(
            "Startup checks failed. Retry?",
            default=True
        ).ask()
        
        if choice:
            return interactive_main()  # Retry
        else:
            sys.exit(1)
    
    # Main processing loop
    while True:
        try:
            # Get input source
            source_type, videos = get_input_source()
            print(f"\n📋 Found {len(videos)} video(s) to process")
            
            # Get processing options
            options = get_processing_options()
            
            # Handle file conflicts
            auto_overwrite = handle_file_conflicts(len(videos))
            
            print(f"\n🎬 Processing {len(videos)} video(s) with {options['model']}...")
            
            # Process videos
            stats = process_video_list(
                video_urls=videos,
                model=options['model'],
                use_cache=options['use_cache'],
                auto_overwrite=auto_overwrite
            )
            
            # Show results
            print(f"\n📊 Results:")
            print(f"   ✅ Successful: {stats.successful}")
            if stats.failed > 0:
                print(f"   ❌ Failed: {stats.failed}")
            if stats.skipped > 0:
                print(f"   ⏭️  Skipped: {stats.skipped}")
            
            # Post-run menu
            if not post_run_menu():
                break
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            
            retry = questionary.confirm(
                "An error occurred. Try again?",
                default=False
            ).ask()
            
            if not retry:
                break
    
    print("\n👋 Thanks for using YouTube Summarizer!")


def legacy_main() -> None:
    """Legacy CLI for backwards compatibility."""
    parser = argparse.ArgumentParser(
        description="YouTube transcript → Ollama summary",
        epilog="For interactive mode, run without arguments"
    )
    parser.add_argument(
        "list_file", 
        nargs='?',
        help="Text file of YouTube URLs/IDs"
    )
    parser.add_argument(
        "--model", 
        default=config.OLLAMA_MODEL, 
        help="Ollama model tag"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Use interactive mode (default if no list_file provided)"
    )
    
    args = parser.parse_args()
    
    # If no list file provided or interactive flag set, use interactive mode
    if not args.list_file or args.interactive:
        interactive_main()
        return
    
    # Legacy mode: direct file processing
    print("📼→📝 YouTube Summarizer (Legacy Mode)")
    
    if not startup_check():
        sys.exit(1)
    
    try:
        videos = read_video_list(Path(args.list_file))
        stats = process_video_list(videos, model=args.model)
        
        if stats.failed > 0:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    # Default to interactive mode for better UX
    if len(sys.argv) == 1:
        interactive_main()
    else:
        legacy_main()


if __name__ == "__main__":
    main()