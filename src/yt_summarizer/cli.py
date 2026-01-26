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

from .config import config, CONFIG_DIR, CONFIG_FILE, create_default_config
from .llm import LLMConnectionError, ensure_connection
from .pipeline import check_prerequisites, process_video_list, process_single_video
from .transcript import clear_cache, get_cache_stats, extract_video_id, TranscriptError
from .utils import read_video_list, format_file_size


def ensure_initialized() -> bool:
    """Ensure config directory and default config exist.

    Creates XDG-compliant configuration directory and default config.yaml
    on first run.

    Returns:
        True if this is the first run, False otherwise.
    """
    first_run = not CONFIG_DIR.exists()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        create_default_config()

    return first_run


def check_migration_needed() -> None:
    """Check if user has legacy data that should be migrated.

    Prompts user to migrate data from current working directory to
    XDG-compliant configuration location if legacy data is detected.
    """
    from .migrate import detect_legacy_data, is_migration_needed, migrate_legacy_data, get_migration_summary

    legacy = detect_legacy_data()
    if not is_migration_needed(legacy, CONFIG_DIR):
        return

    # Show what was detected
    summary = get_migration_summary(legacy)
    print("\n[yellow]Legacy data detected in current directory:[/yellow]".replace("[yellow]", "").replace("[/yellow]", ""))

    for name, count in summary.items():
        print(f"  - {name}/ ({count} files)")

    print(f"\nNew configuration location: {CONFIG_DIR}")

    choice = questionary.select(
        "How would you like to handle existing data?",
        choices=[
            "Move data to new location (recommended)",
            "Copy data to new location",
            "Skip migration (continue using current directory)"
        ]
    ).ask()

    if not choice or "Skip" in choice:
        print("Skipping migration. Data will remain in current directory.")
        print("Note: You can migrate manually later or set DATA_DIR in config.yaml")
        return

    copy_mode = "Copy" in choice
    result = migrate_legacy_data(legacy, CONFIG_DIR, copy=copy_mode)

    if result.success:
        action = "Copied" if copy_mode else "Moved"
        print(f"\n✅ {action} {len(result.moved)} directories to {CONFIG_DIR}")
        for source, target in result.moved:
            print(f"   {source.name}/ → {target}")
    elif result.partial_success:
        print(f"\n⚠️  Partial migration: {len(result.moved)} succeeded, {len(result.errors)} failed")
        for source, error in result.errors:
            print(f"   ❌ {source}: {error}")
    else:
        print(f"\n❌ Migration failed:")
        for source, error in result.errors:
            print(f"   {source}: {error}")


def startup_check() -> bool:
    """
    Perform startup checks and display results.

    Returns:
        True if all checks pass, False otherwise.
    """
    # First-run initialization
    first_run = ensure_initialized()

    if first_run:
        print("🎉 Welcome to YouTube Summarizer!")
        print(f"📁 Configuration created at: {CONFIG_DIR}")
        print(f"📝 Edit {CONFIG_FILE.name} to customize settings.\n")

    # Check for legacy data migration
    check_migration_needed()

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


def get_main_menu_choice() -> str:
    """
    Display main menu and get user's choice.
    
    Returns:
        Selected menu option.
    """
    choices = [
        "📼 Process Videos",
        "🔬 Research Plan",
        "🗑️  Clean Cache",
        "❌ Exit"
    ]
    
    choice = questionary.select("What would you like to do?", choices=choices).ask()
    
    if not choice:
        sys.exit(0)
    
    return choice


def get_research_plan_menu_choice() -> str:
    """
    Display research plan menu and get user's choice.
    
    Returns:
        Selected menu option.
    """
    from .research_plan import list_research_plans
    
    existing_plans = list_research_plans()
    
    choices = ["📝 Create New Research Plan"]
    
    if existing_plans:
        choices.append("📂 Select Existing Research Plan")
    
    choices.extend(["🔙 Back to Main Menu"])
    
    choice = questionary.select("Research Plan Options:", choices=choices).ask()
    
    if not choice:
        sys.exit(0)
    
    return choice


