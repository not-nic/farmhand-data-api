"""
Python module containing an image conversion service, for handling implementation
with wand to convert .dds to .webp, and decoding GIANTS Engine .grle info layer
files (Farming Simulator 22/25) into grayscale .png images.

GRLE format:
    Header (20 bytes, little-endian):
        0-3   Magic "GRLE"
        4-5   Version (u16, always 1)
        6-7   Width / 256 (u16)
        8-9   Reserved
        10-11 Height / 256 (u16)
        12    Reserved
        13    Channels (always 1)
        14-15 Reserved
        16-19 Compressed data size (informational)

    RLE data (from byte 20):
        - First byte is padding, skip it.
        - Read byte pairs (a, b):
            a == b -> a run: read count bytes (each 0xFF adds 255, the
                      first non-0xFF byte is the remainder), emit
                      (count + 2) copies.
            a != b -> emit one copy of a, then back up one byte so b
                      becomes the next pair's first byte.
"""

import struct
from io import BytesIO
from typing import NamedTuple

from PIL import Image
from wand.exceptions import WandException
from wand.image import Image as WandImage

from src.api.core.logger import logger

GRLE_HEADER_SIZE = 20
GRLE_MAGIC = b"GRLE"
GRLE_SUPPORTED_VERSION = 1
GRLE_DIMENSION_SCALE = 256  # header stores width/height divided by 256
GRLE_RUN_LENGTH_OFFSET = 2  # a run of (a, a) always means at least 2 pixels
GRLE_EXTENSION_BYTE = 0xFF  # each 0xFF in a count chain adds 255 to the run


class GrleHeader(NamedTuple):
    """
    Parsed dimensions from a GRLE file's header.
    """

    width: int
    height: int

    @property
    def pixel_count(self) -> int:
        """Total number of pixels described by this header."""
        return self.width * self.height


class _RunLengthReader:
    """
    Cursor over a GRLE RLE byte stream.
    """

    def __init__(self, stream: bytes, start_pos: int = 0) -> None:
        self._stream = stream
        self._pos = start_pos

    def __iter__(self) -> "_RunLengthReader":
        return self

    def __next__(self) -> tuple[int, int]:
        """Read and consume the next byte pair, or stop if none remain."""
        if self._pos + 1 >= len(self._stream):
            raise StopIteration

        first, second = self._stream[self._pos], self._stream[self._pos + 1]
        self._pos += 2
        return first, second

    def step_back(self) -> None:
        """Rewind by one byte, used when a pair turns out to be a transition."""
        self._pos -= 1

    def read_run_length(self) -> int:
        """
        Read an extended run count: keep consuming bytes and adding each
        one to the count, stopping after a byte that isn't the extension
        marker. A run always represents at least GRLE_RUN_LENGTH_OFFSET
        pixels, so that's added on at the end.

        :return: The decoded run length.
        """
        count: int = 0
        while self._pos < len(self._stream):
            byte = self._stream[self._pos]
            self._pos += 1
            count += byte
            if byte != GRLE_EXTENSION_BYTE:
                break
        return count + GRLE_RUN_LENGTH_OFFSET


class ImageConverterService:
    """
    Python service to convert images. Wraps Wand/ImageMagick for .dds
    conversion and decodes .grle images into grayscale .png images.
    """

    @staticmethod
    def convert_image(image: bytes, output_format: str = "webp") -> bytes:
        """
        Convert a Farming Simulator .dds to the given output format.

        :param image: Raw .dds image bytes.
        :param output_format: Target format e.g. 'webp' or 'png'.
        :return: Converted image bytes.
        """
        try:
            with WandImage(blob=image, format="dds") as img:
                img.compression = "no"
                return img.make_blob(format=output_format)
        except WandException:
            logger.exception("Failed to convert image to %s", output_format)
            raise

    @staticmethod
    def convert_filename(filename: str, output_format: str = "webp") -> str:
        """
        Convert a .dds filename to its converted equivalent, with the
        extension following the actual output format.

        E.g. 'icon_FS25_Le_Mechet.dds' -> 'icon_FS25_Le_Mechet.webp'

        :param filename: The original filename from the XML.
        :param output_format: Target format e.g. 'webp' or 'png'.
        :return: Filename with the output format's extension.
        """
        stem = filename.rsplit(".", 1)[0]
        return f"{stem}.{output_format}"

    @staticmethod
    def from_grle(grle_bytes: bytes) -> bytes:
        """
        Convert a Farming Simulator .grle bitmask file to a .png image.

        :param grle_bytes: Raw .grle file bytes.
        :return: Converted PNG image bytes.
        :raises ValueError: If the GRLE header is invalid.
        """
        image = ImageConverterService._decode_grle(grle_bytes)

        buffer = BytesIO()
        image.save(buffer, format="png")
        return buffer.getvalue()

    @staticmethod
    def _parse_grle_header(data: bytes) -> GrleHeader:
        """
        Validate a GRLE header and return its image dimensions.

        :param data: Raw .grle file bytes.
        :return: Parsed GrleHeader.
        :raises ValueError: If the magic bytes or channel count are invalid.
        """
        if len(data) < GRLE_HEADER_SIZE or data[:4] != GRLE_MAGIC:
            raise ValueError("Not a GRLE file (missing 'GRLE' magic bytes)")

        version = struct.unpack_from("<H", data, 4)[0]
        if version != GRLE_SUPPORTED_VERSION:
            logger.warning(
                "Unexpected GRLE version %d (expected %d)", version, GRLE_SUPPORTED_VERSION
            )

        channels = data[13]
        if channels != 1:
            raise ValueError(f"Unsupported channel count: {channels} (expected 1)")

        width = struct.unpack_from("<H", data, 6)[0] * GRLE_DIMENSION_SCALE
        height = struct.unpack_from("<H", data, 10)[0] * GRLE_DIMENSION_SCALE
        return GrleHeader(width, height)

    @staticmethod
    def _decode_pixel_stream(stream: bytes, expected_pixels: int) -> bytes:
        """
        Decode a GRLE RLE byte stream into raw grayscale pixel values.

        :param stream: The RLE-encoded bytes, starting at the padding byte.
        :param expected_pixels: Total pixel count the image should contain.
        :return: Raw grayscale pixel bytes, one byte per pixel.
        """

        reader = _RunLengthReader(stream, start_pos=1)  # skip the padding byte
        pixels = bytearray()

        for first, second in reader:
            if len(pixels) >= expected_pixels:
                break

            if first == second:
                run_length = reader.read_run_length()
                remaining = expected_pixels - len(pixels)
                pixels.extend([first] * min(run_length, remaining))
            else:
                pixels.append(first)
                reader.step_back()

        if len(pixels) < expected_pixels:
            logger.warning(...)
            pixels.extend([0] * (expected_pixels - len(pixels)))

        return bytes(pixels)

    @staticmethod
    def _decode_grle(data: bytes) -> Image.Image:
        """
        Decode a GRLE file's bytes into a Pillow grayscale image.

        :param data: Raw .grle file bytes.
        :return: Decoded grayscale image.
        """
        header = ImageConverterService._parse_grle_header(data)
        pixels = ImageConverterService._decode_pixel_stream(
            data[GRLE_HEADER_SIZE:], header.pixel_count
        )
        return Image.frombytes("L", (header.width, header.height), pixels)
