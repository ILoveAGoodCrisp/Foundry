"""JMS/ASS backend for Foundry's prepared VirtualScene.

The normal export path owns evaluation, filtering, triangulation, face overrides,
animation sampling and restoration. This adapter only converts that result into
the reusable legacy format models and writes files below the data asset folder.
"""
from collections import defaultdict
from copy import copy
from datetime import datetime
from getpass import getuser
from pathlib import Path
from tempfile import NamedTemporaryFile
import io
import os
import re
import xml.etree.ElementTree as ET

import bpy
from mathutils import Matrix, Quaternion, Vector

from .process import ExportScene
from .legacy_materials import material_variant
from .shader_collections import ShaderCollections
from ..legacy import jms_format as jms
from ..legacy import ass_format as ass
from ..legacy.writers import VERSIONS, TextWriter, hierarchy, node_checksum, write_jms, write_ass
from ..tags.backend import TagDocument
from ..tags.animation_graph import AnimationGraphTag
from ..tags.object import ObjectDocument
from ..tags.scenario import ScenarioDocument
from .. import utils


def filename(name):
    if not name or name in {'.', '..'} or any(c in name for c in '<>:"/\\|?*\r\n') or name.endswith((' ', '.')):
        raise ValueError(f'Invalid legacy export filename: {name!r}')
    return name


def transform(matrix, scale=1, inverse_rotation=False):
    rotation = matrix.to_quaternion()
    if inverse_rotation:
        rotation.invert()
    return jms.Transform((rotation.x, rotation.y, rotation.z, rotation.w), tuple(matrix.translation * scale))


def write_outputs(outputs):
    """Serialize and validate the whole batch before replacing any existing file."""
    staged = []
    try:
        for path, asset in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent,
                                    prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, path))
                if isinstance(asset, jms.JMS):
                    write_jms(asset, stream)
                elif isinstance(asset, ass.ASS):
                    write_ass(asset, stream)
                else:
                    stream.write(asset)
            if isinstance(asset, jms.JMS):
                jms.JMS.from_file(temporary)
            elif isinstance(asset, ass.ASS):
                ass.ASS.from_file(temporary)
        for temporary, path in staged:
            temporary.replace(path)
            print(f'--- Saved {path}')
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def ensure_asset_marker(asset_path: Path, data_dir: Path, scene_settings) -> Path:
    """Create the small sidecar used to identify an H1-ODST asset folder."""
    marker = asset_path / f'{asset_path.name}.sidecar.xml'
    scene_settings.sidecar_path = str(marker.relative_to(data_dir))
    if marker.is_file():
        return marker

    metadata = ET.Element('Metadata')
    header = ET.SubElement(metadata, 'Header')
    values = {
        'MainRev': '0',
        'PointRev': '6',
        'Description': 'Forged in Foundry',
        'Created': datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
        'By': getuser(),
        'DirectoryType': 'TAE.Shared.NWOAssetDirectory',
        'Schema': '1',
        'SourceBlend': utils.relative_path(bpy.data.filepath) if bpy.data.filepath else '',
        'BlenderVersion': bpy.app.version_string,
        'FoundryVersion': utils.get_version_string(),
        'AnimationOnly': str(scene_settings.asset_type == 'animation'),
    }
    for name, value in values.items():
        ET.SubElement(header, name).text = value
    ET.SubElement(metadata, 'FaceCollections')

    marker.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='wb', dir=marker.parent,
                            prefix=marker.name + '.', suffix='.tmp',
                            delete=False) as stream:
        temporary = Path(stream.name)
        ET.ElementTree(metadata).write(stream, encoding='utf-8',
                                       xml_declaration=True)
    try:
        temporary.replace(marker)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'--- Created asset marker: {marker}')
    return marker


