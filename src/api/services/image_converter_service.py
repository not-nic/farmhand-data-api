"""
Python module containing an image conversion service, for handling image conversion
for farming simulator. Wand is used for .dds to .webp conversion, and then an additional
set of components to decode .grle info data into grayscale .png images as described below:

GRLE format:
    Header (20 bytes, little-endian):
        0-3   Magic "GRLE"
        4-5   Version (u16, always 1)
        6-7   Width / 256 (u16)
        8-9   Reserved
        10-11 Height / 256 (u16)
        12    Reserved
        13    Channels, i.e. bytes per pixel (1 or 2)
        14-15 Reserved
        16-19 Compressed data size (informational)

    GRLE data (from byte 20):
        - First byte is padding, skip it.
        - Each pixel occupies `channels` little-endian bytes: one byte for a
          single channel file, two for a map whose values exceed 255 (e.g. a
          farmland layer with more than 255 farmlands).
        - Read pixel pairs (a, b):
            a == b -> a run: read count pixels (each all-0xFF pixel adds its
                      maximum value, the first pixel below that maximum is
                      the remainder), emit (count + 2) copies.
            a != b -> emit one copy of a then back-up one pixel so b
                      becomes the next pair's first pixel.
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
GRLE_EXTENSION_BYTE = 0xFF  # an all-0xFF pixel in a count chain adds its maximum
GRLE_MAX_CHANNELS = 2  # a pixel is at most two bytes wide


class GrleHeader(NamedTuple):
    """
    Parsed dimensions and pixel width from a GRLE file's header.
    """

    width: int
    height: int
    bytes_per_pixel: int

    @property
    def pixel_count(self) -> int:
        """Total number of pixels described by this header."""
        return self.width * self.height

    @property
    def byte_count(self) -> int:
        """Total number of bytes the decoded pixel data should occupy."""
        return self.pixel_count * self.bytes_per_pixel


class _RunLengthReader:
    """
    Cursor over a GRLE RLE byte stream, reading one pixel of
    `bytes_per_pixel` little-endian bytes at a time.
    """

    def __init__(self, stream: bytes, bytes_per_pixel: int, start_pos: int = 0) -> None:
        self._stream = stream
        self._bytes_per_pixel = bytes_per_pixel
        self._extension_value = int.from_bytes(
            bytes([GRLE_EXTENSION_BYTE] * bytes_per_pixel), "little"
        )
        self._pos = start_pos

    def _read_pixel(self) -> int:
        """
        Read and consume the next pixel's bytes as a little-endian value.
        """
        end = self._pos + self._bytes_per_pixel
        value = int.from_bytes(self._stream[self._pos : end], "little")
        self._pos = end
        return value

    def __iter__(self) -> "_RunLengthReader":
        return self

    def __next__(self) -> tuple[int, int]:
        """
        Read and consume the next pixel pair, or stop if none remain.
        """
        if self._pos + 2 * self._bytes_per_pixel > len(self._stream):
            raise StopIteration

        return self._read_pixel(), self._read_pixel()

    def step_back(self) -> None:
        """
        Rewind by one pixel, used when a 'pair' turns out to be a transition.
        """
        self._pos -= self._bytes_per_pixel

    def read_run_length(self) -> int:
        """
        Read a run length that may span multiple pixels: each pixel adds to
        the total, and a pixel whose bytes are all GRLE_EXTENSION_BYTE means
        "keep reading." GRLE_RUN_LENGTH_OFFSET is added at the end as the
        minimum run length.

        :return: (int) The decoded run length.
        """
        count: int = 0
        while self._pos + self._bytes_per_pixel <= len(self._stream):
            value = self._read_pixel()
            count += value
            if value != self._extension_value:
                break
        return count + GRLE_RUN_LENGTH_OFFSET


class ImageConverterService:
    """
    Python service to convert images. Wraps Wand/ImageMagick for .dds
    conversion and decodes .grle images into .png images.
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

        One byte per pixel decodes to a grayscale image. Two bytes per pixel
        decodes to RGB, with the low byte in red and the high byte in green,
        so the original value can be recovered as (red + green * 256).

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
        Validate a GRLE header and return its image dimensions and the number
        of bytes each pixel occupies.

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

        bytes_per_pixel = data[13]
        if not 1 <= bytes_per_pixel <= GRLE_MAX_CHANNELS:
            raise ValueError(f"Unsupported channel count: {bytes_per_pixel} (expected 1 or 2)")

        width = struct.unpack_from("<H", data, 6)[0] * GRLE_DIMENSION_SCALE
        height = struct.unpack_from("<H", data, 10)[0] * GRLE_DIMENSION_SCALE
        return GrleHeader(width, height, bytes_per_pixel)

    @staticmethod
    def _decode_pixel_stream(stream: bytes, header: GrleHeader) -> bytes:
        """
        Decode a GRLE RLE byte stream into raw pixel values, little-endian,
        with header.bytes_per_pixel bytes per pixel.

        :param stream: The RLE-encoded bytes, starting at the padding byte.
        :param header: Parsed header, giving the pixel width and total size.
        :return: Raw pixel bytes.
        """
        pixel_bytes = header.bytes_per_pixel
        expected_bytes = header.byte_count

        reader = _RunLengthReader(stream, pixel_bytes, start_pos=1)  # skip padding byte
        pixels = bytearray()

        for first, second in reader:
            if len(pixels) >= expected_bytes:
                break

            if first == second:
                run_length = reader.read_run_length()
                remaining = (expected_bytes - len(pixels)) // pixel_bytes
                pixels.extend(first.to_bytes(pixel_bytes, "little") * min(run_length, remaining))
            else:
                pixels.extend(first.to_bytes(pixel_bytes, "little"))
                reader.step_back()

        if len(pixels) < expected_bytes:
            logger.warning(
                "GRLE stream ended early: %d of %d bytes, padding with zeros",
                len(pixels),
                expected_bytes,
            )
            pixels.extend([0] * (expected_bytes - len(pixels)))

        return bytes(pixels)

    @staticmethod
    def _decode_grle(data: bytes) -> Image.Image:
        """
        Decode a GRLE file's bytes into a Pillow image: grayscale for one
        byte per pixel, RGB (low byte, high byte, 0) for two.

        :param data: Raw .grle file bytes.
        :return: Decoded image.
        """
        header = ImageConverterService._parse_grle_header(data)
        pixels = ImageConverterService._decode_pixel_stream(data[GRLE_HEADER_SIZE:], header)
        size = (header.width, header.height)

        if header.bytes_per_pixel == 1:
            return Image.frombytes("L", size, pixels)

        low_byte = Image.frombytes("L", size, pixels[0::2])
        high_byte = Image.frombytes("L", size, pixels[1::2])
        return Image.merge("RGB", (low_byte, high_byte, Image.new("L", size)))
