"""Media processing: thumbnail generation and content hashing."""

import hashlib
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("tinysignage.media")

THUMB_SIZE = (320, 180)


def compute_content_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of file content."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()


def generate_image_thumbnail(
    source: Path, thumbs_dir: Path, thumb_filename: str
) -> str | None:
    """Generate a thumbnail for an image file using Pillow."""
    try:
        from PIL import Image

        dest = thumbs_dir / thumb_filename
        with Image.open(source) as img:
            img.thumbnail(THUMB_SIZE)
            img.save(dest, "JPEG", quality=80)
        log.info("Generated image thumbnail: %s", thumb_filename)
        return thumb_filename
    except ImportError:
        log.warning("Pillow not installed — skipping image thumbnail")
        return None
    except Exception:
        log.exception("Failed to generate image thumbnail for %s", source.name)
        return None


def generate_video_thumbnail(
    source: Path, thumbs_dir: Path, thumb_filename: str
) -> str | None:
    """Generate a thumbnail for a video file using FFmpeg (best-effort)."""
    dest = thumbs_dir / thumb_filename
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(source),
                "-ss", "00:00:01",
                "-vframes", "1",
                "-vf", f"scale={THUMB_SIZE[0]}:{THUMB_SIZE[1]}:force_original_aspect_ratio=decrease",
                "-q:v", "5",
                str(dest),
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and dest.exists():
            log.info("Generated video thumbnail: %s", thumb_filename)
            return thumb_filename
        log.warning("FFmpeg returned %d for %s", result.returncode, source.name)
        dest.unlink(missing_ok=True)
        return None
    except FileNotFoundError:
        log.info("FFmpeg not found — skipping video thumbnail")
        return None
    except subprocess.TimeoutExpired:
        log.warning("FFmpeg timed out for %s", source.name)
        dest.unlink(missing_ok=True)
        return None
    except Exception:
        log.exception("Failed to generate video thumbnail for %s", source.name)
        dest.unlink(missing_ok=True)
        return None


def generate_thumbnail(
    source: Path, thumbs_dir: Path, asset_type: str, asset_id: str
) -> str | None:
    """Generate a thumbnail based on asset type. Returns the thumbnail filename or None."""
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    thumb_filename = f"{asset_id}.jpg"

    if asset_type == "image":
        return generate_image_thumbnail(source, thumbs_dir, thumb_filename)
    elif asset_type == "video":
        return generate_video_thumbnail(source, thumbs_dir, thumb_filename)
    return None
