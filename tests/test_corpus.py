"""
Tests for corpus aggregation and analysis functionality.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from yt_summarizer.corpus import (
    CorpusManager,
    CorpusError,
    CorpusProcessingResult,
    create_corpus_manager,
    aggregate_and_analyze_corpus
)
from yt_summarizer.research_plan import ResearchPlanConfig


@pytest.fixture
def sample_research_plan():
    """Create a sample research plan for testing."""
    return ResearchPlanConfig(
        name="Test Research Plan",
        description="Test description",
        plan_id="test_plan",
        video_urls=["https://www.youtube.com/watch?v=test123"],
        video_list_file=None,
        chunk_prompt="Analyze this content: {chunk}",
        executive_prompt="Summarize these points: {bullet_summaries}",
        corpus_chunk_prompt="Analyze corpus content: {chunk}",
        corpus_executive_prompt="Create corpus analysis: {bullet_summaries}",
        video_summaries_dir="data/videos/",
        corpus_dir="data/corpus/",
        video_filename_pattern="{title}_{video_id}.md",
        corpus_filename="{research_plan_name}.md",
        corpus_summary_filename="{research_plan_name}_summary.md"
    )


@pytest.fixture
def sample_video_summaries():
    """Create sample video summary content."""
    return {
        "video1_abc123.md": """---
title: Video 1
video_id: abc123
---

# Video 1 Summary

## Executive Summary
This is the executive summary for video 1.

## Key Points
- Point 1
- Point 2
""",
        "video2_def456.md": """---
title: Video 2
video_id: def456
---

# Video 2 Summary

## Executive Summary
This is the executive summary for video 2.

## Key Points
- Point A
- Point B
"""
    }


class TestCorpusManager:
    """Test CorpusManager class."""
    
    def test_init_creates_directories(self, sample_research_plan):
        """Test that CorpusManager creates required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Update research plan to use temp directory
            sample_research_plan.video_summaries_dir = f"{temp_dir}/videos/"
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            
            assert Path(f"{temp_dir}/videos/").exists()
            assert Path(f"{temp_dir}/corpus/").exists()
    
    def test_find_video_summaries_empty_directory(self, sample_research_plan):
        """Test finding video summaries in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_research_plan.video_summaries_dir = f"{temp_dir}/videos/"
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            video_files = manager._find_video_summaries()
            
            assert video_files == []
    
    def test_find_video_summaries_with_files(self, sample_research_plan, sample_video_summaries):
        """Test finding video summaries with existing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            videos_dir = Path(temp_dir) / "videos"
            videos_dir.mkdir()
            
            # Create sample video files
            for filename, content in sample_video_summaries.items():
                (videos_dir / filename).write_text(content)
            
            sample_research_plan.video_summaries_dir = str(videos_dir) + "/"
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            video_files = manager._find_video_summaries()
            
            assert len(video_files) == 2
            assert all(f.suffix == ".md" for f in video_files)
    
    def test_find_video_summaries_filtered_by_ids(self, sample_research_plan, sample_video_summaries):
        """Test finding video summaries filtered by video IDs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            videos_dir = Path(temp_dir) / "videos"
            videos_dir.mkdir()
            
            # Create sample video files
            for filename, content in sample_video_summaries.items():
                (videos_dir / filename).write_text(content)
            
            sample_research_plan.video_summaries_dir = str(videos_dir) + "/"
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            video_files = manager._find_video_summaries(["abc123"])
            
            assert len(video_files) == 1
            assert "abc123" in video_files[0].name
    
    def test_combine_video_summaries(self, sample_research_plan, sample_video_summaries):
        """Test combining video summaries into single content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            videos_dir = Path(temp_dir) / "videos"
            videos_dir.mkdir()
            
            # Create sample video files
            video_files = []
            for filename, content in sample_video_summaries.items():
                file_path = videos_dir / filename
                file_path.write_text(content)
                video_files.append(file_path)
            
            sample_research_plan.video_summaries_dir = str(videos_dir) + "/"
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            combined_content = manager._combine_video_summaries(video_files)
            
            assert "## Video Summary: video1_abc123" in combined_content
            assert "## Video Summary: video2_def456" in combined_content
            assert "This is the executive summary for video 1" in combined_content
            assert "This is the executive summary for video 2" in combined_content
    
    def test_aggregate_video_summaries_no_files(self, sample_research_plan):
        """Test aggregating when no video files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_research_plan.video_summaries_dir = f"{temp_dir}/videos/"
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            result = manager.aggregate_video_summaries()
            
            assert not result.success
            assert "No video summary files found" in result.error
    
    def test_aggregate_video_summaries_success(self, sample_research_plan, sample_video_summaries):
        """Test successful video summary aggregation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            videos_dir = Path(temp_dir) / "videos"
            videos_dir.mkdir()
            corpus_dir = Path(temp_dir) / "corpus"
            corpus_dir.mkdir()
            
            # Create sample video files
            for filename, content in sample_video_summaries.items():
                (videos_dir / filename).write_text(content)
            
            sample_research_plan.video_summaries_dir = str(videos_dir) + "/"
            sample_research_plan.corpus_dir = str(corpus_dir) + "/"
            
            manager = CorpusManager(sample_research_plan)
            result = manager.aggregate_video_summaries()
            
            assert result.success
            assert result.video_count == 2
            assert result.corpus_path.exists()
            
            # Check corpus file content
            corpus_content = result.corpus_path.read_text()
            assert "research_plan: Test Research Plan" in corpus_content
            assert "video_count: 2" in corpus_content
    
    @patch('yt_summarizer.corpus.CorpusManager._analyze_corpus_chunk')
    @patch('yt_summarizer.corpus.CorpusManager._generate_corpus_executive_summary')
    def test_analyze_corpus_success(self, mock_exec_summary, mock_chunk_analysis, 
                                   sample_research_plan):
        """Test successful corpus analysis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus_dir = Path(temp_dir) / "corpus"
            corpus_dir.mkdir()
            
            # Create a corpus file
            corpus_file = corpus_dir / "test_plan.md"
            corpus_content = """---
