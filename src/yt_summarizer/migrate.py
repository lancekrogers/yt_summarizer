"""
Migration utilities for existing users.

Provides detection and migration of legacy data from current working directory
to XDG-compliant configuration locations.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class LegacyData:
    """Detected legacy data locations."""
    data_dir: Optional[Path] = None
    logs_dir: Optional[Path] = None
    research_plans_dir: Optional[Path] = None

    def has_legacy_data(self) -> bool:
        """Check if any legacy data was detected."""
        return any([self.data_dir, self.logs_dir, self.research_plans_dir])

    def get_paths(self) -> List[Tuple[str, Path]]:
        """Get list of (name, path) tuples for existing legacy directories."""
        paths = []
        if self.data_dir:
            paths.append(("data", self.data_dir))
        if self.logs_dir:
            paths.append(("logs", self.logs_dir))
        if self.research_plans_dir:
            paths.append(("research_plans", self.research_plans_dir))
        return paths


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    moved: List[Tuple[Path, Path]]
    errors: List[Tuple[Path, str]]

    @property
    def success(self) -> bool:
        """Check if migration was fully successful."""
        return len(self.errors) == 0

    @property
    def partial_success(self) -> bool:
        """Check if migration was at least partially successful."""
        return len(self.moved) > 0


def detect_legacy_data(cwd: Optional[Path] = None) -> LegacyData:
    """Detect legacy data in current working directory.

    Looks for data/, logs/, and research_plans/ directories that may contain
    data from previous installations using relative paths.

    Args:
        cwd: Directory to search. Defaults to current working directory.

    Returns:
        LegacyData with paths to detected directories.
    """
    cwd = cwd or Path.cwd()

    return LegacyData(
        data_dir=cwd / "data" if (cwd / "data").exists() else None,
        logs_dir=cwd / "logs" if (cwd / "logs").exists() else None,
        research_plans_dir=cwd / "research_plans" if (cwd / "research_plans").exists() else None,
    )


def is_migration_needed(legacy: LegacyData, target_config_dir: Path) -> bool:
    """Check if migration is needed.

    Migration is needed if legacy data exists and target location is empty.

    Args:
        legacy: Detected legacy data.
        target_config_dir: XDG-compliant config directory.

    Returns:
        True if migration should be offered to user.
    """
    if not legacy.has_legacy_data():
        return False

    # Check if target already has data
    target_data = target_config_dir / "data"
    if target_data.exists() and any(target_data.iterdir()):
        return False

    return True


def migrate_legacy_data(
    legacy: LegacyData,
    target_config_dir: Path,
    copy: bool = False,
) -> MigrationResult:
    """Migrate legacy data to XDG-compliant location.

    Args:
        legacy: Detected legacy data locations.
        target_config_dir: Target configuration directory.
        copy: If True, copy data instead of moving.

    Returns:
        MigrationResult with moved paths and any errors.
    """
    result = MigrationResult(moved=[], errors=[])
    operation = shutil.copytree if copy else shutil.move

    mappings = [
        (legacy.data_dir, target_config_dir / "data"),
        (legacy.logs_dir, target_config_dir / "logs"),
        (legacy.research_plans_dir, target_config_dir / "research_plans"),
    ]

    for source, target in mappings:
        if source is None or not source.exists():
            continue

        try:
            if target.exists():
                # Merge into existing directory
                _merge_directory(source, target, copy=copy)
            else:
                # Move/copy entire directory
                target.parent.mkdir(parents=True, exist_ok=True)
                operation(str(source), str(target))

            result.moved.append((source, target))

        except Exception as e:
            result.errors.append((source, str(e)))

    return result


def _merge_directory(source: Path, target: Path, copy: bool = False) -> None:
    """Merge source directory into target, not overwriting existing files.

    Args:
        source: Source directory to merge from.
        target: Target directory to merge into.
        copy: If True, copy instead of moving.
    """
    operation = shutil.copy2 if copy else shutil.move

    for item in source.iterdir():
        dest = target / item.name

        if dest.exists():
            if item.is_dir() and dest.is_dir():
                # Recursively merge subdirectories
                _merge_directory(item, dest, copy=copy)
            # Skip existing files (don't overwrite)
            continue

        if item.is_dir():
            if copy:
                shutil.copytree(str(item), str(dest))
            else:
                shutil.move(str(item), str(dest))
        else:
            operation(str(item), str(dest))


def get_migration_summary(legacy: LegacyData) -> Dict[str, int]:
    """Get summary of legacy data for display.

    Args:
        legacy: Detected legacy data.

    Returns:
        Dictionary with counts of files/directories in each legacy location.
    """
    summary = {}

    for name, path in legacy.get_paths():
        if path.is_dir():
            file_count = sum(1 for _ in path.rglob("*") if _.is_file())
            summary[name] = file_count

    return summary
