"""Read asset assembly metadata without requiring Blender or Granny."""
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
import xml.etree.ElementTree as ET


@dataclass
class SidecarSource:
    reference: str
    content_name: str = ''
    content_type: str = ''
    object_type: str = ''
    object_name: str = ''
    network: dict[str, str] = field(default_factory=dict)
    output_tags: dict[str, str] = field(default_factory=dict)
    region: str | None = None
    permutation: str = 'default'
    lod: str = ''

    @property
    def rig_key(self):
        # Cinematic actor networks share a scene content but have separate rigs.
        return (self.object_name or self.content_name) if self.content_type == 'scene' else self.content_name

    @property
    def priority(self):
        return {'skeleton': 0, 'render_model': 1, 'model_animation_graph': 3}.get(self.object_type, 2)


@dataclass
class SidecarAsset:
    path: Path
    name: str
    asset_type: str
    sources: list[SidecarSource]
    regions: list[tuple[str, bool]]
    global_materials: list[str]
    output_tags: dict[str, str]
    aliases: list[SidecarSource]
    source_blend: str
    xml: str


def output_tags(element):
    return {tag.get('Type', ''): (tag.text or '').strip()
            for tag in element.findall('./OutputTagCollection/OutputTag')}


def read_sidecar(path):
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f'Invalid sidecar XML: {exc}') from exc
    for element in root.iter():
        element.tag = element.tag.rsplit('}', 1)[-1]
    asset = root.find('Asset')
    if root.tag != 'Metadata' or asset is None:
        raise ValueError(f'{path.name} is not an asset sidecar')
    name = asset.get('Name') or (path.parent.name if path.name.lower() == 'sidecar.xml' else path.name[:-len('.sidecar.xml')])
    asset_type = asset.get('Type', 'model').lower()
    if asset_type == 'model' and asset.get('Sky', '').lower() == 'true':
        asset_type = 'sky'
    if (root.findtext('./Header/AnimationOnly') or '').lower() == 'true':
        asset_type = 'animation'
    regions, materials = [], []
    for collection in root.findall('./FaceCollections/FaceCollection'):
        entries = sorted(collection.findall('.//FaceCollectionEntry'), key=lambda entry: int(entry.get('Index', '0')))
        table = collection.get('StringTable', '')
        if table == 'connected_geometry_regions_table':
            regions = [(entry.get('Name', 'default'), entry.get('Active', 'true').lower() == 'true') for entry in entries]
        elif table == 'connected_geometry_global_material_table':
            materials = [entry.get('Name', 'default') for entry in entries]
    sources, aliases, consumed = [], [], set()
    for content in root.findall('.//Content'):
        for obj in content.findall('./ContentObject'):
            for network in obj.findall('./ContentNetwork'):
                attributes = dict(network.attrib)
                region, permutation = None, attributes.get('Permutation') or attributes.get('Name') or 'default'
                kind = obj.get('Type', '')
                if kind in {'scenario_structure_bsp', 'structure_design'}:
                    region = attributes.get('Region') or (content.get('Name', 'default') if content.get('Type') in {'bsp', 'design'} else 'default')
                    network_name = attributes.get('Name', '')
                    shared = network_name.endswith('_shared')
                    if shared:
                        region = 'shared'
                    prefix = f'{name}_{"design" if kind == "structure_design" else "structure"}_{region}_'
                    if network_name.startswith(prefix):
                        permutation = network_name[len(prefix):]
                        if shared:
                            permutation = permutation.removesuffix('_shared')
                    else:
                        permutation = attributes.get('Permutation', 'default')
                metadata = dict(content_name=content.get('Name', name), content_type=content.get('Type', ''),
                                object_type=kind, object_name=obj.get('Name', ''), network=attributes,
                                output_tags=output_tags(obj), region=region, permutation=permutation,
                                lod=obj.get('LOD', ''))
                if attributes.get('Type', '').lower() in {'rename', 'copy'}:
                    aliases.append(SidecarSource('', **metadata))
                # Some external sidecars use InputFile for a GR2 directly.
                references = []
                for element in network.iter():
                    reference = (element.text or '').strip()
                    if reference.lower().endswith('.gr2'):
                        consumed.add(id(element))
                        if reference not in references:
                            references.append(reference)
                sources.extend(SidecarSource(reference, **metadata) for reference in references)
    # Retain references outside the usual network layout as well.
    for element in root.iter():
        reference = (element.text or '').strip()
        if id(element) not in consumed and reference.lower().endswith('.gr2'):
            sources.append(SidecarSource(reference, content_name=name))
    return SidecarAsset(path, name, asset_type, sources, regions, materials, output_tags(asset), aliases,
                        root.findtext('./Header/SourceBlend') or '', ET.tostring(root, encoding='unicode'))


def resolve_gr2_path(sidecar, reference, data_dir=None):
    """Resolve kit-data paths, local paths and references in moved asset folders."""
    sidecar = Path(sidecar).resolve()
    reference = reference.strip().replace('\\', '/')
    original = Path(reference)
    candidates = [original] if original.is_absolute() else []
    parts = list(PureWindowsPath(reference).parts)
    absolute = PureWindowsPath(reference).is_absolute() or original.is_absolute()
    # Relocate obsolete absolute paths through their original data-relative tail.
    if absolute:
        data_index = next((i for i, part in enumerate(parts) if part.lower() == 'data'), None)
        parts = parts[data_index + 1:] if data_index is not None else []
    if parts:
        relative = Path(*parts)
        inferred_data = next((parent for parent in sidecar.parents if parent.name.lower() == 'data'), None)
        if inferred_data is not None:
            candidates.append(inferred_data / relative)
        if data_dir:
            candidates.append(Path(data_dir) / relative)
        candidates.append(sidecar.parent / relative)
        # A copied asset may keep its former objects/.../asset prefix in XML.
        for i, part in enumerate(parts[:-1]):
            if part.lower() in {sidecar.parent.name.lower(), sidecar.name.lower().removesuffix('.sidecar.xml')}:
                candidates.append(sidecar.parent.joinpath(*parts[i + 1:]))
    for candidate in dict.fromkeys(candidates):
        if candidate.is_file():
            return candidate.resolve()
    return None


def animation_settings(attributes):
    kind = attributes.get('Type', 'Base').lower()
    blending = attributes.get('ModelAnimationOverlayBlending', '').lower()
    replacement = blending.startswith('replacement')
    return dict(
        animation_type='replacement' if replacement else kind if kind in {'base', 'overlay', 'world'} else 'base',
        animation_space='local' if blending.endswith('localspace') else 'object',
        pose_overlay=attributes.get('ModelAnimationOverlayType', '').lower() == 'pose',
        animation_movement_data={'none': 'none', 'xy': 'xy', 'xyyaw': 'xyyaw', 'xyzyaw': 'xyzyaw',
                                 'xyzfullrotation': 'full', 'xyzabsolute': 'full'}.get(attributes.get('ModelAnimationMovementData', 'None').lower(), 'none'),
        compression=attributes.get('Compression', 'Default'),
    )
