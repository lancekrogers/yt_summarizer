"""
Tests for research plan configuration and management.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from yt_summarizer.research_plan import (
    ResearchPlanConfig,
    ResearchPlanManager,
    ResearchPlanError,
    ResearchPlanNotFoundError,
    ResearchPlanValidationError,
    load_research_plan,
    create_research_plan,
    list_research_plans
)


class TestResearchPlanConfig:
    """Test ResearchPlanConfig class."""
    
    def test_from_dict_valid_config(self):
        """Test creating ResearchPlanConfig from valid dictionary."""
        data = {
            "research_plan": {
                "name": "Test Plan",
                "description": "Test description"
            },
            "videos": {
                "urls": ["https://www.youtube.com/watch?v=test123"],
                "list_file": None
            },
            "prompts": {
                "chunk_prompt": "Test chunk prompt with {chunk}",
                "executive_prompt": "Test executive prompt with {bullet_summaries}",
                "corpus_chunk_prompt": "Test corpus chunk prompt with {chunk}",
                "corpus_executive_prompt": "Test corpus executive prompt with {bullet_summaries}"
            },
            "output": {
                "video_summaries_dir": "data/videos/",
                "corpus_dir": "data/corpus/",
                "video_filename_pattern": "{title}_{video_id}.md",
                "corpus_filename": "{research_plan_name}.md",
                "corpus_summary_filename": "{research_plan_name}_summary.md"
            }
        }
        
        config = ResearchPlanConfig.from_dict(data, "test_plan")
        
        assert config.name == "Test Plan"
        assert config.description == "Test description"
        assert config.plan_id == "test_plan"
        assert config.video_urls == ["https://www.youtube.com/watch?v=test123"]
        assert config.video_list_file is None
        assert "{chunk}" in config.chunk_prompt
        assert "{bullet_summaries}" in config.executive_prompt
    
    def test_from_dict_missing_sections(self):
        """Test handling of missing configuration sections."""
        data = {}
        
        config = ResearchPlanConfig.from_dict(data, "test_plan")
        
        # Should use empty defaults
        assert config.name == ""
        assert config.description == ""
        assert config.video_urls == []
        assert config.video_list_file is None
        assert config.chunk_prompt == ""
    
    def test_validate_success(self):
        """Test successful validation."""
        config = ResearchPlanConfig(
            name="Test Plan",
            description="Test description",
            plan_id="test_plan",
            video_urls=["https://www.youtube.com/watch?v=test123"],
            video_list_file=None,
            chunk_prompt="Test chunk prompt with {chunk}",
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        
        # Should not raise
        config.validate()
    
    def test_validate_empty_name(self):
        """Test validation failure for empty name."""
        config = ResearchPlanConfig(
            name="",
            description="Test description",
            plan_id="test_plan",
            video_urls=["https://www.youtube.com/watch?v=test123"],
            video_list_file=None,
            chunk_prompt="Test chunk prompt with {chunk}",
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        
        with pytest.raises(ResearchPlanValidationError, match="name cannot be empty"):
            config.validate()
    
    def test_validate_missing_placeholder(self):
        """Test validation failure for missing prompt placeholders."""
        config = ResearchPlanConfig(
            name="Test Plan",
            description="Test description",
            plan_id="test_plan",
            video_urls=["https://www.youtube.com/watch?v=test123"],
            video_list_file=None,
            chunk_prompt="Test chunk prompt without placeholder",  # Missing {chunk}
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        
        with pytest.raises(ResearchPlanValidationError, match="must contain {chunk} placeholder"):
            config.validate()
    
    def test_get_video_filename(self):
        """Test video filename generation."""
        config = ResearchPlanConfig(
            name="Test Plan",
            description="Test description",
            plan_id="test_plan",
            video_urls=["https://www.youtube.com/watch?v=test123"],
            video_list_file=None,
            chunk_prompt="Test chunk prompt with {chunk}",
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        
        filename = config.get_video_filename("Test Video Title", "abc123")
        assert "abc123" in filename
        assert filename.endswith(".md")
    
    def test_validate_no_videos(self):
        """Test validation failure when no videos are configured."""
        config = ResearchPlanConfig(
            name="Test Plan",
            description="Test description",
            plan_id="test_plan",
            video_urls=[],  # Empty
            video_list_file=None,  # None
            chunk_prompt="Test chunk prompt with {chunk}",
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        
        with pytest.raises(ResearchPlanValidationError, match="Must specify either video URLs or video list file"):
            config.validate()
    
    def test_get_video_list_from_urls(self):
        """Test getting video list from direct URLs."""
        config = ResearchPlanConfig(
            name="Test Plan",
            description="Test description",
            plan_id="test_plan",
            video_urls=["https://www.youtube.com/watch?v=abc123", "https://www.youtube.com/watch?v=def456"],
            video_list_file=None,
            chunk_prompt="Test chunk prompt with {chunk}",
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        
        videos = config.get_video_list()
        assert len(videos) == 2
        assert "abc123" in videos[0]
        assert "def456" in videos[1]


class TestResearchPlanManager:
    """Test ResearchPlanManager class."""
    
    def test_init_creates_directory(self):
        """Test that manager creates plans directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            manager = ResearchPlanManager(plans_dir)
            
            assert plans_dir.exists()
            assert plans_dir.is_dir()
    
    def test_list_plans_empty(self):
        """Test listing plans when directory is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            manager = ResearchPlanManager(plans_dir)
            
            plans = manager.list_plans()
            assert plans == []
    
    def test_list_plans_with_files(self):
        """Test listing plans with existing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            plans_dir.mkdir()
            
            # Create test plan files
            (plans_dir / "plan1.yaml").touch()
            (plans_dir / "plan2.yaml").touch()
            (plans_dir / "not_yaml.txt").touch()  # Should be ignored
            
            manager = ResearchPlanManager(plans_dir)
            plans = manager.list_plans()
            
            assert sorted(plans) == ["plan1", "plan2"]
    
    def test_plan_exists(self):
        """Test checking plan existence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            plans_dir.mkdir()
            (plans_dir / "existing_plan.yaml").touch()
            
            manager = ResearchPlanManager(plans_dir)
            
            assert manager.plan_exists("existing_plan")
            assert not manager.plan_exists("nonexistent_plan")
    
    def test_load_plan_success(self):
        """Test successful plan loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            plans_dir.mkdir()
            
            plan_data = {
                "research_plan": {
                    "name": "Test Plan",
                    "description": "Test description"
                },
                "videos": {
                    "urls": ["https://www.youtube.com/watch?v=test123"],
                    "list_file": None
                },
                "prompts": {
                    "chunk_prompt": "Test chunk prompt with {chunk}",
                    "executive_prompt": "Test executive prompt with {bullet_summaries}",
                    "corpus_chunk_prompt": "Test corpus chunk prompt with {chunk}",
                    "corpus_executive_prompt": "Test corpus executive prompt with {bullet_summaries}"
                },
                "output": {
                    "video_summaries_dir": "data/videos/",
                    "corpus_dir": "data/corpus/",
                    "video_filename_pattern": "{title}_{video_id}.md",
                    "corpus_filename": "{research_plan_name}.md",
                    "corpus_summary_filename": "{research_plan_name}_summary.md"
                }
            }
            
            plan_file = plans_dir / "test_plan.yaml"
            with open(plan_file, 'w') as f:
                yaml.dump(plan_data, f)
            
            manager = ResearchPlanManager(plans_dir)
            config = manager.load_plan("test_plan")
            
            assert config.name == "Test Plan"
            assert config.plan_id == "test_plan"
    
    def test_load_plan_not_found(self):
        """Test loading nonexistent plan."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            manager = ResearchPlanManager(plans_dir)
            
            with pytest.raises(ResearchPlanNotFoundError):
                manager.load_plan("nonexistent_plan")
    
    def test_load_plan_invalid_yaml(self):
        """Test loading plan with invalid YAML."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            plans_dir.mkdir()
            
            plan_file = plans_dir / "invalid_plan.yaml"
            with open(plan_file, 'w') as f:
                f.write("invalid: yaml: content: [")
            
            manager = ResearchPlanManager(plans_dir)
            
            with pytest.raises(ResearchPlanValidationError, match="Invalid YAML"):
                manager.load_plan("invalid_plan")
    
    def test_create_plan_from_template(self):
        """Test creating plan from template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            manager = ResearchPlanManager(plans_dir)
            
            plan_path = manager.create_plan_from_template("test_plan", "Test Plan", "Test description")
            
            assert plan_path.exists()
            assert plan_path.name == "test_plan.yaml"
            
            # Verify content
            with open(plan_path, 'r') as f:
                data = yaml.safe_load(f)
            
            assert data["research_plan"]["name"] == "Test Plan"
            assert data["research_plan"]["description"] == "Test description"
    
    def test_create_plan_already_exists(self):
        """Test creating plan when it already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            plans_dir.mkdir()
            (plans_dir / "existing_plan.yaml").touch()
            
            manager = ResearchPlanManager(plans_dir)
            
            with pytest.raises(ResearchPlanError, match="already exists"):
                manager.create_plan_from_template("existing_plan", "Test Plan")
    
    def test_delete_plan_success(self):
        """Test successful plan deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            plans_dir.mkdir()
            plan_file = plans_dir / "test_plan.yaml"
            plan_file.touch()
            
            manager = ResearchPlanManager(plans_dir)
            manager.delete_plan("test_plan")
            
            assert not plan_file.exists()
    
    def test_delete_plan_not_found(self):
        """Test deleting nonexistent plan."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "test_plans"
            manager = ResearchPlanManager(plans_dir)
            
            with pytest.raises(ResearchPlanNotFoundError):
                manager.delete_plan("nonexistent_plan")


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @patch('yt_summarizer.research_plan.ResearchPlanManager')
    def test_load_research_plan(self, mock_manager_class):
        """Test load_research_plan convenience function."""
        mock_manager = mock_manager_class.return_value
        mock_config = ResearchPlanConfig(
            name="Test Plan",
            description="Test description",
            plan_id="test_plan",
            video_urls=["https://www.youtube.com/watch?v=test123"],
            video_list_file=None,
            chunk_prompt="Test chunk prompt with {chunk}",
            executive_prompt="Test executive prompt with {bullet_summaries}",
            corpus_chunk_prompt="Test corpus chunk prompt with {chunk}",
            corpus_executive_prompt="Test corpus executive prompt with {bullet_summaries}",
            video_summaries_dir="data/videos/",
            corpus_dir="data/corpus/",
            video_filename_pattern="{title}_{video_id}.md",
            corpus_filename="{research_plan_name}.md",
            corpus_summary_filename="{research_plan_name}_summary.md"
        )
        mock_manager.load_plan.return_value = mock_config
        
        result = load_research_plan("test_plan")
        
        assert result == mock_config
        mock_manager.load_plan.assert_called_once_with("test_plan")
    
    @patch('yt_summarizer.research_plan.ResearchPlanManager')
    def test_create_research_plan(self, mock_manager_class):
        """Test create_research_plan convenience function."""
        mock_manager = mock_manager_class.return_value
        mock_path = Path("/test/path/test_plan.yaml")
        mock_manager.create_plan_from_template.return_value = mock_path
        
        result = create_research_plan("test_plan", "Test Plan", "Test description")
        
        assert result == mock_path
        mock_manager.create_plan_from_template.assert_called_once_with(
            "test_plan", "Test Plan", "Test description"
        )
    
    @patch('yt_summarizer.research_plan.ResearchPlanManager')
    def test_list_research_plans(self, mock_manager_class):
        """Test list_research_plans convenience function."""
        mock_manager = mock_manager_class.return_value
        mock_plans = ["plan1", "plan2"]
        mock_manager.list_plans.return_value = mock_plans
        
        result = list_research_plans()
        
        assert result == mock_plans
        mock_manager.list_plans.assert_called_once()