def create_research_plan_interactive() -> str | None:
    """
    Interactive research plan creation wizard.
    
    Returns:
        Plan ID if created successfully, None if cancelled.
    """
    from .research_plan import ResearchPlanManager, ResearchPlanError
    import yaml
    
    while True:
        # Get plan name
        plan_name = questionary.text(
            "Enter research plan name:",
            validate=lambda x: len(x.strip()) > 0 or "Plan name cannot be empty"
        ).ask()
        
        if not plan_name:
            return None
        
        plan_name = plan_name.strip()
        
        # Get description
        description = questionary.text(
            "Enter plan description (optional):",
            default=""
        ).ask()
        
        if description is None:
            return None
        
        # Get video input method
        video_input_method = questionary.select(
            "How would you like to provide videos?",
            choices=[
                "📝 Enter URLs manually",
                "📁 Specify a video list file",
                "📝📁 Both URLs and file",
                "⏭️  Skip (add videos later)"
            ]
        ).ask()
        
        if video_input_method is None:
            return None
        
        video_urls = []
        video_list_file = None
        
        # Handle video input based on user choice
        if "Enter URLs manually" in video_input_method or "Both URLs and file" in video_input_method:
            print("\n📋 Enter video URLs (one per line). Press Enter on empty line to finish:")
            url_count = 0
            while True:
                url = questionary.text(
                    f"Video URL {url_count + 1} (or press Enter to finish):",
                    default=""
                ).ask()
                
                if url is None:  # User cancelled
                    return None
                
                url = url.strip()
                if not url:  # Empty line, finish input
                    break
                
                # Basic validation
                if "youtube.com" in url or "youtu.be" in url or url.startswith("http"):
                    video_urls.append(url)
                    url_count += 1
                    print(f"   ✅ Added: {url}")
                else:
                    print(f"   ⚠️  Warning: '{url}' doesn't look like a YouTube URL")
                    add_anyway = questionary.confirm("Add it anyway?", default=False).ask()
                    if add_anyway:
                        video_urls.append(url)
                        url_count += 1
        
        if "Specify a video list file" in video_input_method or "Both URLs and file" in video_input_method:
            while True:
                file_path = questionary.text(
                    "Enter path to video list file (relative to project root):",
                    default="videolist.txt"
                ).ask()
                
                if file_path is None:
                    return None
                
                if not file_path.strip():
                    break  # User left it empty
                
                file_path = file_path.strip()
                
                # Validate that the file exists
                from pathlib import Path
                test_paths = [
                    Path.cwd() / file_path,
                    Path(file_path) if Path(file_path).is_absolute() else None
                ]
                test_paths = [p for p in test_paths if p is not None]
                
                file_exists = any(p.exists() for p in test_paths)
                
                if file_exists:
                    video_list_file = file_path
                    print(f"   ✅ Found: {file_path}")
                    break
                else:
                    print(f"   ⚠️  File not found: {file_path}")
                    choice = questionary.select(
                        "What would you like to do?",
                        choices=[
                            "📝 Enter a different path",
                            "➡️  Continue anyway (file will be checked later)",
                            "⏭️  Skip video list file"
                        ]
                    ).ask()
                    
                    if choice is None:
                        return None
                    elif "Continue anyway" in choice:
                        video_list_file = file_path
                        print(f"   ⚠️  Will attempt to use: {file_path}")
                        break
                    elif "Skip" in choice:
                        break
                    # Otherwise loop to try again
        
        # Show summary
        print(f"\n📋 Video Configuration Summary:")
        if video_urls:
            print(f"   📝 Direct URLs: {len(video_urls)} videos")
            for i, url in enumerate(video_urls[:3], 1):  # Show first 3
                print(f"      {i}. {url}")
            if len(video_urls) > 3:
                print(f"      ... and {len(video_urls) - 3} more")
        else:
            print(f"   📝 Direct URLs: None")
        
        if video_list_file:
            print(f"   📁 Video list file: {video_list_file}")
        else:
            print(f"   📁 Video list file: None")
        
        if not video_urls and not video_list_file:
            print(f"   ⚠️  No videos configured - you'll need to edit the plan later")
        
        # Confirmation
        print(f"\n📋 Plan Details:")
        print(f"   Name: {plan_name}")
        print(f"   Description: {description or 'None'}")
        
        confirm_choice = questionary.select(
            "Confirm plan creation?",
            choices=["✅ Confirm", "✏️  Change Details", "❌ Cancel"]
        ).ask()
        
        if not confirm_choice or "Cancel" in confirm_choice:
            return None
        
        if "Change Details" in confirm_choice:
            continue
        
        # Create the plan with video configuration
        try:
            from .io_utils import sanitize_filename
            plan_id = sanitize_filename(plan_name.lower().replace(" ", "_"))
            
            # Create plan using manager directly so we can customize the video config
            manager = ResearchPlanManager()
            
            # Create custom plan data with videos
            plan_data = {
                "research_plan": {
                    "name": plan_name,
                    "description": description or "Research plan for focused content extraction"
                },
                "videos": {
                    "urls": video_urls,
                    "list_file": video_list_file
                },
                "prompts": {
                    "chunk_prompt": (
                        "You are analyzing YouTube video transcripts for focused content extraction.\n"
                        "Extract and summarize only the relevant content from this transcript chunk:\n\n"
                        "{chunk}\n\n"
                        "Focus on the specific topics and information relevant to the research plan."
                    ),
                    "executive_prompt": (
                        "Create a comprehensive summary by combining these extracted content sections:\n\n"
                        "{bullet_summaries}\n\n"
                        "Provide a clear, well-structured summary that captures the key information and themes."
                    ),
                    "corpus_chunk_prompt": (
                        "You are analyzing a collection of research summaries from multiple videos.\n"
                        "Identify patterns, themes, and insights from this content:\n\n"
                        "{chunk}\n\n"
                        "Focus on connections and recurring themes across the research corpus."
                    ),
                    "corpus_executive_prompt": (
                        "Create a comprehensive analysis of the research corpus by synthesizing these insights:\n\n"
                        "{bullet_summaries}\n\n"
                        "Organize findings by themes, highlight key patterns, and provide actionable insights."
                    )
                },
                "output": {
                    "video_summaries_dir": "data/videos/",
                    "corpus_dir": "data/corpus/",
                    "video_filename_pattern": "{title}_{video_id}.md",
                    "corpus_filename": "{research_plan_name}.md",
                    "corpus_summary_filename": "{research_plan_name}_summary.md"
                }
            }
            
            # Create the plan file
            plan_path = manager._get_plan_path(plan_id)
            
            if plan_path.exists():
                raise ResearchPlanError(f"Research plan '{plan_id}' already exists")
            
            with open(plan_path, 'w', encoding='utf-8') as f:
                yaml.dump(plan_data, f, default_flow_style=False, indent=2, allow_unicode=True)
            
            print(f"\n✅ Research plan created: {plan_path}")
            
            if video_urls or video_list_file:
                print(f"📋 Videos configured - ready to start processing!")
                
                # Ask what to do next
                next_choice = questionary.select(
                    "What would you like to do next?",
                    choices=[
                        "🚀 Start Processing with this Plan",
                        "✏️  Edit Prompts First",
                        "🔙 Back to Research Plan Menu"
                    ]
                ).ask()
                
                if not next_choice:
                    return None
                
                if "Start Processing" in next_choice:
                    return plan_id
                elif "Edit Prompts" in next_choice:
                    print(f"\n💡 Edit your research plan prompts at: {plan_path}")
                    print("   Then restart the application to use your plan.")
                    sys.exit(0)
                else:  # Back to menu
                    return None
            else:
                print(f"📝 Please edit the configuration file to add videos and customize prompts:")
                print(f"   {plan_path}")
                
                # Ask what to do next
                next_choice = questionary.select(
                    "What would you like to do next?",
                    choices=[
                        "🔙 Back to Research Plan Menu",
                        "❌ Exit to Edit Config"
                    ]
                ).ask()
                
                if not next_choice or "Exit" in next_choice:
                    print(f"\n💡 Edit your research plan configuration at: {plan_path}")
                    print("   Then restart the application to use your plan.")
                    sys.exit(0)
                else:  # Back to menu
                    return None
                
        except ResearchPlanError as e:
            print(f"❌ Failed to create research plan: {e}")
            retry = questionary.confirm("Try again?", default=True).ask()
            if not retry:
                return None


