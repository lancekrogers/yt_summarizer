"""
Corpus aggregation and analysis system for research plans.

Provides functionality for combining individual video summaries into research
corpora and performing higher-level analysis across multiple videos.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple, Optional

from yaspin import yaspin

from .config import config
from .llm import LLMError, summarise_chunk, summarise_transcript
from .research_plan import ResearchPlanConfig
from .transcript import chunk_text
from .utils import save_markdown

logger = logging.getLogger(__name__)


class CorpusError(Exception):
    """Base exception for corpus operations."""
    pass


class CorpusProcessingResult(NamedTuple):
    """Result of corpus processing operations."""
    success: bool
    corpus_path: Optional[Path] = None
    summary_path: Optional[Path] = None
    video_count: int = 0
    error: Optional[str] = None


class CorpusManager:
    """Manager for corpus aggregation and analysis operations."""
    
    def __init__(self, research_plan: ResearchPlanConfig):
        """Initialize corpus manager with research plan configuration.
        
        Args:
            research_plan: Research plan configuration.
        """
        self.research_plan = research_plan
        self.video_dir = research_plan.get_video_output_dir()
        self.corpus_dir = research_plan.get_corpus_output_dir()
        
        # Ensure output directories exist
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
    
    def aggregate_video_summaries(self, video_ids: Optional[List[str]] = None) -> CorpusProcessingResult:
        """Aggregate video summaries into a corpus document.
        
        Args:
            video_ids: Optional list of specific video IDs to include.
                      If None, includes all video summaries in the directory.
                      
        Returns:
            CorpusProcessingResult with aggregation outcome.
        """
        try:
            # Find video summary files
            video_files = self._find_video_summaries(video_ids)
            
            if not video_files:
                return CorpusProcessingResult(
                    success=False,
                    error="No video summary files found for aggregation"
                )
            
            logger.info(f"Aggregating {len(video_files)} video summaries into corpus")
            
            # Read and combine summaries
            with yaspin(text=f"Reading {len(video_files)} video summaries...", color="cyan") as spinner:
                combined_content = self._combine_video_summaries(video_files)
                spinner.ok("✓")
            
            # Generate corpus file
            corpus_filename = self.research_plan.get_corpus_filename()
            corpus_path = self.corpus_dir / corpus_filename
            
            with yaspin(text="Creating corpus document...", color="yellow") as spinner:
                self._write_corpus_document(corpus_path, combined_content, video_files)
                spinner.ok("✓")
            
            logger.info(f"✓ Corpus created: {corpus_path}")
            
            return CorpusProcessingResult(
                success=True,
                corpus_path=corpus_path,
                video_count=len(video_files)
            )
            
        except Exception as e:
            error_msg = f"Failed to aggregate video summaries: {e}"
            logger.error(error_msg, exc_info=True)
            return CorpusProcessingResult(success=False, error=error_msg)
    
    def analyze_corpus(self, model: Optional[str] = None) -> CorpusProcessingResult:
        """Analyze the research corpus and generate insights.
        
        Args:
            model: LLM model to use for analysis. Defaults to config.OLLAMA_MODEL.
            
        Returns:
            CorpusProcessingResult with analysis outcome.
        """
        if model is None:
            model = config.OLLAMA_MODEL
        
        try:
            # Check if corpus exists
            corpus_filename = self.research_plan.get_corpus_filename()
            corpus_path = self.corpus_dir / corpus_filename
            
            if not corpus_path.exists():
                return CorpusProcessingResult(
                    success=False,
                    error=f"Corpus file not found: {corpus_path}. Run aggregation first."
                )
            
            # Read corpus content
            with yaspin(text="Reading corpus content...", color="cyan") as spinner:
                corpus_text = self._read_corpus_content(corpus_path)
                spinner.ok("✓")
            
            # Chunk the corpus if necessary
            chunks = chunk_text(corpus_text)
            logger.info(f"Split corpus into {len(chunks)} chunks for analysis")
            
            # Analyze each chunk using corpus-specific prompts
            chunk_analyses = []
            with yaspin(text=f"Analyzing {len(chunks)} corpus chunks...", color="yellow") as spinner:
                for i, chunk in enumerate(chunks, 1):
                    spinner.text = f"Analyzing chunk {i}/{len(chunks)}..."
                    analysis = self._analyze_corpus_chunk(chunk, model)
                    chunk_analyses.append(analysis)
                spinner.ok("✓")
            
            # Generate executive analysis
            with yaspin(text="Generating comprehensive corpus analysis...", color="green") as spinner:
                executive_analysis = self._generate_corpus_executive_summary(chunk_analyses, model)
                spinner.ok("✓")
            
            # Save analysis document
            summary_filename = self.research_plan.get_corpus_summary_filename()
            summary_path = self.corpus_dir / summary_filename
            
            self._write_corpus_analysis(summary_path, executive_analysis, chunk_analyses, model)
            
            logger.info(f"✓ Corpus analysis completed: {summary_path}")
            
            return CorpusProcessingResult(
                success=True,
                corpus_path=corpus_path,
                summary_path=summary_path,
                video_count=self._count_videos_in_corpus(corpus_path)
            )
            
        except LLMError as e:
            error_msg = f"LLM analysis failed: {e}"
            logger.error(error_msg)
            return CorpusProcessingResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Failed to analyze corpus: {e}"
            logger.error(error_msg, exc_info=True)
            return CorpusProcessingResult(success=False, error=error_msg)
    
    def full_corpus_pipeline(self, video_ids: Optional[List[str]] = None, model: Optional[str] = None) -> CorpusProcessingResult:
        """Run the complete corpus pipeline: aggregate then analyze.
        
        Args:
            video_ids: Optional list of specific video IDs to include.
            model: LLM model to use for analysis.
            
        Returns:
            CorpusProcessingResult with final outcome.
        """
        # Step 1: Aggregate video summaries
        aggregation_result = self.aggregate_video_summaries(video_ids)
        if not aggregation_result.success:
            return aggregation_result
        
        # Step 2: Analyze the corpus
        analysis_result = self.analyze_corpus(model)
        if not analysis_result.success:
            return analysis_result
        
        # Return combined result
        return CorpusProcessingResult(
            success=True,
            corpus_path=aggregation_result.corpus_path,
            summary_path=analysis_result.summary_path,
            video_count=aggregation_result.video_count
        )
    
    def _find_video_summaries(self, video_ids: Optional[List[str]] = None) -> List[Path]:
        """Find video summary files for aggregation."""
        if not self.video_dir.exists():
            return []
        
        all_files = list(self.video_dir.glob("*.md"))
        
        if video_ids is None:
            return sorted(all_files)
        
        # Filter by specific video IDs
        filtered_files = []
        for video_id in video_ids:
            # Look for files containing the video ID
            matching_files = [f for f in all_files if video_id in f.name]
            filtered_files.extend(matching_files)
        
        return sorted(list(set(filtered_files)))  # Remove duplicates and sort
    
    def _combine_video_summaries(self, video_files: List[Path]) -> str:
        """Combine multiple video summary files into a single text."""
        combined_sections = []
        
        for video_file in video_files:
            try:
                with open(video_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract the main content (skip YAML frontmatter if present)
                content_lines = content.split('\n')
                if content_lines and content_lines[0].strip() == '---':
                    # Skip YAML frontmatter
                    end_marker = -1
                    for i, line in enumerate(content_lines[1:], 1):
                        if line.strip() == '---':
                            end_marker = i
                            break
                    if end_marker > 0:
                        content = '\n'.join(content_lines[end_marker + 1:])
                
                # Add section header with filename
                section_header = f"## Video Summary: {video_file.stem}"
                combined_sections.append(f"{section_header}\n\n{content.strip()}")
                
            except OSError as e:
                logger.warning(f"Failed to read video summary {video_file}: {e}")
                continue
        
        return '\n\n---\n\n'.join(combined_sections)
    
    def _write_corpus_document(self, corpus_path: Path, content: str, video_files: List[Path]) -> None:
        """Write the aggregated corpus document."""
        # Create frontmatter metadata
        frontmatter = [
            "---",
            f"research_plan: {self.research_plan.name}",
            f"plan_id: {self.research_plan.plan_id}",
            f"created: {datetime.now().isoformat()}",
            f"video_count: {len(video_files)}",
            "video_files:",
        ]
        
        for video_file in video_files:
            frontmatter.append(f"  - {video_file.name}")
        
        frontmatter.extend([
            f"description: {self.research_plan.description}",
            "---",
            ""
        ])
        
        # Combine frontmatter and content
        full_content = '\n'.join(frontmatter) + f"\n# Research Corpus: {self.research_plan.name}\n\n{content}"
        
        try:
            with open(corpus_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
        except OSError as e:
            raise CorpusError(f"Failed to write corpus document: {e}")
    
    def _read_corpus_content(self, corpus_path: Path) -> str:
        """Read corpus content, excluding frontmatter."""
        try:
            with open(corpus_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove YAML frontmatter
            lines = content.split('\n')
            if lines and lines[0].strip() == '---':
                end_marker = -1
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == '---':
                        end_marker = i
                        break
                if end_marker > 0:
                    content = '\n'.join(lines[end_marker + 1:])
            
            return content.strip()
            
        except OSError as e:
            raise CorpusError(f"Failed to read corpus file: {e}")
    
    def _analyze_corpus_chunk(self, chunk: str, model: str) -> str:
        """Analyze a corpus chunk using corpus-specific prompts."""
        base_prompt = self.research_plan.corpus_chunk_prompt
        
        # Add research context
        if self.research_plan.description:
            contextualized_prompt = f"""RESEARCH CONTEXT: {self.research_plan.description}