class LegacyExportScene(ExportScene):
    legacy_export = True

    object_tag_types = (
        'biped', 'crate', 'creature', 'device_control', 'device_machine',
        'device_terminal', 'effect_scenery', 'equipment', 'giant', 'scenery',
        'vehicle', 'weapon',
    )

    def __init__(self, *args, **kwargs):
        self.original_cwd = Path.cwd()
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            os.chdir(self.original_cwd)
            raise
        self.target_game = utils.get_project(self.scene_settings.scene_project).game
        self.jms_version, self.ass_version, self.jma_version = VERSIONS[self.target_game]
        self.shader_collections = ShaderCollections(self.tags_dir, self.target_game)
        self.granny_textures = False

    def export_legacy(self, single_animation=False):
        self.bones = []
        skeleton = self.virtual_scene.skeleton_model
        if skeleton:
            self.bones = [b for b in skeleton.skeleton.bones if isinstance(b.bone, bpy.types.PoseBone)]
        self.bone_index = {b.name: i for i, b in enumerate(self.bones)}
        self.bone_world = {b.name: b.matrix_world for b in self.bones}
        self.bone_parents = {}
        if skeleton:
            for bone in self.bones:
                parent = skeleton.skeleton.bones[bone.parent_index] if bone.parent_index >= 0 else None
                self.bone_parents[bone.name] = self.bone_index.get(parent.name, -1) if parent else -1
        grouped = defaultdict(list)
        markers = []
        for node in self.virtual_scene.nodes.values():
            if node.invalid:
                continue
            if node.props.get('bungie_object_type') == 2:
                if node.ob.nwo.marker_type in {'_connected_geometry_marker_type_physics_constraint', '_connected_geometry_marker_type_game_instance'}:
                    raise ValueError(f'{node.name}: legacy export of constraints and tag references is not implemented yet')
                markers.append(node)
            if node.mesh is None or node.mesh.invalid:
                continue
            if self.limit_bsps_to_selection and node.region not in self.selected_bsps:
                continue
            if self.limit_perms_to_selection and node.permutation not in self.selected_permutations and node.props.get('bungie_mesh_type') != 11:
                continue
            if node.props.get('bungie_mesh_type') == 11 and self.ass_version is None:
                raise ValueError(f'{node.name}: H1 does not support ASS model instances')
            if node.tag_type not in self.export_tag_types:
                continue
            folder = {'design': 'structure', 'structure': 'structure', 'render': 'render',
                      'collision': 'collision', 'physics': 'physics'}.get(node.tag_type)
            if folder is None:
                raise ValueError(f'Unsupported legacy geometry role: {node.tag_type}')
            if self.target_game == 'halo1':
                # H1 Tool scans ``models`` for render geometry and ``physics``
                # for the JMS used by both collision-geometry and physics.
                folder = {'render': 'models', 'collision': 'physics',
                          'physics': 'physics'}.get(folder, folder)
            name = node.region if folder == 'structure' else node.permutation or 'default'
            if node.tag_type == 'design':
                name += '_design'
            if node.props.get('bungie_mesh_type') == 11:
                nwo = node.ob.nwo
                listed = {p.name for p in nwo.marker_permutations}
                permutations = [p for p in self.permutations if not nwo.marker_uses_regions or not listed or
                                ((p in listed) != (nwo.marker_permutation_type == 'exclude'))]
                for permutation in permutations:
                    if self.limit_perms_to_selection and permutation not in self.selected_permutations:
                        continue
                    variant = copy(node)
                    variant.permutation = permutation
                    grouped[(folder, filename(permutation))].append(variant)
            else:
                grouped[(folder, filename(name))].append(node)
        outputs = []
        if not single_animation:
            if not grouped and ((self.bones and 'skeleton' in self.export_tag_types) or
                                (markers and 'markers' in self.export_tag_types)):
                grouped[('models' if self.target_game == 'halo1' else 'render',
                         'default')] = []
            for (folder, name), nodes in grouped.items():
                use_ass = self.ass_version is not None and (folder == 'structure' or
                    (folder == 'render' and any(n.props.get('bungie_mesh_type') == 11 for n in nodes)))
                asset = self.ass_asset(name, nodes, markers if folder == 'render' else ()) if use_ass else self.jms_asset(name, nodes, markers, folder)
                outputs.append((Path(self.asset_path, folder, name + ('.ass' if use_ass else '.jms')), asset))
        for animation in self.virtual_scene.animations:
            if hasattr(animation, 'legacy_tracks'):
                outputs.append((Path(self.asset_path, 'animations', filename(animation.name.replace(':', ' ')) + self.animation_extension(animation)), self.jma_text(animation)))
        if self.external_animations:
            raise ValueError('Legacy export of external animation files is not implemented; open their source asset to export JMA')
        if self.animation_composites:
            raise ValueError('JMA cannot encode animation composites; export the individual source animations')
        if not outputs:
            raise ValueError('No JMS, ASS or JMA data matched the export selection')
        if len({str(path).casefold() for path, _ in outputs}) != len(outputs):
            raise ValueError('Legacy output names collide; rename the affected BSP, permutation or animation')
        if self.shader_collections.dirty:
            outputs.append((self.shader_collections.path, self.shader_collections.text()))
        write_outputs(outputs)

    def write_tags(self, single_animation=False):
        """Compile legacy model sources, then update object tags natively."""
        supported_asset_types = {'MODEL', 'SKY', 'ANIMATION', 'SINGLE_ANIMATION'}
        if self.target_game in {'halo1', 'halo2'}:
            supported_asset_types.add('SCENARIO')
        if self.asset_type.name not in supported_asset_types:
            raise ValueError(
                f'Legacy tag writing is not implemented for {self.asset_type.name.lower()} assets')

        print("\n\nWriting Tags")
        print("-----------------------------------------------------------------------\n")
        animation_only = single_animation or self.asset_type.name in {
            'ANIMATION', 'SINGLE_ANIMATION'}
        halo1_tool_options = {}
        if self.target_game == 'halo1':
            # H1 has no usable tool_fast equivalent for these imports.
            halo1_tool_options = {'force_tool': True}
        if self.asset_type.name == 'SCENARIO':
            structure_dir = Path(self.asset_path, 'structure')
            structure_sources = sorted(
                path for path in structure_dir.iterdir()
                if path.is_file() and path.suffix.lower() in {'.jms', '.ass'}
                and not path.stem.endswith('_design')
            ) if structure_dir.is_dir() else []
            if not structure_sources:
                raise FileNotFoundError(
                    f'No structure sources were found in {structure_dir}')
            if self.target_game == 'halo1':
                self.ensure_halo1_shaders(
                    structure_sources, 'shader_environment')
            for source in structure_sources:
                utils.run_tool(
                    ['structure', self.asset_path_relative, source.stem],
                    event_level=self.export_settings.event_level,
                    **halo1_tool_options,
                )
            self.write_classic_scenario_tag(structure_sources)
            return
        if not animation_only:
            if self.target_game == 'halo1':
                models = Path(self.asset_path, 'models')
                physics = Path(self.asset_path, 'physics')
                model_sources = sorted(models.glob('*.jms')) if models.is_dir() else []
                if model_sources:
                    self.ensure_halo1_shaders(model_sources, 'shader_model')
                    utils.run_tool(['model', self.asset_path_relative],
                                   event_level=self.export_settings.event_level,
                                   **halo1_tool_options)
                if physics.is_dir() and any(physics.glob('*.jms')):
                    for command in ('collision-geometry', 'physics'):
                        utils.run_tool([command, self.asset_path_relative],
                                       event_level=self.export_settings.event_level,
                                       **halo1_tool_options)
            else:
                command = ('bulk-import-model-folder'
                           if self.target_game == 'halo2' or self.export_settings.lightmap_structure
                           else 'bulk-import-model-folder-draft')
                utils.run_tool([command, self.asset_path_relative],
                               event_level=self.export_settings.event_level)

        animation_dir = Path(self.asset_path, 'animations')
        has_animation_sources = (animation_dir.is_dir() and any(
            path.is_file() and path.suffix.lower().startswith('.jm')
            for path in animation_dir.iterdir()))
        if animation_only or (self.export_settings.export_animations != 'NONE'
                              and has_animation_sources):
            command = 'animations' if self.target_game == 'halo1' else 'model-animations'
            utils.run_tool([command, self.asset_path_relative],
                           event_level=self.export_settings.event_level,
                           **halo1_tool_options)
            self.write_classic_animation_events()
        if self.asset_type.name in {'MODEL', 'SKY'}:
            self.write_object_tags()

    def ensure_halo1_shaders(self, source_paths: list[Path], shader_type: str) -> None:
        """Create unresolved H1 shaders before Tool can open its console prompt."""
        shader_root = Path(self.tags_dir, self.asset_path_relative)
        existing = {
            path.stem.casefold()
            for path in shader_root.rglob('*')
            if path.is_file() and path.suffix.lower().startswith('.shader')
        } if shader_root.is_dir() else set()
        for source in source_paths:
            for material in jms.JMS.from_file(source).materials:
                # H1 Tool does not treat the later precise-position `)`
                # marker as a material suffix, so preserve it in the lookup name.
                name = re.sub(
                    r'\b(?:lm|lp|hl|ds|pf|lt|to|at|ro):\S+',
                    '',
                    material.name,
                ).strip().rstrip("%#?!@*$^-&=.;><|~({]}[' ")
                if not name or name.startswith('+') or name.casefold() in existing:
                    continue
                name = filename(name)
                destination = Path(
                    self.tags_dir, self.asset_path_relative, name + '.' + shader_type
                )
                with TagDocument(
                    destination,
                    tags_root=self.tags_dir,
                    game='halo1',
                ):
                    pass
                existing.add(name.casefold())
                print(f'--- Created {destination}')

    def write_object_tags(self):
        """Create selected high-level object tags through blam-tags."""
        model_path = Path(self.tags_dir, self.asset_path_relative,
                          self.asset_name).with_suffix(
                              '.gbxmodel' if self.target_game == 'halo1' else '.model')
        if not model_path.is_file():
            raise FileNotFoundError(
                f'Model compilation did not create the expected tag: {model_path}')

        if (self.asset_type.name == 'SKY'
                and self.target_game in {'halo1', 'halo2'}):
            self.write_classic_sky_tag(model_path)
            return

        outputs = {'scenery'} if self.asset_type.name == 'SKY' else {
            tag_type for tag_type in self.object_tag_types
            if getattr(self.scene_settings, 'output_' + tag_type, False)
        }
        model_reference = utils.relative_path(model_path)
        for tag_type in sorted(outputs):
            destination = model_path.with_suffix('.' + tag_type)
            template = getattr(self.scene_settings, 'template_' + tag_type, '')
            if template and not destination.exists():
                template_path = Path(self.tags_dir, utils.relative_path(template))
                if template_path.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    utils.copy_file(template_path, destination)
                    print(f'--- Loaded {tag_type} tag template')
                else:
                    utils.print_warning(
                        f'Tag template does not exist: {template_path}')

            with ObjectDocument(destination, tags_root=self.tags_dir,
                                game=self.target_game) as tag:
                if self.target_game == 'halo1':
                    base = model_path.with_suffix('')
                    tag.set_halo1_model_paths(
                        model_reference,
                        utils.relative_path(base.with_suffix('.model_collision_geometry'))
                        if base.with_suffix('.model_collision_geometry').is_file() else None,
                        utils.relative_path(base.with_suffix('.model_animations'))
                        if base.with_suffix('.model_animations').is_file() else None,
                        utils.relative_path(base.with_suffix('.physics'))
                        if base.with_suffix('.physics').is_file() else None,
                    )
                else:
                    tag.set_model_tag_path(model_reference)
            print(f'--- Wrote {destination}')

    def write_classic_scenario_tag(self, structure_sources: list[Path]) -> None:
        """Create/update an H1/H2 scenario with its compiled BSP references."""
        destination = Path(
            self.tags_dir, self.asset_path_relative, self.asset_name
        ).with_suffix('.scenario')
        is_new = not destination.is_file()
        bsp_paths: list[Path] = []
        for source in structure_sources:
            bsp = Path(
                self.tags_dir, self.asset_path_relative, source.stem
            ).with_suffix('.scenario_structure_bsp')
            if not bsp.is_file():
                raise FileNotFoundError(
                    f'Structure compilation did not create the expected tag: {bsp}')
            bsp_paths.append(Path(utils.relative_path(bsp)))

        with ScenarioDocument(
            destination, tags_root=self.tags_dir, game=self.target_game
        ) as scenario:
            scenario.ensure_structure_bsps(bsp_paths)
            if is_new:
                scenario.create_default_profile()
                scenario.set_scenario_type(self.scene_settings.scenario_type)
        print(f'--- Wrote {destination}')

    def write_classic_sky_tag(self, model_path: Path) -> None:
        """Create/update the distinct H1/H2 sky tag reference layout."""
        destination = model_path.with_suffix('.sky')
        with TagDocument(destination, tags_root=self.tags_dir,
                         game=self.target_game) as tag:
            root = tag.tag.root()
            if self.target_game == 'halo1':
                tag.set_reference(root, 'model', utils.relative_path(model_path))
                animation = model_path.with_suffix('.model_animations')
            else:
                render_model = model_path.with_suffix('.render_model')
                if not render_model.is_file():
                    raise FileNotFoundError(
                        f'Sky compilation did not create the expected tag: {render_model}')
                tag.set_reference(root, 'render model',
                                  utils.relative_path(render_model))
                animation = model_path.with_suffix('.model_animation_graph')
            if animation.is_file():
                tag.set_reference(root, 'animation graph',
                                  utils.relative_path(animation))
        print(f'--- Wrote {destination}')

    def write_classic_animation_events(self) -> None:
        """Apply Blender events after Tool creates the classic animation tag."""
        extension = ('model_animations' if self.target_game == 'halo1'
                     else 'model_animation_graph')
        destination = Path(
            self.tags_dir, self.asset_path_relative, self.asset_name
        ).with_suffix('.' + extension)
        if not destination.is_file():
            raise FileNotFoundError(
                f'Animation compilation did not create the expected tag: {destination}')
        animations = {
            animation.name: animation.anim
            for animation in self.virtual_scene.animations
            if (hasattr(animation, 'legacy_tracks')
                or bool(animation.anim.animation_events))
        }
        if not animations:
            return
        with AnimationGraphTag(destination) as graph:
            count = graph.inline_events_from_blender(animations)
        print(f'--- Updated inline events for {count} animation(s) in {destination}')

    def create_event_objects(self, animation):
        unsupported = [
            event.event_type for event in animation.animation_events
            if event.event_type != '_connected_geometry_animation_event_type_frame'
        ]
        if unsupported:
            raise ValueError(
                f'{animation.name}: classic animation tags cannot store event types: '
                + ', '.join(sorted(set(unsupported))))
        # JMA has no event channel. Frame events are written into the compiled
        # tag after Tool finishes, using the original Blender animation data.
        return [], []

    def parent_index(self, node, implied_root=False):
        if node.mesh is not None and len(node.mesh.bone_bindings) == 1 and node.mesh.bone_bindings[0] in self.bone_index:
            return self.bone_index[node.mesh.bone_bindings[0]]
        ob = node.ob
        while ob is not None:
            if ob.parent_type == 'BONE' and ob.parent_bone in self.bone_index:
                return self.bone_index[ob.parent_bone]
            ob = ob.parent
        return 0 if self.bones or implied_root else -1

    def face_materials(self, node, asset, cache):
        mesh = node.mesh
        materials = {}
        regions = {v: k for k, v in self.virtual_scene.regions.items()}
        globals_ = {v: k for k, v in self.virtual_scene.global_materials.items()}
        for mat, _, (start, count) in mesh.groups:
            for face in range(int(start), int(start + count)):
                props = dict(node.props)
                for key, face_set in mesh.face_properties.items():
                    value = face_set.array[face]
                    props[key] = value.tolist() if hasattr(value, 'tolist') else value
                region = props.get('bungie_face_region', node.region or 'default')
                if not isinstance(region, str):
                    region = regions[region]
                gm = props.get('bungie_face_global_material', props.get('bungie_mesh_global_material', 'default'))
                if not isinstance(gm, str):
                    gm = globals_[gm]
                if self.supports_bsp:
                    gm = 'default'  # Pre-H4 BSP surface types are resolved from shaders.
                shader = (self.shader_collections.material_name(mat.shader_path)
                          if mat.shader_path not in {'override', 'shaders\\invalid'} else mat.name)
                name, lighting = material_variant(shader, props, gm,
                    asset.version if isinstance(asset, ass.ASS) else None,
                    self.target_game)
                if props.get('foundry_weather_polyhedron'):
                    name = '+weather'
                if node.tag_type in {'collision', 'physics'}:
                    name = gm  # Physics/collision material names are surface types, not display shaders.
                permutation = node.permutation or 'default'
                lod = (node.ob.nwo.mesh_lod
                       if self.target_game == 'halo2' and node.tag_type == 'render'
                       else '')
                definition = f'{permutation} {region}' + (f' {lod}' if lod else '')
                key = (name, definition, lighting)
                if key not in cache:
                    cache[key] = len(asset.materials)
                    asset.materials.append(ass.Material(name, definition, lighting) if isinstance(asset, ass.ASS)
                                           else jms.Material(name, definition, region, permutation, lod.lower()))
                materials[face] = cache[key], region
        return materials

    def vertices(self, node, matrix, weighted=True, implied_root=False):
        mesh = node.mesh
        normal_matrix = matrix.to_3x3().inverted().transposed()
        vertices = []
        for i, position in enumerate(mesh.positions):
            influences = []
            if weighted and mesh.bone_weights is not None:
                for index, weight in zip(mesh.bone_indices[i], mesh.bone_weights[i]):
                    if weight:
                        name = mesh.bone_bindings[int(index)]
                        if name not in self.bone_index:
                            raise ValueError(f'{node.name}: unknown skin bone {name}')
                        influences.append((self.bone_index[name], float(weight)))
                total = sum(w for _, w in influences)
                influences = [(b, w / total) for b, w in influences]
            elif weighted and (self.bones or implied_root):
                influences = [(self.parent_index(node, implied_root), 1)]
            normal = normal_matrix @ Vector(mesh.normals[i] if mesh.normals is not None else (0, 0, 1))
            normal.normalize()
            color = tuple(float(c) for c in mesh.vertex_colors[0][i][:3]) if mesh.vertex_colors else None
            vertices.append(jms.Vertex(tuple((matrix @ Vector(position)) * self.to_halo_scale), tuple(normal),
                tuple(influences), tuple(tuple(float(c) for c in uv[i][:2]) for uv in mesh.texcoords), color))
        return vertices

    def jms_asset(self, name, nodes, markers, folder):
        asset = jms.JMS(name=name, version=self.jms_version)
        if self.bones:
            for bone in self.bones:
                parent = self.bone_parents[bone.name]
                matrix = bone.matrix_world
                if asset.version < 8205 and parent != -1:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                asset.nodes.append(jms.Node(bone.name, parent, transform(matrix, self.to_halo_scale, asset.version < 8205)))
        else:
            asset.nodes.append(jms.Node(
                'implied_root_node', -1,
                jms.Transform((0, 0, 0, 1), (0, 0, 0))))
        asset.checksum = node_checksum(asset.nodes)
        cache = {}
        for node in nodes:
            materials = self.face_materials(node, asset, cache)
            if folder == 'physics' and self.jms_version >= 8206:
                if len({m[0] for m in materials.values()}) > 1:
                    raise ValueError(f'{node.name}: split physics shapes with different collision materials into separate objects')
                parent = self.parent_index(node, implied_root=True)
                matrix = node.matrix_world
                if parent != -1 and self.bones:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                # Convex records can represent arbitrary evaluated physics meshes.
                points = tuple(v.position for v in self.vertices(node, matrix, False))
                material = next(iter(materials.values()), (-1, 'default'))[0]
                asset.shapes.append(jms.Shape('convex', node.name, parent, material,
                    jms.Transform((0, 0, 0, 1), (0, 0, 0)), vertices=points))
                continue
            offset = len(asset.vertices)
            asset.vertices.extend(self.vertices(
                node, node.matrix_world, implied_root=True))
            for face, triangle in enumerate(node.mesh.indices.reshape((-1, 3))):
                material, region = materials[face]
                if region not in asset.regions:
                    asset.regions.append(region)
                indices = tuple(int(i) + offset for i in triangle)
                if node.negative_scaling:
                    indices = indices[0], indices[2], indices[1]
                asset.triangles.append(jms.Triangle(material, indices, asset.regions.index(region)))
        if folder in {'render', 'models'} and 'markers' in self.export_tag_types:
            for node in markers:
                nwo = node.ob.nwo
                permutations = {p.name for p in nwo.marker_permutations}
                if nwo.marker_uses_regions and permutations:
                    if (name in permutations) == (nwo.marker_permutation_type == 'exclude'):
                        continue
                parent = self.parent_index(node, implied_root=True)
                matrix = node.matrix_world
                if parent != -1 and self.bones:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                region = node.region or 'default'
                if region not in asset.regions:
                    asset.regions.append(region)
                marker_name = f'({name} {region}){node.name}' if nwo.marker_uses_regions and self.jms_version >= 8205 else node.name
                asset.markers.append(jms.Marker(marker_name, asset.regions.index(region) if nwo.marker_uses_regions else -1,
                    parent, transform(matrix, self.to_halo_scale), node.props.get('bungie_mesh_primitive_sphere_radius', 1)))
        return asset

    def ass_asset(self, name, nodes, markers=()):
        asset = ass.ASS(name=name, version=self.ass_version)
        cache, geometries = {}, {}
        asset.instances.append(ass.Instance(-1, 'frame', -1, -1, 0, ass.Transform(), ass.Transform()))
        for bone in self.bones:
            parent = self.bone_parents[bone.name]
            matrix = bone.matrix_world
            if parent != -1:
                matrix = self.bones[parent].matrix_world.inverted() @ matrix
            value = transform(matrix, self.to_halo_scale)
            asset.instances.append(ass.Instance(-1, bone.name, len(asset.instances), parent + 1,
                0, ass.Transform(value.rotation, value.translation), ass.Transform()))
        for node in nodes:
            materials = self.face_materials(node, asset, cache)
            matrix = node.matrix_world
            loc, rot, scale = matrix.decompose()
            uniform = max(scale) - min(scale) < 1e-5 and min(scale) > 0
            rebuilt = Matrix.LocRotScale(loc, rot, scale)
            uniform = uniform and max(abs(matrix[r][c] - rebuilt[r][c]) for r in range(4) for c in range(4)) < 1e-5
            local = ass.Transform((rot.x, rot.y, rot.z, rot.w), tuple(loc * self.to_halo_scale), tuple(scale)) if uniform else ass.Transform()
            key = (id(node.mesh), tuple(m[0] for m in materials.values()), node.negative_scaling)
            geometry_index = geometries.get(key) if uniform else None
            if geometry_index is None:
                geometry = ass.Geometry('MESH')
                geometry.vertices = self.vertices(node, Matrix.Identity(4) if uniform else matrix, bool(self.bones))
                palette = sorted({b for vertex in geometry.vertices for b, _ in vertex.influences})
                palette_map = {b: i for i, b in enumerate(palette)}
                for vertex in geometry.vertices:
                    vertex.influences = tuple((palette_map[b], weight) for b, weight in vertex.influences)
                geometry.node_indices = list(range(len(palette)))
                for face, triangle in enumerate(node.mesh.indices.reshape((-1, 3))):
                    indices = tuple(int(i) for i in triangle)
                    if node.negative_scaling:
                        indices = indices[0], indices[2], indices[1]
                    geometry.triangles.append(jms.Triangle(materials[face][0], indices))
                geometry_index = len(asset.geometries)
                asset.geometries.append(geometry)
                if uniform:
                    geometries[key] = geometry_index
                geometry_bones = tuple(b + 1 for b in palette)
            else:
                geometry_bones = next(i.bones for i in asset.instances if i.geometry == geometry_index)
            prefix = '%' if node.props.get('bungie_mesh_type') in {4, 11} else ''
            instance_name = prefix + node.name.lstrip('%')
            if node.props.get('foundry_weather_polyhedron'):
                if not instance_name.casefold().startswith('+weather'):
                    suffix = instance_name.rpartition(':')[2].lstrip('+')
                    instance_name = '+weather_' + (suffix or str(len(asset.instances)))
            asset.instances.append(ass.Instance(geometry_index, instance_name, len(asset.instances),
                0, 0, local, ass.Transform(), geometry_bones))
        if 'markers' in self.export_tag_types:
            for node in markers:
                nwo = node.ob.nwo
                permutations = {p.name for p in nwo.marker_permutations}
                if nwo.marker_uses_regions and permutations and (name in permutations) == (nwo.marker_permutation_type == 'exclude'):
                    continue
                parent = self.parent_index(node)
                matrix = node.matrix_world
                if parent != -1:
                    matrix = self.bones[parent].matrix_world.inverted() @ matrix
                value = transform(matrix, self.to_halo_scale)
                marker_name = f'#({name} {node.region}){node.name}' if nwo.marker_uses_regions else '#' + node.name
                asset.instances.append(ass.Instance(-1, marker_name, len(asset.instances), parent + 1,
                    0, ass.Transform(value.rotation, value.translation), ass.Transform()))
        return asset

    @staticmethod
    def animation_extension(animation):
        if animation.overlay:
            return '.jmo'
        if animation.animation_type == 'replacement':
            return '.jmr'
        return {'none': '.jmm', 'xy': '.jma', 'xyyaw': '.jmt', 'xyzyaw': '.jmz'}.get(animation.movement, '.jma')

    def jma_text(self, animation):
        tracks = {name: (positions, rotations, scales) for name, positions, rotations, scales in animation.legacy_tracks}
        if not self.bones or set(self.bone_index) - tracks.keys():
            raise ValueError(f'{animation.name}: animation and exported skeleton do not match')
        stream = io.StringIO()
        w = TextWriter(stream)
        nodes = hierarchy([jms.Node(b.name, self.bone_parents[b.name], jms.Transform((0, 0, 0, 1), (0, 0, 0))) for b in self.bones])
        w.line(self.jma_version)
        if self.jma_version >= 16394:
            w.line(node_checksum(nodes))
        for value in (animation.frame_count, round(1 / self.virtual_scene.time_step), 1, self.asset_name, len(self.bones)):
            w.line(value)
        if self.jma_version < 16394:
            w.line(node_checksum(nodes))
        for node in nodes:
            w.line(node.name)
            if self.jma_version >= 16394:
                w.line(node.parent)
            else:
                w.line(node.child)
                w.line(node.sibling)
        for frame in range(animation.frame_count):
            world = {}
            for bone in self.bones:
                positions, rotations, scales = tracks[bone.name]
                scale = [scales[frame * 9 + i] for i in (0, 4, 8)]
                if max(scale) - min(scale) > 1e-5:
                    raise ValueError(f'{animation.name}: JMA cannot represent nonuniform scale on {bone.name}')
                x, y, z, q = rotations[frame * 4:frame * 4 + 4]
                matrix = Matrix.LocRotScale(Vector(positions[frame * 3:frame * 3 + 3]), Quaternion((q, x, y, z)), Vector(scale))
                parent = self.bone_parents[bone.name]
                world[bone.name] = world[self.bones[parent].name] @ matrix if parent != -1 else matrix
                if self.jma_version >= 16394:
                    matrix = world[bone.name]
                value = transform(matrix, self.to_halo_scale, self.jma_version <= 16394)
                w.vector(value.translation)
                w.vector(value.rotation)
                w.vector((matrix.to_scale()[0],))
        if self.jma_version >= 16395:
            w.line(0)  # No separate biped-controller track.
        return stream.getvalue()


