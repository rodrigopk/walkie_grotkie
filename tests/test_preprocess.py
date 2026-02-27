from pathlib import Path

import pytest
from PIL import Image

from idotmatrix_upload.generate import generate_spinning_number_gif
from idotmatrix_upload.preprocess import (
    PreprocessResult,
    ValidationError,
    preprocess_batch,
    preprocess_gif,
    validate_gif,
)


@pytest.fixture
def valid_gif_32(tmp_path: Path) -> Path:
    """Create a valid 32x32 test GIF."""
    return generate_spinning_number_gif(
        1, tmp_path / "input" / "test_32.gif", size=32, num_frames=4
    )


@pytest.fixture
def valid_gif_64(tmp_path: Path) -> Path:
    """Create a valid 64x64 GIF (oversized for the device)."""
    return generate_spinning_number_gif(
        2, tmp_path / "input" / "test_64.gif", size=64, num_frames=4
    )


@pytest.fixture
def non_gif_file(tmp_path: Path) -> Path:
    """Create a file that is not a GIF."""
    path = tmp_path / "input" / "not_a_gif.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("This is not a GIF file")
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "processed"


class TestValidateGif:
    def test_valid_gif_passes(self, valid_gif_32: Path):
        validate_gif(valid_gif_32)

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="File not found"):
            validate_gif(tmp_path / "nonexistent.gif")

    def test_non_gif_raises(self, non_gif_file: Path):
        with pytest.raises(ValueError, match="Not a valid GIF"):
            validate_gif(non_gif_file)

    def test_empty_file_raises(self, tmp_path: Path):
        empty = tmp_path / "empty.gif"
        empty.write_bytes(b"")
        with pytest.raises(ValueError, match="Not a valid GIF"):
            validate_gif(empty)

    def test_truncated_gif_header(self, tmp_path: Path):
        path = tmp_path / "truncated.gif"
        path.write_bytes(b"GIF89a")  # header only, no image data
        with pytest.raises(ValueError):
            validate_gif(path)


class TestPreprocessGif:
    def test_correct_size_passthrough(self, valid_gif_32: Path, output_dir: Path):
        result = preprocess_gif(valid_gif_32, output_dir)
        assert result.output_size == (32, 32)
        assert result.output_path.exists()
        with Image.open(result.output_path) as img:
            assert img.size == (32, 32)
            assert img.format == "GIF"

    def test_oversized_gif_resized(self, valid_gif_64: Path, output_dir: Path):
        result = preprocess_gif(valid_gif_64, output_dir, target_size=(32, 32))
        assert result.original_size == (64, 64)
        assert result.output_size == (32, 32)
        with Image.open(result.output_path) as img:
            assert img.size == (32, 32)

    def test_result_stats(self, valid_gif_32: Path, output_dir: Path):
        result = preprocess_gif(valid_gif_32, output_dir)
        assert isinstance(result, PreprocessResult)
        assert result.input_path == valid_gif_32
        assert result.output_path == output_dir / valid_gif_32.name
        assert result.original_bytes > 0
        assert result.output_bytes > 0
        assert result.frame_count == 4

    def test_custom_target_size(self, valid_gif_32: Path, output_dir: Path):
        result = preprocess_gif(valid_gif_32, output_dir, target_size=(16, 16))
        assert result.output_size == (16, 16)
        with Image.open(result.output_path) as img:
            assert img.size == (16, 16)

    def test_creates_output_directory(self, valid_gif_32: Path, tmp_path: Path):
        deep_dir = tmp_path / "a" / "b" / "c"
        result = preprocess_gif(valid_gif_32, deep_dir)
        assert result.output_path.exists()

    def test_output_frame_count_preserved(self, valid_gif_32: Path, output_dir: Path):
        result = preprocess_gif(valid_gif_32, output_dir)
        with Image.open(result.output_path) as img:
            count = 0
            try:
                while True:
                    count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        assert count == result.frame_count


class TestPreprocessBatch:
    def test_all_valid(self, tmp_path: Path, output_dir: Path):
        gifs = [
            generate_spinning_number_gif(
                i, tmp_path / "input" / f"num_{i}.gif", num_frames=4
            )
            for i in range(1, 4)
        ]
        results = preprocess_batch(gifs, output_dir)
        assert len(results) == 3
        for r in results:
            assert r.output_path.exists()

    def test_validates_all_before_processing(
        self, valid_gif_32: Path, non_gif_file: Path, tmp_path: Path, output_dir: Path
    ):
        missing = tmp_path / "does_not_exist.gif"
        with pytest.raises(ValidationError) as exc_info:
            preprocess_batch([valid_gif_32, non_gif_file, missing], output_dir)

        errors = exc_info.value.errors
        assert len(errors) == 2

        error_paths = [p for p, _ in errors]
        assert non_gif_file in error_paths
        assert missing in error_paths

        # Valid file should NOT have been processed since batch failed
        assert not (output_dir / valid_gif_32.name).exists()

    def test_error_message_lists_all_failures(
        self, non_gif_file: Path, tmp_path: Path, output_dir: Path
    ):
        missing = tmp_path / "ghost.gif"
        with pytest.raises(ValidationError, match="2 file"):
            preprocess_batch([non_gif_file, missing], output_dir)

    def test_empty_batch(self, output_dir: Path):
        results = preprocess_batch([], output_dir)
        assert results == []
