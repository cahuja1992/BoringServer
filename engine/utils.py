"""Enhanced utilities with better error handling."""

import io
from typing import Tuple

from PIL import Image

from engine.exceptions import InvalidImageError
from engine.logging import get_logger

logger = get_logger(__name__)

# Configure PIL for security
Image.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None


def decode_image(raw_bytes: bytes) -> Image.Image:
    """Decode image from bytes.

    Args:
        raw_bytes: Raw image bytes

    Returns:
        PIL Image

    Raises:
        InvalidImageError: If image cannot be decoded
    """
    if not raw_bytes:
        raise InvalidImageError("Empty image data")

    try:
        img = Image.open(io.BytesIO(raw_bytes))

        # Convert to RGB if needed
        if img.mode != "RGB":
            logger.debug(f"Converting image from {img.mode} to RGB")
            img = img.convert("RGB")

        # Validate image dimensions
        width, height = img.size
        if width <= 0 or height <= 0:
            raise InvalidImageError(f"Invalid image dimensions: {width}x{height}")

        logger.debug(f"Image decoded successfully: {width}x{height}, mode={img.mode}")
        return img

    except InvalidImageError:
        raise
    except Exception as e:
        logger.error(f"Failed to decode image: {e}")
        raise InvalidImageError(f"Invalid image format: {str(e)}")


def validate_image_size(image: Image.Image, max_size_mb: float = 10.0) -> None:
    """Validate image size.

    Args:
        image: PIL Image
        max_size_mb: Maximum size in MB

    Raises:
        InvalidImageError: If image is too large
    """
    # Estimate size in bytes (width * height * channels)
    width, height = image.size
    channels = len(image.getbands())
    estimated_size = width * height * channels
    estimated_size_mb = estimated_size / (1024 * 1024)

    if estimated_size_mb > max_size_mb:
        raise InvalidImageError(
            f"Image too large: {estimated_size_mb:.2f}MB (max: {max_size_mb}MB)"
        )


def get_image_info(image: Image.Image) -> dict:
    """Get image information.

    Args:
        image: PIL Image

    Returns:
        Dictionary with image info
    """
    width, height = image.size
    return {
        "width": width,
        "height": height,
        "mode": image.mode,
        "format": image.format,
        "channels": len(image.getbands()),
    }


def resize_image(
    image: Image.Image, max_width: int = 1024, max_height: int = 1024
) -> Image.Image:
    """Resize image if it exceeds maximum dimensions.

    Args:
        image: PIL Image
        max_width: Maximum width
        max_height: Maximum height

    Returns:
        Resized PIL Image
    """
    width, height = image.size

    if width <= max_width and height <= max_height:
        return image

    # Calculate aspect ratio preserving dimensions
    ratio = min(max_width / width, max_height / height)
    new_width = int(width * ratio)
    new_height = int(height * ratio)

    logger.debug(f"Resizing image from {width}x{height} to {new_width}x{new_height}")
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
