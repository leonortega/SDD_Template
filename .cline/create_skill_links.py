#!/usr/bin/env python3
"""
Python script to create directory junctions from .codex/skills to .cline/skills
This creates a mapping/wrapper structure where .cline/skills contains links to the actual skills
"""

import subprocess  # nosec
import sys
from pathlib import Path


def create_skill_junctions():
    """Create directory junctions for all skills from .codex/skills to .cline/skills"""

    # Define source and target directories
    source_dir = Path(".codex/skills")
    target_dir = Path(".cline/skills")

    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    print("Creating directory junctions from .codex/skills to .cline/skills...")
    print("=" * 60)

    # Get all skill directories (excluding _shared)
    skill_dirs = [d for d in source_dir.iterdir() if d.is_dir() and d.name != "_shared"]

    success_count = 0
    skip_count = 0

    for skill_dir in skill_dirs:
        source_path = skill_dir
        target_path = target_dir / skill_dir.name

        print(f"Processing: {skill_dir.name}")

        # Skip if target already exists
        if target_path.exists():
            print(f"  -> Already exists: {target_path}")
            skip_count += 1
            continue

        # Create junction using mklink /J
        try:
            # mklink /J requires Windows and the paths to be absolute for reliability
            abs_source = source_path.resolve()
            abs_target = target_path.resolve()

            # mklink command
            cmd = ["mklink", "/J", str(abs_target), str(abs_source)]
            subprocess.run(
                cmd, shell=False, check=True, capture_output=True, text=True
            )  # nosec

            print(f"  [OK] Created junction: {target_path} -> {source_path}")
            success_count += 1

        except subprocess.CalledProcessError as e:
            print(
                f"  [ERROR] Failed to create junction for {skill_dir.name}: {e.stderr}"
            )
        except Exception as e:
            print(f"  [ERROR] Error creating junction for {skill_dir.name}: {str(e)}")

    print("=" * 60)
    print("Skill mapping completed!")
    print(f"  * Successfully created: {success_count} junctions")
    print(f"  * Skipped (already exist): {skip_count} junctions")
    print(f"  * Total skills processed: {len(skill_dirs)}")

    if success_count > 0:
        print("\n.cline/skills now contains junctions to .codex/skills")
    else:
        print("\nNo new junctions were created (all already exist)")


if __name__ == "__main__":
    # Check if we're on Windows (mklink is Windows-only)
    if not sys.platform.startswith("win32"):
        print("Error: This script requires Windows (mklink command)")
        print("The directory junction functionality is Windows-specific.")
        sys.exit(1)

    create_skill_junctions()
