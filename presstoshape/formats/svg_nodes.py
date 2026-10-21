"""Elements of an SVG document as selector nodes (formats/css_selectors.py), with parents and sibling positions
worked out on first use: documents without structural selectors never pay for them."""

import xml.etree.ElementTree as ET

from presstoshape.formats.svg_names import SVG_PREFIX

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_PREFIXED = {"xlink:href": "{http://www.w3.org/1999/xlink}href", "xml:lang": XML_LANG}


class Nodes:
    def __init__(self, root: ET.Element) -> None:
        self._root = root
        self._info: dict[ET.Element, tuple[ET.Element, int, int]] | None = None
        self._cache: dict[ET.Element, "SvgNode"] = {}

    def node(self, element: ET.Element) -> "SvgNode":
        node = self._cache.get(element)
        if node is None:
            node = self._cache[element] = SvgNode(self, element)
        return node

    def position(self, element: ET.Element) -> tuple[ET.Element, int, int] | None:
        """(parent, index among its element children, number of siblings including the element itself)."""
        if self._info is None:
            self._info = {}
            for parent in self._root.iter():
                count = len(parent)
                for index, child in enumerate(parent):
                    self._info[child] = (parent, index, count)
        return self._info.get(element)


class SvgNode:
    def __init__(self, nodes: Nodes, element: ET.Element) -> None:
        self._nodes = nodes
        self.element = element
        tag = element.tag
        self.tag: str | None = tag[len(SVG_PREFIX) :] if isinstance(tag, str) and tag.startswith(SVG_PREFIX) else None
        self.id = element.get("id")
        self.classes = frozenset(element.get("class", "").split())

    def attribute(self, name: str) -> str | None:
        return self.element.get(_PREFIXED.get(name, name))

    @property
    def parent(self) -> "SvgNode | None":
        position = self._nodes.position(self.element)
        return self._nodes.node(position[0]) if position else None

    @property
    def previous_sibling(self) -> "SvgNode | None":
        position = self._nodes.position(self.element)
        return self._nodes.node(position[0][position[1] - 1]) if position and position[1] > 0 else None

    @property
    def index(self) -> int:
        position = self._nodes.position(self.element)
        return position[1] if position else 0

    @property
    def sibling_count(self) -> int:
        position = self._nodes.position(self.element)
        return position[2] if position else 1

    @property
    def language(self) -> str | None:
        node: SvgNode | None = self
        while node is not None:
            language = node.element.get(XML_LANG) or node.element.get("lang")
            if language:
                return language
            node = node.parent
        return None
