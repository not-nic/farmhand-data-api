"""
Python module containing an image conversion service, for handling implementation
with wand to convert .dds to .webp.
"""

from wand.exceptions import WandException
from wand.image import Image

from src.api.core.logger import logger


class ImageConverterService:
    """
    Python service to convert images. Wraps Wand/ImageMagick so callers
    never need to know which library performs the conversion.
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
            with Image(blob=image, format="dds") as img:
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
