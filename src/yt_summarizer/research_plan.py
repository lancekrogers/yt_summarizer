"""
Research plan configuration and management system.

Provides functionality for creating, loading, and managing research plans
that define focused content extraction strategies for YouTube video analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from yaml import YAMLError

from .config import config
from .io_utils import validate_file_path, sanitize_filename

logger = logging.getLogger(__name__)


class ResearchPlanError(Exception):
    """Base exception for research plan operations."""
    pass


class ResearchPlanNotFoundError(ResearchPlanError):
    """Raised when a research plan file cannot be found."""
    pass


class ResearchPlanValidationError(ResearchPlanError):
    """Raised when a research plan configuration is invalid."""
    pass


@dataclass
class ResearchPlanConfig:
    """Configuration for a research plan."""
    
    # Plan metadata
    name: str
    description: str
    plan_id: str
    
    # Video configuration
    video_urls: List[str]
    video_list_file: Optional[str]
    
    # Prompt configuration
    chunk_prompt: str
    executive_prompt: str
    corpus_chunk_prompt: str
    corpus_executive_prompt: str
    
    # Output configuration
    video_summaries_dir: str
    corpus_dir: str
    video_filename_pattern: str
    corpus_filename: str
    corpus_summary_filename: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], plan_id: str) -> ResearchPlanConfig:
        """Create a ResearchPlanConfig from a dictionary.
        
        Args:
            data: Dictionary containing plan configuration.
            plan_id: Unique identifier for the plan.
            
        Returns:
            ResearchPlanConfig instance.
            
        Raises:
            ResearchPlanValidationError: If configuration is invalid.
        """
        try:
            research_plan = data.get("research_plan", {})
            videos = data.get("videos", {})
            prompts = data.get("prompts", {})
            output = data.get("output", {})
            
            return cls(
                # Metadata
                name=research_plan.get("name", ""),
                description=research_plan.get("description", ""),
                plan_id=plan_id,
                
                # Video configuration
                video_urls=videos.get("urls", []),
                video_list_file=videos.get("list_file"),
                
                # Prompts
                chunk_prompt=prompts.get("chunk_prompt", ""),
                executive_prompt=prompts.get("executive_prompt", ""),
                corpus_chunk_prompt=prompts.get("corpus_chunk_prompt", ""),
                corpus_executive_prompt=prompts.get("corpus_executive_prompt", ""),
                
                # Output configuration
                video_summaries_dir=output.get("video_summaries_dir", "data/videos/"),
                corpus_dir=output.get("corpus_dir", "data/corpus/"),
                video_filename_pattern=output.get("video_filename_pattern", "{title}_{video_id}.md"),
                corpus_filename=output.get("corpus_filename", "{research_plan_name}.md"),
                corpus_summary_filename=output.get("corpus_summary_filename", "{research_plan_name}_summary.md")
            )
            
        except (KeyError, TypeError) as e:
            raise ResearchPlanValidationError(f"Invalid research plan configuration: {e}")
    
    def validate(self) -> None:
        """Validate the research plan configuration.
        
        Raises:
            ResearchPlanValidationError: If configuration is invalid.
        """
        if not self.name.strip():
            raise ResearchPlanValidationError("Research plan name cannot be empty")
        
        if not self.plan_id.strip():
            raise ResearchPlanValidationError("Research plan ID cannot be empty")
        
        # Validate video configuration - must have either URLs or file
        if not self.video_urls and not self.video_list_file:
            raise ResearchPlanValidationError("Must specify either video URLs or video list file")
        
        # Validate required prompts
        required_prompts = [
            ("chunk_prompt", self.chunk_prompt),
            ("executive_prompt", self.executive_prompt),
            ("corpus_chunk_prompt", self.corpus_chunk_prompt),
            ("corpus_executive_prompt", self.corpus_executive_prompt)
        ]
        
        for prompt_name, prompt_value in required_prompts:
            if not prompt_value.strip():
                raise ResearchPlanValidationError(f"{prompt_name} cannot be empty")
            
            # Check for required placeholders
            if prompt_name in ["chunk_prompt", "corpus_chunk_prompt"] and "{chunk}" not in prompt_value:
                raise ResearchPlanValidationError(f"{prompt_name} must contain {{chunk}} placeholder")
            
            if prompt_name in ["executive_prompt", "corpus_executive_prompt"] and "{bullet_summaries}" not in prompt_value:
                raise ResearchPlanValidationError(f"{prompt_name} must contain {{bullet_summaries}} placeholder")
    
    def get_video_output_dir(self) -> Path:
        """Get the resolved video summaries output directory."""
        return Path(self.video_summaries_dir)
    
    def get_corpus_output_dir(self) -> Path:
        """Get the resolved corpus output directory."""
        return Path(self.corpus_dir)
    
    def get_corpus_filename(self) -> str:
        """Get the resolved corpus filename."""
        return self.corpus_filename.format(research_plan_name=self.plan_id)
    
    def get_corpus_summary_filename(self) -> str:
        """Get the resolved corpus summary filename."""
        return self.corpus_summary_filename.format(research_plan_name=self.plan_id)
    
    def get_video_filename(self, title: str, video_id: str) -> str:
        """Get the resolved video filename.
        
        Args:
            title: Video title.
            video_id: Video ID.
            
        Returns:
            Resolved filename.
        """
        from .utils import slugify  # Avoid circular import
        safe_title = slugify(title)
        return self.video_filename_pattern.format(title=safe_title, video_id=video_id)
    
    def get_video_list(self) -> List[str]:
        """Get the list of videos to process.
        
        Returns:
            List of video URLs/IDs from the research plan.
            
        Raises:
            ResearchPlanError: If video list file is specified but cannot be read.
        """
        videos = []
        
        # Add direct URLs if specified (filter out comments)
        if self.video_urls:
            for url in self.video_urls:
                if url and not url.strip().startswith('#'):
                    videos.append(url)
        
        # Add URLs from file if specified
        if self.video_list_file and self.video_list_file.strip():
            try:
                from .utils import read_video_list  # Avoid circular import
                from pathlib import Path
                
                file_path = Path(self.video_list_file)
                
                if not file_path.is_absolute():
                    # Try multiple locations for relative paths
                    search_paths = [
                        # 1. Relative to current working directory
                        Path.cwd() / self.video_list_file,
                        # 2. Relative to project root (look for common project indicators)
                        self._find_project_root() / self.video_list_file,
                        # 3. In the research_plans directory
                        Path("research_plans").parent / self.video_list_file,
                    ]
                    
                    file_path = None
                    for search_path in search_paths:
                        if search_path.exists():
                            file_path = search_path
                            break
                    
                    if file_path is None:
                        # Create helpful error message with search locations
                        search_locations = "\n".join([f"  - {p}" for p in search_paths])
                        raise FileNotFoundError(
                            f"Video list file '{self.video_list_file}' not found in any of these locations:\n{search_locations}"
                        )
                else:
                    file_path = Path(self.video_list_file)
                
                file_videos = read_video_list(file_path)
                videos.extend(file_videos)
                
            except Exception as e:
                raise ResearchPlanError(f"Failed to read video list file '{self.video_list_file}': {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_videos = []
        for video in videos:
            if video not in seen:
                seen.add(video)
                unique_videos.append(video)
        
        return unique_videos
    
    def _find_project_root(self) -> Path:
        """Find the project root directory by looking for common indicators."""
        current = Path.cwd()
        
        # Look for common project files/directories
        project_indicators = [
            "pyproject.toml",
            "poetry.lock", 
            "requirements.txt",
            "setup.py",
            ".git",
            "research_plans",
            "src"
        ]
        
        # Walk up the directory tree
        for parent in [current] + list(current.parents):
            for indicator in project_indicators:
                if (parent / indicator).exists():
                    return parent
        
        # If no project root found, return current directory
        return current


class ResearchPlanManager:
    """Manager for research plan operations."""
    
    def __init__(self, plans_dir: Optional[Union[str, Path]] = None):
        """Initialize the research plan manager.
        
        Args:
            plans_dir: Directory containing research plans. Defaults to research_plans.
        """
        self.plans_dir = Path(plans_dir) if plans_dir else Path("research_plans")
        self.plans_dir.mkdir(parents=True, exist_ok=True)
    
    def list_plans(self) -> List[str]:
        """List available research plan IDs.
        
        Returns:
            List of plan IDs (filenames without .yaml extension).
        """
        if not self.plans_dir.exists():
            return []
        
        plan_files = list(self.plans_dir.glob("*.yaml"))
        return sorted([f.stem for f in plan_files])
    
    def plan_exists(self, plan_id: str) -> bool:
        """Check if a research plan exists.
        
        Args:
            plan_id: Plan identifier.
            
        Returns:
            True if plan exists, False otherwise.
        """
        plan_path = self._get_plan_path(plan_id)
        return plan_path.exists()
    
    def load_plan(self, plan_id: str) -> ResearchPlanConfig:
        """Load a research plan configuration.
        
        Args:
            plan_id: Plan identifier.
            
        Returns:
            ResearchPlanConfig instance.
            
        Raises:
            ResearchPlanNotFoundError: If plan file doesn't exist.
            ResearchPlanValidationError: If plan configuration is invalid.
        """
        plan_path = self._get_plan_path(plan_id)
        
        if not plan_path.exists():
            raise ResearchPlanNotFoundError(f"Research plan '{plan_id}' not found at {plan_path}")
        
        try:
            with open(plan_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                raise ResearchPlanValidationError("Research plan file must contain a YAML dictionary")
            
            plan_config = ResearchPlanConfig.from_dict(data, plan_id)
            
            logger.info(f"Loaded research plan: {plan_id}")
            return plan_config
            
        except YAMLError as e:
            raise ResearchPlanValidationError(f"Invalid YAML in research plan '{plan_id}': {e}")
        except OSError as e:
            raise ResearchPlanError(f"Failed to read research plan file: {e}")
    
    def create_plan_from_template(self, plan_id: str, name: str, description: str = "") -> Path:
        """Create a new research plan from template.
        
        Args:
            plan_id: Unique plan identifier.
            name: Human-readable plan name.
            description: Plan description.
            
        Returns:
            Path to created plan file.
            
        Raises:
            ResearchPlanError: If plan creation fails.
        """
        # Sanitize plan_id for filesystem
        safe_plan_id = sanitize_filename(plan_id)
        plan_path = self._get_plan_path(safe_plan_id)
        
        if plan_path.exists():
            raise ResearchPlanError(f"Research plan '{safe_plan_id}' already exists")
        
        template_data = self._get_template_data(name, description)
        
        try:
            with open(plan_path, 'w', encoding='utf-8') as f:
                yaml.dump(template_data, f, default_flow_style=False, indent=2, allow_unicode=True)
            
            logger.info(f"Created research plan: {safe_plan_id} at {plan_path}")
            return plan_path
            
        except OSError as e:
            raise ResearchPlanError(f"Failed to create research plan file: {e}")
    
    def delete_plan(self, plan_id: str) -> None:
        """Delete a research plan.
        
        Args:
            plan_id: Plan identifier.
            
        Raises:
            ResearchPlanNotFoundError: If plan doesn't exist.
            ResearchPlanError: If deletion fails.
        """
        plan_path = self._get_plan_path(plan_id)
        
        if not plan_path.exists():
            raise ResearchPlanNotFoundError(f"Research plan '{plan_id}' not found")
        
        try:
            plan_path.unlink()
            logger.info(f"Deleted research plan: {plan_id}")
        except OSError as e:
            raise ResearchPlanError(f"Failed to delete research plan: {e}")
    
    def _get_plan_path(self, plan_id: str) -> Path:
        """Get the file path for a plan ID."""
        return self.plans_dir / f"{plan_id}.yaml"
    
    def _get_template_data(self, name: str, description: str) -> Dict[str, Any]:
        """Get template data for a new research plan."""
        return {
            "research_plan": {
                "name": name,
                "description": description or "Research plan for focused content extraction"
            },
            "videos": {
                "urls": [],  # Add your video URLs here
                "list_file": None  # Optional: path to a text file containing video URLs
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


# Convenience functions for common operations
def load_research_plan(plan_id: str) -> ResearchPlanConfig:
    """Load a research plan configuration.
    
    Args:
        plan_id: Plan identifier.
        
    Returns:
        ResearchPlanConfig instance.
    """
    manager = ResearchPlanManager()
    return manager.load_plan(plan_id)


def create_research_plan(plan_id: str, name: str, description: str = "") -> Path:
    """Create a new research plan from template.
    
    Args:
        plan_id: Unique plan identifier.
        name: Human-readable plan name.
        description: Plan description.
        
    Returns:
        Path to created plan file.
    """
    manager = ResearchPlanManager()
    return manager.create_plan_from_template(plan_id, name, description)


def list_research_plans() -> List[str]:
    """List available research plan IDs.
    
    Returns:
        List of plan IDs.
    """
    manager = ResearchPlanManager()
    return manager.list_plans()