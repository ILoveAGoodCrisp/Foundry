"""Native model-animation-graph metadata used outside the legacy graph editor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .backend import TagDocument, TagReference
from .blender import BlenderTag

if TYPE_CHECKING:
    import blam_tags


@dataclass(frozen=True)
class AnimationGraphNode:
    name: str
    parent_index: int


class AnimationGraphTag(BlenderTag, TagDocument):
    """Read common graph metadata without starting ManagedBlam."""

    tag_ext = 'model_animation_graph'

    def _definitions(self) -> blam_tags.TagStruct:
        definitions = self.required_field(self.tag.root(), 'definitions').as_struct()
        if definitions is None:
            raise TypeError(f'{self.path}: definitions is not a structure')
        return definitions

    def animation_names(self, contains: str = '') -> list[str]:
        animations = self.block(self._definitions(), 'animations')
        names = [str(self.value(animation, 'name')) for animation in animations]
        if contains:
            return [name for name in names if contains in name]
        return names

    def nodes(self) -> list[AnimationGraphNode]:
        nodes = self.block(self._definitions(), 'skeleton nodes')
        return [AnimationGraphNode(
            name=str(self.value(node, 'name')),
            parent_index=int(self.value(node, 'parent node index')),
        ) for node in nodes]

    def get_nodes(self) -> list[str]:
        """Compatibility name for callers that only need skeleton ordering."""
        return [node.name for node in self.nodes()]

    def node_usages(self) -> dict[str, int]:
        usages: dict[str, int] = {}
        for element in self.block(self._definitions(), 'node usage'):
            usage = self.required_field(element, 'usage')
            options = usage.options()
            name = options.current_name if options is not None else None
            if name:
                usages[name] = int(self.value(element, 'node to use'))
        return usages

    def parent_graph(self) -> TagReference | None:
        return self.reference(self._definitions(), 'parent animation graph')

    def frame_event_list(self) -> TagReference | None:
        return self.reference(self._definitions(), 'imported events')