def export_legacy_asset(context, asset_name, asset_path, scene_settings, export_settings, single_animation, collection_view_layer=None):
    project = utils.get_project(scene_settings.scene_project)
    if not project or project.game not in VERSIONS:
        raise ValueError('JMS/ASS export requires an H1, H2, H3 or ODST project')
    if scene_settings.asset_type not in {'model', 'sky', 'scenario', 'prefab', 'particle_model', 'decorator_set', 'animation', 'single_animation', 'multi_model', 'multi_prefab'}:
        raise ValueError(f'JMS/ASS export does not support {scene_settings.asset_type} assets')
    write_intermediates = export_settings.export_mode in {'FULL', 'GRANNY'}
    write_tags = export_settings.export_mode in {'FULL', 'TAGS'}
    if not asset_path and single_animation:
        asset_path = str(Path(bpy.data.filepath).parent.parent)
    path = Path(asset_path).resolve()
    # Keep tag names and paths tied to the selected legacy asset folder even if
    # an operator entered with a stale ExportHelper filename.
    asset_name = path.name
    data = Path(utils.get_data_path()).resolve()
    if not path.is_relative_to(data) or path == data:
        raise ValueError('Legacy exports must be inside an asset folder below the project data directory')
    ensure_asset_marker(path, data, scene_settings)
    export = LegacyExportScene(context, '', '', scene_settings.asset_type, asset_name, str(path), False,
                               export_settings, scene_settings, context.scene)
    export.new_scene('default')
    try:
        export.ready_scene(collection_view_layer)
        export.get_initial_export_objects()
        export.map_halo_properties()
        if write_intermediates:
            # Legacy export uses the prepared bone order because its tags use the older layout.
            export.create_virtual_tree()
            export.sample_animations(single_animation)
            export.export_legacy(single_animation)
            export.report_warnings()
    finally:
        try:
            export.restore_scene()
        finally:
            os.chdir(export.original_cwd)

    if write_tags:
        try:
            # H1 uses model_animations and distinct object references rather
            # than the H2+ model/animation-graph post-processing layout.
            if project.game != 'halo1':
                export.preprocess_tags()
            export.write_tags(single_animation)
            if project.game != 'halo1':
                export.postprocess_tags()
        finally:
            os.chdir(export.original_cwd)
