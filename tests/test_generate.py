from pathlib import Path

import pytest
from PIL import Image

from idotmatrix_upload.generate import generate_spinning_number_gif, generate_test_set


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
