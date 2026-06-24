"""
Python module for creating adapters used in the farmhand-data-api.
"""

import io
from typing import Iterator


class IteratorAsFileObj(io.RawIOBase):
    """
    Adapts a bytes iterator into a file-like object compatible with
    boto3's upload_fileobj and io.BufferedReader.
    """

    def __init__(self, iterator: Iterator[bytes]) -> None:
        """
        :param iterator: An iterator yielding bytes chunks to be read sequentially.
        """
        self._iterator = iterator
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, b: bytearray) -> int:
        """
        Read up to len(b) bytes into b, buffering any remainder for the next call.

        :param b: The buffer to read into.
        :return: The number of bytes read, or 0 at the end of stream.
        """
        size = len(b)

        while len(self._buffer) < size:
            try:
                self._buffer += next(self._iterator)
            except StopIteration:
                break

        chunk, self._buffer = self._buffer[:size], self._buffer[size:]
        n = len(chunk)
        b[:n] = chunk
        return n