def select_existing_research_plan() -> str | None:
    """
    Interactive selection of existing research plan.
    
    Returns:
        Plan ID if selected, None if cancelled.
    """
    from .research_plan import list_research_plans
    
    existing_plans = list_research_plans()
    
    if not existing_plans:
        print("❌ No existing research plans found.")
        return None
    
    choices = [f"📋 {plan_id}" for plan_id in existing_plans]
    choices.append("🔙 Back to Research Plan Menu")
    
    choice = questionary.select("Select a research plan:", choices=choices).ask()
    
    if not choice or "Back to" in choice:
        return None
    
    plan_id = choice.replace("📋 ", "")
    return plan_id


def process_with_research_plan(plan_id: str) -> None:
    """
    Process videos using a research plan.
    
    Args:
        plan_id: Research plan identifier.
    """
    from .research_plan import load_research_plan, ResearchPlanError
    from .corpus import CorpusManager
    
    try:
        # Load research plan
        research_plan = load_research_plan(plan_id)
        
        print(f"\n🔬 Research Plan: {research_plan.name}")
        print(f"📝 Description: {research_plan.description}")
        
        # Validate and get video list from research plan
        try:
            research_plan.validate()
            videos = research_plan.get_video_list()
            print(f"\n📋 Research plan contains {len(videos)} video(s) to process")
            
            if not videos:
                print("❌ No videos configured in research plan. Please edit the plan configuration.")
                return
                
        except ResearchPlanError as e:
            print(f"❌ Research plan validation error: {e}")
            print("💡 Please edit the plan configuration to add video URLs.")
            return
        
        # Get processing options
        options = get_processing_options()
        
        # Process videos with research plan
        print(f"\n🎬 Processing {len(videos)} video(s) with research plan...")
        
        # Phase 1: Process individual videos
        from .pipeline import process_single_video
        
        video_results = []
        for i, video_url in enumerate(videos, 1):
            print(f"\n--- Processing video {i}/{len(videos)} ---")
            
            result = process_single_video(
                url_or_id=video_url,
                model=options["model"],
                use_cache=options["use_cache"],
                research_plan=research_plan
            )
            
            video_results.append(result)
            
            if result.success:
                print(f"✓ {result.video_id}: {result.chunk_count} chunks → {result.output_path}")
            else:
                print(f"✗ {result.video_id}: {result.error}")
        
        # Show Phase 1 results
        successful_videos = [r for r in video_results if r.success]
        failed_videos = [r for r in video_results if not r.success]
        
        print(f"\n📊 Phase 1 Results (Individual Videos):")
        print(f"   ✅ Successful: {len(successful_videos)}")
        if failed_videos:
            print(f"   ❌ Failed: {len(failed_videos)}")
        
        if not successful_videos:
            print("❌ No videos processed successfully. Cannot proceed to corpus analysis.")
            return
        
        # Phase 2: Corpus operations
        corpus_choice = questionary.select(
            "Proceed with corpus analysis?",
            choices=[
                "🔬 Run Full Corpus Pipeline (Aggregate + Analyze)",
                "📚 Aggregate Only",
                "🔍 Analyze Existing Corpus",
                "🔙 Skip Corpus Analysis"
            ]
        ).ask()
        
        if not corpus_choice or "Skip" in corpus_choice:
            return
        
        corpus_manager = CorpusManager(research_plan)
        successful_video_ids = [r.video_id for r in successful_videos]
        
        if "Full Corpus Pipeline" in corpus_choice:
            result = corpus_manager.full_corpus_pipeline(successful_video_ids, options["model"])
        elif "Aggregate Only" in corpus_choice:
            result = corpus_manager.aggregate_video_summaries(successful_video_ids)
        else:  # Analyze existing
            result = corpus_manager.analyze_corpus(options["model"])
        
        # Show final results
        if result.success:
            print(f"\n🎉 Corpus processing completed!")
            if result.corpus_path:
                print(f"📚 Corpus: {result.corpus_path}")
            if result.summary_path:
                print(f"🔍 Analysis: {result.summary_path}")
            print(f"📊 Videos included: {result.video_count}")
        else:
            print(f"❌ Corpus processing failed: {result.error}")
        
    except ResearchPlanError as e:
        print(f"❌ Research plan error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


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

    source = questionary.select("Choose input source:", choices=choices).ask()

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

            supported_extensions = {".txt", ".list", ".urls", ".csv"}
            compatible_files = []

            try:
                for file_path in directory.iterdir():
                    if (
                        file_path.is_file()
                        and file_path.suffix.lower() in supported_extensions
                    ):
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

        choices.extend(["📁 Browse other directory", "✏️  Enter path manually"])

        if not choices or len(choices) == 2:  # Only browse/manual options
            choices = ["📁 Browse other directory", "✏️  Enter path manually"]

        selection = questionary.select("Select video list file:", choices=choices).ask()

        if not selection:
            sys.exit(0)

        if "Browse other directory" in selection:
            # Let user pick a directory first
            dir_path = questionary.path(
                "Enter directory to browse:", only_directories=True
            ).ask()

            if not dir_path:
                sys.exit(0)

            # Get compatible files in selected directory
            dir_files = get_compatible_files(Path(dir_path))

            if not dir_files:
                print(
                    f"❌ No compatible files (.txt, .list, .urls, .csv) found in {dir_path}"
                )
                sys.exit(1)

            file_selection = questionary.select(
                f"Select file from {dir_path}:",
                choices=[f"📄 {Path(f).name}" for f in dir_files],
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
                supported_extensions = {".txt", ".list", ".urls", ".csv"}
                if path.suffix.lower() not in supported_extensions:
                    return f"Unsupported file type. Use: {', '.join(sorted(supported_extensions))}"

                return True

            file_path = questionary.path(
                "Enter path to video list file (.txt, .list, .urls, .csv):",
                validate=validate_video_list_file,
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
        url = questionary.text("Enter YouTube URL or video ID:").ask()

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
    model = questionary.text("Ollama model to use:", default=config.OLLAMA_MODEL).ask()

    if not model:
        model = config.OLLAMA_MODEL

    # Cache option
    use_cache = questionary.confirm(
        "Use cached transcripts if available?", default=True
    ).ask()

    return {"model": model.strip(), "use_cache": use_cache}


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
            "📝 Create new versions (file_v2.md)",
        ],
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
            "🚪 Quit",
        ],
    ).ask()

    if not choice or "Quit" in choice:
        return False

    elif "Clean transcript cache" in choice:
        confirm = questionary.confirm(
            f"Delete {cache_stats['total_files']} cached transcript files?",
            default=False,
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
            "Startup checks failed. Retry?", default=True
        ).ask()

        if choice:
            return interactive_main()  # Retry
        else:
            sys.exit(1)

    # Main menu loop
    while True:
        try:
            main_choice = get_main_menu_choice()
            
            if "Exit" in main_choice:
                print("👋 Goodbye!")
                sys.exit(0)
            
            elif "Clean Cache" in main_choice:
                cache_stats = get_cache_stats()
                cache_info = f"({cache_stats['total_files']} files, {format_file_size(cache_stats['total_size_bytes'])})"
                
                confirm = questionary.confirm(
                    f"Delete {cache_stats['total_files']} cached transcript files?",
                    default=False,
                ).ask()
                
                if confirm:
                    deleted = clear_cache()
                    print(f"✓ Deleted {deleted} cached files")
                continue
            
            elif "Research Plan" in main_choice:
                # Research plan workflow
                while True:
                    research_choice = get_research_plan_menu_choice()
                    
                    if "Back to Main Menu" in research_choice:
                        break
                    
                    elif "Create New" in research_choice:
                        plan_id = create_research_plan_interactive()
                        if plan_id:
                            process_with_research_plan(plan_id)
                        break
                    
                    elif "Select Existing" in research_choice:
                        plan_id = select_existing_research_plan()
                        if plan_id:
                            process_with_research_plan(plan_id)
                        break
                continue
            
            elif "Process Videos" in main_choice:
                # Traditional video processing workflow
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
                    model=options["model"],
                    use_cache=options["use_cache"],
                    auto_overwrite=auto_overwrite,
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
                "An error occurred. Try again?", default=False
            ).ask()

            if not retry:
                break

    print("\n👋 Thanks for using YouTube Summarizer!")


def legacy_main() -> None:
    """Legacy CLI for backwards compatibility."""
    parser = argparse.ArgumentParser(
        description="YouTube transcript → Ollama summary",
        epilog="For interactive mode, run without arguments",
    )
    parser.add_argument("list_file", nargs="?", help="Text file of YouTube URLs/IDs")
    parser.add_argument("--model", default=config.OLLAMA_MODEL, help="Ollama model tag")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Use interactive mode (default if no list_file provided)",
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

