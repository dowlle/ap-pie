"""Archipelago game generation via subprocess."""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    success: bool
    seed: str | None = None
    zip_path: Path | None = None
    log: str = ""
    error: str | None = None


def generate_game(
    yamls: list[tuple[str, str]],  # [(filename, yaml_content), ...]
    output_dir: str | Path,
    generator_exe: str,
    spoiler_level: int = 3,
    race_mode: bool = False,
    timeout: int = 300,
    custom_worlds_dir: str | None = None,
) -> GenerationResult:
    """
    Generate an Archipelago multiworld game.

    1. Write YAML files to a temp directory
    2. Optionally set up custom worlds for the generator to find
    3. Run the generator subprocess
    4. Find and move the output ZIP to output_dir
    5. Return result with seed name and log
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ap_gen_") as tmpdir:
        players_dir = Path(tmpdir) / "Players"
        players_dir.mkdir()
        gen_output = Path(tmpdir) / "output"
        gen_output.mkdir()

        # Write YAML files. filename is uploader-controlled, so strip any
        # path components before joining with players_dir.
        for filename, content in yamls:
            raw = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
            safe_name = raw or "player.yaml"
            (players_dir / safe_name).write_text(content, encoding="utf-8")

        # Build command
        cmd = [
            generator_exe,
            "--player_files_path", str(players_dir),
            "--outputpath", str(gen_output),
            "--spoiler", str(spoiler_level),
        ]
        if race_mode:
            cmd.append("--race")

        # Set up environment - point custom_worlds to our managed directory
        env = os.environ.copy()
        generator_dir = Path(generator_exe).parent

        # The AP generator looks for custom_worlds/ relative to its own directory.
        # If we have a separate custom worlds dir, symlink it into a temp working copy.
        cwd = str(generator_dir)
        if custom_worlds_dir:
            custom_src = Path(custom_worlds_dir)
            custom_dest = generator_dir / "custom_worlds"
            # If the generator dir is read-only (Docker mount), we can't create symlinks.
            # Instead, use a writable temp dir as CWD with custom_worlds linked in.
            if not os.access(str(generator_dir), os.W_OK):
                work_dir = Path(tmpdir) / "workdir"
                work_dir.mkdir()
                # Symlink custom_worlds into the work dir
                (work_dir / "custom_worlds").symlink_to(custom_src)
                cwd = str(work_dir)
            elif custom_src.is_dir() and not custom_dest.exists():
                try:
                    custom_dest.symlink_to(custom_src)
                except OSError:
                    pass

        logger.info(f"Running generation: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
        except FileNotFoundError:
            return GenerationResult(
                success=False,
                error=f"Generator not found: {generator_exe}",
            )
        except subprocess.TimeoutExpired:
            return GenerationResult(
                success=False,
                log="",
                error=f"Generation timed out after {timeout} seconds",
            )

        log_output = result.stdout + ("\n" + result.stderr if result.stderr else "")

        if result.returncode != 0:
            return GenerationResult(
                success=False,
                log=log_output,
                error=f"Generator exited with code {result.returncode}",
            )

        # Find the output ZIP
        zips = glob.glob(str(gen_output / "AP_*.zip"))
        if not zips:
            return GenerationResult(
                success=False,
                log=log_output,
                error="Generation completed but no output ZIP found",
            )

        src_zip = Path(zips[0])
        dest_zip = output_dir / src_zip.name

        # Move to final output directory
        shutil.move(str(src_zip), str(dest_zip))

        # Extract seed from filename: AP_{SEED}.zip
        seed = src_zip.stem.replace("AP_", "")

        logger.info(f"Generation complete: seed={seed}, output={dest_zip}")

        return GenerationResult(
            success=True,
            seed=seed,
            zip_path=dest_zip,
            log=log_output,
        )
