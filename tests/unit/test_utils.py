"""Unit tests for utility functions."""

import io

import pytest
from PIL import Image

from engine.exceptions import InvalidImageError
from engine.utils import (
    decode_image,
    get_image_info,
    resize_image,
    validate_image_size,
)


def create_test_image(width=100, height=100, mode="RGB"):
    """Create a test image.

    Args:
        width: Image width
        height: Image height
        mode: Image mode

    Returns:
        PIL Image
    """
    return Image.new(mode, (width, height), color="red")


def image_to_bytes(img, format="PNG"):
    """Convert PIL image to bytes.

    Args:
        img: PIL Image
        format: Image format

    Returns:
        Image bytes
    """
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


class TestDecodeImage:
    """Tests for decode_image function."""

    def test_decode_valid_image(self):
        """Test decoding valid image."""
        img = create_test_image(100, 100)
        img_bytes = image_to_bytes(img)

        decoded = decode_image(img_bytes)

        assert isinstance(decoded, Image.Image)
        assert decoded.size == (100, 100)
        assert decoded.mode == "RGB"

    def test_decode_empty_bytes(self):
        """Test decoding empty bytes."""
        with pytest.raises(InvalidImageError, match="Empty image data"):
            decode_image(b"")

    def test_decode_invalid_bytes(self):
        """Test decoding invalid image bytes."""
        with pytest.raises(InvalidImageError, match="Invalid image format"):
            decode_image(b"not an image")

    def test_decode_grayscale_converts_to_rgb(self):
        """Test that grayscale images are converted to RGB."""
        img = create_test_image(100, 100, mode="L")
        img_bytes = image_to_bytes(img)

        decoded = decode_image(img_bytes)

        assert decoded.mode == "RGB"

    def test_decode_rgba_converts_to_rgb(self):
        """Test that RGBA images are converted to RGB."""
        img = create_test_image(100, 100, mode="RGBA")
        img_bytes = image_to_bytes(img, format="PNG")

        decoded = decode_image(img_bytes)

        assert decoded.mode == "RGB"

    @pytest.mark.parametrize("format", ["PNG", "JPEG", "BMP"])
    def test_decode_different_formats(self, format):
        """Test decoding different image formats."""
        img = create_test_image(50, 50)

        # JPEG doesn't support transparency, so use RGB
        if format == "JPEG":
            img = img.convert("RGB")

        img_bytes = image_to_bytes(img, format=format)
        decoded = decode_image(img_bytes)

        assert isinstance(decoded, Image.Image)
        assert decoded.mode == "RGB"


class TestValidateImageSize:
    """Tests for validate_image_size function."""

    def test_validate_small_image(self):
        """Test validation of small image."""
        img = create_test_image(100, 100)

        # Should not raise
        validate_image_size(img, max_size_mb=10.0)

    def test_validate_large_image_fails(self):
        """Test validation fails for large image."""
        # Create large image (2000x2000 RGB = 12MB)
        img = create_test_image(2000, 2000)

        with pytest.raises(InvalidImageError, match="too large"):
            validate_image_size(img, max_size_mb=1.0)

    def test_validate_exact_limit(self):
        """Test validation at exact limit."""
        img = create_test_image(1000, 1000)  # ~3MB

        # Should not raise
        validate_image_size(img, max_size_mb=5.0)


class TestGetImageInfo:
    """Tests for get_image_info function."""

    def test_get_info_rgb(self):
        """Test getting info for RGB image."""
        img = create_test_image(200, 150, mode="RGB")

        info = get_image_info(img)

        assert info["width"] == 200
        assert info["height"] == 150
        assert info["mode"] == "RGB"
        assert info["channels"] == 3

    def test_get_info_grayscale(self):
        """Test getting info for grayscale image."""
        img = create_test_image(100, 100, mode="L")

        info = get_image_info(img)

        assert info["width"] == 100
        assert info["height"] == 100
        assert info["mode"] == "L"
        assert info["channels"] == 1

    def test_get_info_rgba(self):
        """Test getting info for RGBA image."""
        img = create_test_image(50, 75, mode="RGBA")

        info = get_image_info(img)

        assert info["width"] == 50
        assert info["height"] == 75
        assert info["mode"] == "RGBA"
        assert info["channels"] == 4


class TestResizeImage:
    """Tests for resize_image function."""

    def test_resize_no_change_needed(self):
        """Test resize when image is already small enough."""
        img = create_test_image(500, 400)

        resized = resize_image(img, max_width=1024, max_height=1024)

        # Should return same image
        assert resized.size == (500, 400)

    def test_resize_width_exceeded(self):
        """Test resize when width exceeds maximum."""
        img = create_test_image(2000, 1000)

        resized = resize_image(img, max_width=1024, max_height=1024)

        # Width should be 1024, height proportionally scaled
        assert resized.size[0] == 1024
        assert resized.size[1] == 512  # 1000 * 0.512

    def test_resize_height_exceeded(self):
        """Test resize when height exceeds maximum."""
        img = create_test_image(1000, 2000)

        resized = resize_image(img, max_width=1024, max_height=1024)

        # Height should be 1024, width proportionally scaled
        assert resized.size[1] == 1024
        assert resized.size[0] == 512  # 1000 * 0.512

    def test_resize_both_exceeded(self):
        """Test resize when both dimensions exceed maximum."""
        img = create_test_image(3000, 2000)

        resized = resize_image(img, max_width=1024, max_height=1024)

        # Should scale to maintain aspect ratio
        assert resized.size[0] <= 1024
        assert resized.size[1] <= 1024

        # Check aspect ratio preserved (approximately)
        original_ratio = 3000 / 2000
        new_ratio = resized.size[0] / resized.size[1]
        assert abs(original_ratio - new_ratio) < 0.01

    def test_resize_square_image(self):
        """Test resizing square image."""
        img = create_test_image(2000, 2000)

        resized = resize_image(img, max_width=500, max_height=500)

        assert resized.size == (500, 500)

    def test_resize_custom_dimensions(self):
        """Test resize with custom max dimensions."""
        img = create_test_image(1000, 800)

        resized = resize_image(img, max_width=200, max_height=200)

        assert resized.size[0] == 200
        assert resized.size[1] == 160  # Maintains aspect ratio


class TestIntegration:
    """Integration tests for utility functions."""

    def test_decode_and_validate_pipeline(self):
        """Test decode -> validate pipeline."""
        img = create_test_image(500, 500)
        img_bytes = image_to_bytes(img)

        # Decode
        decoded = decode_image(img_bytes)

        # Validate
        validate_image_size(decoded, max_size_mb=5.0)

        # Get info
        info = get_image_info(decoded)

        assert info["width"] == 500
        assert info["height"] == 500
        assert info["mode"] == "RGB"

    def test_decode_resize_pipeline(self):
        """Test decode -> resize pipeline."""
        img = create_test_image(2000, 1500)
        img_bytes = image_to_bytes(img)

        # Decode
        decoded = decode_image(img_bytes)

        # Resize
        resized = resize_image(decoded, max_width=800, max_height=800)

        assert resized.size[0] == 800
        assert resized.size[1] == 600
        assert resized.mode == "RGB"
