from pathlib import Path

import pytest
from PIL import Image

from idotmatrix_upload.sprite import GROT_PNG, Sprite


def _make_test_png(tmp_path: Path, size: int = 8) -> Path:
    """Create a small test PNG with a known opaque region.

    Opaque pixels form a 4x4 block at (2,2)-(5,5) on an 8x8 canvas.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(2, 6):
        for x in range(2, 6):
            px[x, y] = (100 + x, 50 + y, 200, 255)
    p = tmp_path / "test_sprite.png"
    img.save(p)
    return p


class TestFromPng:
    def test_loads_grot(self):
        sprite = Sprite.from_png(GROT_PNG)
        assert len(sprite.pixels) > 0
        assert sprite.width == 64
        assert sprite.height == 64
        min_x, min_y, max_x, max_y = sprite.bbox
        assert 0 <= min_x <= max_x < 64
        assert 0 <= min_y <= max_y < 64

    def test_extracts_only_opaque(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)
        assert len(sprite.pixels) == 16  # 4x4 block
        for x, y, _ in sprite.pixels:
            assert 2 <= x <= 5
            assert 2 <= y <= 5

    def test_center_computed_correctly(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)
        assert sprite.bbox == (2, 2, 5, 5)
        assert sprite.center_x == 3.5
        assert sprite.center_y == 3.5

    def test_fully_transparent_raises(self, tmp_path: Path):
        img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        p = tmp_path / "empty.png"
        img.save(p)
        with pytest.raises(ValueError, match="No opaque pixels"):
            Sprite.from_png(p)

    def test_accepts_string_path(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(str(png))
        assert len(sprite.pixels) == 16


class TestRenderFrame:
    def test_default_frame(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)
        frame = sprite.render_frame()
        assert frame.size == (8, 8)
        px = frame.load()
        assert px[0, 0] == (0, 0, 0, 255)  # background
        assert px[3, 3][3] == 255  # character pixel is opaque

    def test_y_offset(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)

        frame_normal = sprite.render_frame()
        frame_shifted = sprite.render_frame(y_offset=-2)

        px_normal = frame_normal.load()
        px_shifted = frame_shifted.load()

        # Row 2 in normal should appear at row 0 when shifted up by 2
        assert px_normal[3, 2] == px_shifted[3, 0]

    def test_x_offset(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)

        frame_normal = sprite.render_frame()
        frame_shifted = sprite.render_frame(x_offset=1)

        px_normal = frame_normal.load()
        px_shifted = frame_shifted.load()

        assert px_normal[2, 3] == px_shifted[3, 3]

    def test_flip_x(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)

        frame_normal = sprite.render_frame()
        frame_flipped = sprite.render_frame(flip_x=True)

        px_normal = frame_normal.load()
        px_flipped = frame_flipped.load()

        # center_x = 3.5, so pixel at x=2 should map to x=5 and vice versa
        assert px_normal[2, 3] == px_flipped[5, 3]
        assert px_normal[5, 3] == px_flipped[2, 3]

    def test_clips_to_bounds(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)
        frame = sprite.render_frame(y_offset=-100)
        assert frame.size == (8, 8)
        px = frame.load()
        for y in range(8):
            for x in range(8):
                assert px[x, y] == (0, 0, 0, 255)

    def test_custom_background(self, tmp_path: Path):
        png = _make_test_png(tmp_path)
        sprite = Sprite.from_png(png)
        frame = sprite.render_frame(bg=(255, 0, 0, 255))
        px = frame.load()
        assert px[0, 0] == (255, 0, 0, 255)


class TestGrotPngConstant:
    def test_exists(self):
        assert GROT_PNG.exists(), f"Expected grot.png at {GROT_PNG}"

    def test_is_png(self):
        with Image.open(GROT_PNG) as img:
            assert img.format == "PNG"
            assert img.size == (64, 64)
