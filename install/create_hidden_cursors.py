#!/usr/bin/env python3
"""Generate transparent 1x1 Xcursor files for all standard cursor names.

Usage: python3 create_hidden_cursors.py <output_directory>

Creates valid Xcursor-format files containing a single 1x1 transparent pixel.
Used to hide the mouse cursor at the compositor level on Wayland (labwc, etc.).
"""
import struct
import sys
from pathlib import Path

# Xcursor binary format constants
XCURSOR_MAGIC = 0x72756358  # "Xcur" little-endian
XCURSOR_VERSION = 0x00010000
XCURSOR_IMAGE_TYPE = 0xFFFD0002

# All standard cursor names used by Wayland compositors, X11, and GTK/Qt apps.
# Includes common symlink aliases so every cursor shape resolves to transparent.
CURSOR_NAMES = [
    # Core pointers
    "default", "left_ptr", "arrow", "top_left_arrow",
    # Links / clickable
    "pointer", "hand", "hand1", "hand2", "pointing_hand",
    # Text
    "text", "ibeam", "xterm",
    # Busy / wait
    "wait", "watch", "progress", "left_ptr_watch", "half-busy",
    # Move / drag
    "move", "fleur", "grabbing", "grab", "dnd-move", "dnd-copy",
    "dnd-link", "dnd-none", "dnd-ask",
    # Resize edges
    "n-resize", "s-resize", "e-resize", "w-resize",
    "ne-resize", "nw-resize", "se-resize", "sw-resize",
    "top_side", "bottom_side", "left_side", "right_side",
    "top_left_corner", "top_right_corner",
    "bottom_left_corner", "bottom_right_corner",
    # Resize axes
    "ns-resize", "ew-resize", "nesw-resize", "nwse-resize",
    "row-resize", "col-resize",
    "sb_v_double_arrow", "sb_h_double_arrow",
    "size_ver", "size_hor", "size_fdiag", "size_bdiag", "size_all",
    # Crosshair
    "crosshair", "cross", "tcross", "cross_reverse",
    # Forbidden
    "not-allowed", "no-drop", "circle", "forbidden", "X_cursor",
    # Help
    "help", "question_arrow", "whats_this",
    # Context menu
    "context-menu",
    # Misc
    "copy", "alias", "cell", "vertical-text", "zoom-in", "zoom-out",
    "all-scroll", "pencil", "pirate", "plus",
    "up_arrow", "right_arrow", "left_arrow", "down_arrow",
    "based_arrow_up", "based_arrow_down",
]


def build_xcursor_image() -> bytes:
    """Build a minimal valid Xcursor file: single 1x1 transparent image."""
    nominal_size = 1
    header_size = 16  # file header
    toc_entry_size = 12  # one TOC entry
    image_header_size = 36  # image chunk header
    pixel_data = struct.pack("<I", 0x00000000)  # 1 ARGB pixel, fully transparent

    toc_offset = header_size
    image_offset = toc_offset + toc_entry_size

    # File header
    data = struct.pack(
        "<IIII",
        XCURSOR_MAGIC,
        header_size,
        XCURSOR_VERSION,
        1,  # ntoc (one entry)
    )
    # TOC entry
    data += struct.pack(
        "<III",
        XCURSOR_IMAGE_TYPE,
        nominal_size,
        image_offset,
    )
    # Image chunk header
    data += struct.pack(
        "<IIIIIIIII",
        image_header_size,
        XCURSOR_IMAGE_TYPE,
        nominal_size,
        1,  # version
        1,  # width
        1,  # height
        0,  # xhot
        0,  # yhot
        0,  # delay
    )
    # Pixel data
    data += pixel_data

    return data


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <output_directory>")
        sys.exit(1)

    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    image_data = build_xcursor_image()
    count = 0

    for name in CURSOR_NAMES:
        (out_dir / name).write_bytes(image_data)
        count += 1

    print(f"Created {count} transparent cursor files in {out_dir}")


if __name__ == "__main__":
    main()
