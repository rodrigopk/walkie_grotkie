from pathlib import Path

import pytest
from PIL import Image

from idotmatrix_upload.generate import (
    assemble_gif_from_frames,
    generate_spinning_number_gif,
    generate_test_set,
)


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path / "gifs"


class TestGenerateSpinningNumberGif:
    def test_creates_valid_gif(self, tmp_output: Path):
        path = generate_spinning_number_gif(1, tmp_output / "test.gif")
        assert path.exists()
        with Image.open(path) as img:
            assert img.format == "GIF"

    def test_correct_resolution(self, tmp_output: Path):
        path = generate_spinning_number_gif(5, tmp_output / "test.gif", size=32)
        with Image.open(path) as img:
            assert img.size == (32, 32)

    def test_custom_resolution(self, tmp_output: Path):
        path = generate_spinning_number_gif(3, tmp_output / "test.gif", size=16)
        with Image.open(path) as img:
            assert img.size == (16, 16)

    def test_correct_frame_count(self, tmp_output: Path):
        num_frames = 36
        path = generate_spinning_number_gif(
            1, tmp_output / "test.gif", num_frames=num_frames
        )
        with Image.open(path) as img:
            count = 0
            try:
                while True:
                    count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
            assert count == num_frames

    def test_file_size_reasonable(self, tmp_output: Path):
        path = generate_spinning_number_gif(7, tmp_output / "test.gif")
        size = path.stat().st_size
        assert size > 100, "GIF should not be trivially small"
        assert size < 50_000, "GIF should be small enough for BLE transfer"

    def test_double_digit_number(self, tmp_output: Path):
        path = generate_spinning_number_gif(10, tmp_output / "test.gif")
        assert path.exists()
        with Image.open(path) as img:
            assert img.format == "GIF"
            assert img.size == (32, 32)

    def test_creates_parent_directory(self, tmp_path: Path):
        deep_path = tmp_path / "a" / "b" / "c" / "test.gif"
        path = generate_spinning_number_gif(1, deep_path)
        assert path.exists()


class TestGenerateTestSet:
    def test_creates_all_files(self, tmp_output: Path):
        paths = generate_test_set(tmp_output, count=10)
        assert len(paths) == 10
        for p in paths:
            assert p.exists()

    def test_filenames(self, tmp_output: Path):
        paths = generate_test_set(tmp_output, count=3)
        names = [p.name for p in paths]
        assert names == ["number_01.gif", "number_02.gif", "number_03.gif"]

    def test_all_valid_gifs(self, tmp_output: Path):
        paths = generate_test_set(tmp_output, count=5)
        for p in paths:
            with Image.open(p) as img:
                assert img.format == "GIF"
                assert img.size == (32, 32)

    def test_custom_size(self, tmp_output: Path):
        paths = generate_test_set(tmp_output, count=2, size=16)
        for p in paths:
            with Image.open(p) as img:
                assert img.size == (16, 16)


class TestAssembleGifFromFrames:
    def _make_frames(self, tmp_path: Path, count: int = 5, size: int = 64) -> list[Path]:
        """Create distinct PNG frames for testing."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir(exist_ok=True)
        paths = []
        for i in range(count):
            r = (i * 37) % 256
            g = (i * 73 + 50) % 256
            b = (i * 113 + 100) % 256
            img = Image.new("RGBA", (size, size), (r, g, b, 255))
            p = frames_dir / f"frame_{i:03d}.png"
            img.save(p)
            paths.append(p)
        return paths

    def test_assembles_valid_gif(self, tmp_path: Path):
        frames = self._make_frames(tmp_path)
        out = tmp_path / "out.gif"
        result = assemble_gif_from_frames(frames, out, fps=10)
        assert result.exists()
        with Image.open(result) as img:
            assert img.format == "GIF"

    def test_correct_frame_count(self, tmp_path: Path):
        frames = self._make_frames(tmp_path, count=12)
        out = tmp_path / "out.gif"
        assemble_gif_from_frames(frames, out)
        with Image.open(out) as img:
            count = 0
            try:
                while True:
                    count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
            assert count == 12

    def test_correct_dimensions(self, tmp_path: Path):
        frames = self._make_frames(tmp_path, size=64)
        out = tmp_path / "out.gif"
        assemble_gif_from_frames(frames, out)
        with Image.open(out) as img:
            assert img.size == (64, 64)

    def test_resize_option(self, tmp_path: Path):
        frames = self._make_frames(tmp_path, size=64)
        out = tmp_path / "out.gif"
        assemble_gif_from_frames(frames, out, size=(32, 32))
        with Image.open(out) as img:
            assert img.size == (32, 32)

    def test_empty_frames_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="No frame"):
            assemble_gif_from_frames([], tmp_path / "out.gif")

    def test_inconsistent_sizes_raises(self, tmp_path: Path):
        d = tmp_path / "frames"
        d.mkdir()
        Image.new("RGBA", (64, 64), "red").save(d / "a.png")
        Image.new("RGBA", (32, 32), "blue").save(d / "b.png")
        with pytest.raises(ValueError, match="expected 64x64"):
            assemble_gif_from_frames(sorted(d.glob("*.png")), tmp_path / "out.gif")

    def test_creates_parent_dirs(self, tmp_path: Path):
        frames = self._make_frames(tmp_path, count=2)
        out = tmp_path / "deep" / "nested" / "out.gif"
        result = assemble_gif_from_frames(frames, out)
        assert result.exists()

    def test_fps_affects_duration(self, tmp_path: Path):
        frames = self._make_frames(tmp_path, count=3)
        out = tmp_path / "out.gif"
        assemble_gif_from_frames(frames, out, fps=10)
        with Image.open(out) as img:
            assert img.info.get("duration") == 100