{base_prompt}"""
        else:
            contextualized_prompt = base_prompt
            
        prompt = contextualized_prompt.format(chunk=chunk)
        
        try:
            # Use the same infrastructure as regular summarization but with corpus prompts
            from .llm import ollama, requests
            
            try:
                response = ollama.generate(
                    model=model,
                    prompt=prompt,
                    options={"temperature": 0.7}
                )
                return response["response"].strip()
                
            except Exception as ollama_error:
                logger.warning(f"Ollama client failed, falling back to HTTP: {ollama_error}")
                
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7}
                }
                
                response = requests.post(
                    config.get_ollama_api_url("generate"),
                    json=payload,
                    timeout=config.OLLAMA_TIMEOUT
                )
                response.raise_for_status()
                
                return response.json()["response"].strip()
                
        except Exception as e:
            raise LLMError(f"Failed to analyze corpus chunk: {e}")
    
    def _generate_corpus_executive_summary(self, chunk_analyses: List[str], model: str) -> str:
        """Generate executive summary of corpus analysis."""
        base_prompt = self.research_plan.corpus_executive_prompt
        
        # Add research context
        if self.research_plan.description:
            contextualized_prompt = f"""RESEARCH CONTEXT: {self.research_plan.description}

{base_prompt}"""
        else:
            contextualized_prompt = base_prompt
            
        bullet_summaries = "\n\n".join(chunk_analyses)
        prompt = contextualized_prompt.format(bullet_summaries=bullet_summaries)
        
        try:
            from .llm import ollama, requests
            
            try:
                response = ollama.generate(
                    model=model,
                    prompt=prompt,
                    options={"temperature": 0.7}
                )
                return response["response"].strip()
                
            except Exception as ollama_error:
                logger.warning(f"Ollama client failed, falling back to HTTP: {ollama_error}")
                
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7}
                }
                
                response = requests.post(
                    config.get_ollama_api_url("generate"),
                    json=payload,
                    timeout=config.OLLAMA_TIMEOUT
                )
                response.raise_for_status()
                
                return response.json()["response"].strip()
                
        except Exception as e:
            raise LLMError(f"Failed to generate corpus executive summary: {e}")
    
    def _write_corpus_analysis(self, summary_path: Path, executive_analysis: str, 
                              chunk_analyses: List[str], model: str) -> None:
        """Write the corpus analysis document."""
        # Create frontmatter
        frontmatter = [
            "---",
            f"research_plan: {self.research_plan.name}",
            f"plan_id: {self.research_plan.plan_id}",
            f"analysis_created: {datetime.now().isoformat()}",
            f"model: {model}",
            f"chunk_count: {len(chunk_analyses)}",
            f"description: Comprehensive analysis of {self.research_plan.name} research corpus",
            "---",
            ""
        ]
        
        # Build content structure
        content_sections = [
            f"# Corpus Analysis: {self.research_plan.name}",
            "",
            "## Executive Analysis",
            "",
            executive_analysis,
            "",
            "## Detailed Analysis Sections",
            ""
        ]
        
        # Add individual chunk analyses
        for i, analysis in enumerate(chunk_analyses, 1):
            content_sections.extend([
                f"### Analysis Section {i}",
                "",
                analysis,
                ""
            ])
        
        # Combine all content
        full_content = '\n'.join(frontmatter) + '\n'.join(content_sections)
        
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
        except OSError as e:
            raise CorpusError(f"Failed to write corpus analysis: {e}")
    
    def _count_videos_in_corpus(self, corpus_path: Path) -> int:
        """Count the number of videos included in a corpus file."""
        try:
            with open(corpus_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count video summary sections
            return content.count("## Video Summary:")
            
        except OSError:
            return 0


# Convenience functions for corpus operations
def create_corpus_manager(research_plan: ResearchPlanConfig) -> CorpusManager:
    """Create a corpus manager for a research plan.
    
    Args:
        research_plan: Research plan configuration.
        
    Returns:
        CorpusManager instance.
    """
    return CorpusManager(research_plan)


def aggregate_and_analyze_corpus(research_plan: ResearchPlanConfig, 
                                video_ids: Optional[List[str]] = None,
                                model: Optional[str] = None) -> CorpusProcessingResult:
    """Run complete corpus pipeline for a research plan.
    
    Args:
        research_plan: Research plan configuration.
        video_ids: Optional list of specific video IDs to include.
        model: LLM model to use for analysis.
        
    Returns:
        CorpusProcessingResult with outcome.
    """
    manager = CorpusManager(research_plan)
    return manager.full_corpus_pipeline(video_ids, model)