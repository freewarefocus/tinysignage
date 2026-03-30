"""Tests for compute_content_hash() and generate_thumbnail() from app/media.py.

Feature tree refs: [FT-19.14]
"""

from pathlib import Path

from app.media import compute_content_hash, generate_thumbnail


def test_compute_content_hash_deterministic(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello world")
    assert compute_content_hash(f) == compute_content_hash(f)


def test_compute_content_hash_different_files(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"content A")
    f2.write_bytes(b"content B")
    assert compute_content_hash(f1) != compute_content_hash(f2)


def test_compute_content_hash_is_sha256(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"test content")
    h = compute_content_hash(f)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_generate_thumbnail_image(tmp_path):
    """Creates a .jpg thumbnail for an image (requires Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        import pytest
        pytest.skip("Pillow not installed")

    # Create a small valid PNG
    src = tmp_path / "source.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(src, "PNG")

    thumbs_dir = tmp_path / "thumbs"
    result = generate_thumbnail(src, thumbs_dir, "image", "test-asset-id")

    assert result == "test-asset-id.jpg"
    assert (thumbs_dir / "test-asset-id.jpg").exists()


def test_generate_thumbnail_unsupported_type(tmp_path):
    """asset_type='html' returns None."""
    src = tmp_path / "page.html"
    src.write_text("<h1>Hello</h1>")
    thumbs_dir = tmp_path / "thumbs"

    result = generate_thumbnail(src, thumbs_dir, "html", "html-asset-id")
    assert result is None