research_plan: Test Research Plan
---

# Research Corpus

This is test corpus content for analysis.
"""
            corpus_file.write_text(corpus_content)
            
            sample_research_plan.corpus_dir = str(corpus_dir) + "/"
            
            # Mock LLM responses
            mock_chunk_analysis.return_value = "Analysis of chunk content"
            mock_exec_summary.return_value = "Executive analysis summary"
            
            manager = CorpusManager(sample_research_plan)
            result = manager.analyze_corpus("test_model")
            
            assert result.success
            assert result.summary_path.exists()
            
            # Check summary file content
            summary_content = result.summary_path.read_text()
            assert "Executive analysis summary" in summary_content
    
    def test_analyze_corpus_no_corpus_file(self, sample_research_plan):
        """Test corpus analysis when corpus file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_research_plan.corpus_dir = f"{temp_dir}/corpus/"
            
            manager = CorpusManager(sample_research_plan)
            result = manager.analyze_corpus("test_model")
            
            assert not result.success
            assert "Corpus file not found" in result.error
    
    @patch('yt_summarizer.corpus.CorpusManager.aggregate_video_summaries')
    @patch('yt_summarizer.corpus.CorpusManager.analyze_corpus')
    def test_full_corpus_pipeline(self, mock_analyze, mock_aggregate, sample_research_plan):
        """Test full corpus pipeline."""
        # Mock successful aggregation
        mock_aggregate.return_value = CorpusProcessingResult(
            success=True,
            corpus_path=Path("/test/corpus.md"),
            video_count=2
        )
        
        # Mock successful analysis
        mock_analyze.return_value = CorpusProcessingResult(
            success=True,
            summary_path=Path("/test/summary.md"),
            video_count=2
        )
        
        manager = CorpusManager(sample_research_plan)
        result = manager.full_corpus_pipeline(["video1", "video2"], "test_model")
        
        assert result.success
        assert result.video_count == 2
        mock_aggregate.assert_called_once_with(["video1", "video2"])
        mock_analyze.assert_called_once_with("test_model")
    
    @patch('yt_summarizer.corpus.CorpusManager.aggregate_video_summaries')
    def test_full_corpus_pipeline_aggregation_fails(self, mock_aggregate, sample_research_plan):
        """Test full corpus pipeline when aggregation fails."""
        # Mock failed aggregation
        mock_aggregate.return_value = CorpusProcessingResult(
            success=False,
            error="Aggregation failed"
        )
        
        manager = CorpusManager(sample_research_plan)
        result = manager.full_corpus_pipeline(["video1", "video2"], "test_model")
        
        assert not result.success
        assert result.error == "Aggregation failed"
    
    def test_count_videos_in_corpus(self, sample_research_plan):
        """Test counting videos in corpus file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus_dir = Path(temp_dir) / "corpus"
            corpus_dir.mkdir()
            
            corpus_file = corpus_dir / "test_corpus.md"
            corpus_content = """
# Research Corpus

## Video Summary: video1
Content for video 1

## Video Summary: video2
Content for video 2

## Video Summary: video3
Content for video 3
"""
            corpus_file.write_text(corpus_content)
            
            sample_research_plan.corpus_dir = str(corpus_dir) + "/"
            
            manager = CorpusManager(sample_research_plan)
            count = manager._count_videos_in_corpus(corpus_file)
            
            assert count == 3


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_corpus_manager(self, sample_research_plan):
        """Test create_corpus_manager convenience function."""
        manager = create_corpus_manager(sample_research_plan)
        
        assert isinstance(manager, CorpusManager)
        assert manager.research_plan == sample_research_plan
    
    @patch('yt_summarizer.corpus.CorpusManager')
    def test_aggregate_and_analyze_corpus(self, mock_manager_class, sample_research_plan):
        """Test aggregate_and_analyze_corpus convenience function."""
        mock_manager = mock_manager_class.return_value
        mock_result = CorpusProcessingResult(success=True, video_count=2)
        mock_manager.full_corpus_pipeline.return_value = mock_result
        
        result = aggregate_and_analyze_corpus(
            sample_research_plan, 
            ["video1", "video2"], 
            "test_model"
        )
        
        assert result == mock_result
        mock_manager.full_corpus_pipeline.assert_called_once_with(
            ["video1", "video2"], "test_model"
        )