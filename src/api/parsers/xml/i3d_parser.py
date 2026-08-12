"""
Python module containing a parser for a .i3d XML file.
"""

from xml.etree.ElementTree import Element

from src.api.core.schema.mods.i3d import (
    I3dModel,
    InfoLayerGroupModel,
    InfoLayerModel,
    InfoLayerOptionModel,
)
from src.api.parsers.xml.base_parser import BaseXmlParser


class I3dParser(BaseXmlParser[I3dModel]):
    """
    Parses an .i3d file into an I3dModel.
    """

    valid_info_layers: set[str] = {
        "farmlands",
        "soilMap",
        "environment",
    }

    def parse(self, content: bytes) -> I3dModel:
        """
        Parse .i3d bytes into an I3dModel.

        :param content: (bytes) Raw bytes of the .i3d file from S3.
        :return: (I3dModel) A Parsed I3d file.
        """
        root = self._load(content)
        files = self._get_files(root)

        return I3dModel(
            info_layers=self._get_info_layers(root, files),
        )

    @staticmethod
    def _get_files(root: Element) -> dict[str, str]:
        """
        Get the fileIds and corresponding filename from an i3d file.

        :param root: (Element) The root element of the parsed .i3d file.
        :return: (dict) mapping fileId to its .grle filename.
        """
        files = {}
        for file in root.iter("File"):
            file_id = file.get("fileId")
            filename = file.get("filename")

            if not file_id or not filename:
                continue

            basename = filename.rsplit("/", 1)[-1]
            stem = basename.rsplit(".", 1)[0]
            files[file_id] = f"{stem}.grle"

        return files

    def _get_info_layers(self, root: Element, files: dict[str, str]) -> list[InfoLayerModel]:
        """
        Get info layers from an i3d file.

        :param root: (Element) The root element of the parsed .i3d file.
        :param files: (dict) A dict of files from the i3d file.
        :return: (list) of parsed InfoLayerModel entries.
        """
        valid_lower = {name.lower() for name in self.valid_info_layers}

        layers = []
        for element in root.iter("InfoLayer"):
            name = element.get("name", "")
            if name.lower() not in valid_lower:
                continue

            file_id = element.get("fileId")

            layers.append(
                InfoLayerModel(
                    layer_key=name,
                    i3d_file_id=file_id,
                    grle_filename=files.get(file_id, f"infoLayer_{name}.grle"),
                    groups=self._get_groups(element),
                )
            )

        return layers

    @staticmethod
    def _get_groups(info_layer_element: Element) -> list[InfoLayerGroupModel]:
        """
        Get groups from within an InfoLayer.

        :param info_layer_element: (Element) The <InfoLayer> element to search within.
        :return: (list) of parsed InfoLayerGroupModel entries.
        """
        groups = []
        for group_element in info_layer_element.findall("Group"):
            options = [
                InfoLayerOptionModel(value=int(option.get("value")), name=option.get("name"))
                for option in group_element.findall("Option")
                if option.get("value") is not None and option.get("name")
            ]

            groups.append(
                InfoLayerGroupModel(
                    name=group_element.get("name", ""),
                    first_channel=int(group_element.get("firstChannel", 0)),
                    num_channels=int(group_element.get("numChannels", 0)),
                    options=options,
                )
            )

        return groups
