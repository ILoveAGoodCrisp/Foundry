"""Blender --background --factory-startup --python-exit-code 1 --python this_file.

Optional -- --source input.jms --output directory also checks a real BSP.
"""
from pathlib import Path
import sys, tempfile, json, argparse
from zipfile import ZipFile
from types import SimpleNamespace
from collections import Counter
import unittest
import bpy
from mathutils import Matrix
from math import pi

ROOT=Path(__file__).parent/'addons'
if not ROOT.exists():
    import os
    ROOT=Path(os.environ['FOUNDRY_TEST_ADDONS'])
sys.path.insert(0,str(ROOT))
wheels=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (ROOT/'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as archive:
        archive.extractall(wheels.name)
sys.path.insert(0,wheels.name)
from io_scene_foundry import props, utils
from io_scene_foundry.tools.importer import NWOImporter, JMSMaterialSlot
from io_scene_foundry.legacy.jms_importer import JMSImporter
from io_scene_foundry.legacy.jms_format import JMS, Node, Transform, Material, Vertex, Triangle
from io_scene_foundry.legacy.writers import write_jms
from io_scene_foundry.export.legacy import LegacyExportScene
from io_scene_foundry.export.virtual_geometry import VirtualScene, VirtualMesh
from io_scene_foundry.export.process import ExportScene
from io_scene_foundry.tools.asset_types import AssetType

props.register()
utils.get_project=lambda *a, **kw: SimpleNamespace(game='halo1',corinth=False)
bpy.context.scene.nwo.asset_type='scenario'

class Owner:
    scale_factor=1
    from_x_rot=0
    corinth=False
    game='halo1'
    target_game='halo1'
    scene_nwo=bpy.context.scene.nwo
    _apply_jms_material_props=NWOImporter._apply_jms_material_props
    mesh_and_material=NWOImporter.mesh_and_material
    def __init__(self):
        self.region_names=set()
        self.permutation_names=set()
    _ensure_region_entry=NWOImporter._ensure_region_entry
    _ensure_permutation_entry=NWOImporter._ensure_permutation_entry
    set_region=NWOImporter.set_region
    set_permutation=NWOImporter.set_permutation


def import_file(path, kind='auto', owner=None):
    importer=JMSImporter(owner or Owner(),path,kind)
    importer.build()
    return importer


def export_file(objects, path, scale=1, rotation=0):
    settings=SimpleNamespace(triangulate_quad_method='BEAUTY',triangulate_ngon_method='BEAUTY',
        export_structure=True,disable_automatic_suspension_computation=False,
        legacy_generate_checksum=True,legacy_file_checksum=0,legacy_maya_order=False,
        auto_precise=False)
    scene=VirtualScene(AssetType.SCENARIO,bpy.context.evaluated_depsgraph_get(),False,
        Path(path).parent,None,settings,1/30,'Automatic',rotation,False,False,
        SimpleNamespace(game='halo1',default_material=''),1,1,1,bpy.context)
    scene.regions={'default':0}; scene.global_materials={'default':0}
    exporter=LegacyExportScene.__new__(LegacyExportScene)
    exporter.virtual_scene=scene
    exporter.target_game=exporter.project_game='halo1'
    exporter.asset_type=AssetType.SCENARIO
    exporter.corinth=False; exporter.legacy_export=True; exporter.supports_bsp=True
    exporter.export_settings=settings; exporter.atten_scalar=1
    exporter.default_region='default'; exporter.reg_name='BSP'
    exporter.regions_set={'default'}; exporter.global_materials={'default'}
    exporter.warnings=[]; exporter.shader_name_cache={}; exporter.warned_shader_paths=set()
    exporter.jms_version=8200; exporter.bones=[]; exporter.bone_index={}; exporter.bone_parents={}
    exporter.to_halo_scale=1/scale; exporter.export_tag_types={'structure'}
    nodes=[]
    for ob in objects:
        if ob.type!='MESH': continue
        wrapped=utils.ExportObject()
        for name in ('name','type','nwo','data','parent','parent_type','parent_bone','matrix_world','material_slots','vertex_groups','modifiers'):
            setattr(wrapped,name,getattr(ob,name))
        wrapped.ob=ob
        kind=13 if ob.data.nwo.mesh_type.endswith('_portal') else 3
        halo_props={'bungie_mesh_type':kind}
        if ob.nwo.portal_ai_deafening:
            halo_props['bungie_mesh_portal_ai_deafening']=1
        mesh_props={}
        exporter._setup_mesh_level_props(wrapped,'default',mesh_props,kind,halo_props)
        halo_props.update(mesh_props)
        mesh=VirtualMesh(False,scene,[],wrapped,True,[],halo_props,False,[],tuple(ob.data.materials))
        if mesh.invalid: raise AssertionError('Invalid virtual mesh: '+ob.name)
        nodes.append(SimpleNamespace(name=ob.name,ob=wrapped,mesh=mesh,props=halo_props,
            region='default',permutation='default',matrix_world=Matrix.Rotation(-rotation,4,'Z') @ ob.matrix_world,
            negative_scaling=False,tag_type='structure'))
    asset=exporter.jms_asset(Path(path).stem,nodes,[],'structure')
    with Path(path).open('w',encoding='utf-8',newline='\n') as stream:
        write_jms(asset,stream)
    return JMS.from_file(path)


def fixture(path):
    # Each face has independent corners, as real legacy files commonly do.
    names=['+exactportal','+portal','+ladder stair%*^','+ladder stair%*','wall@',
           'wall!','wall%','+sky','+sky3','+seamsealer@']
    asset=JMS(name='flags',version=8200)
    asset.nodes=[Node('implied_root_node',-1,Transform((0,0,0,1),(0,0,0)))]
    asset.materials=[Material(n,'<none>') for n in names]
    asset.regions=['default']
    for i,name in enumerate(names):
        start=len(asset.vertices)
        for x,y in ((0,0),(1,0),(0,1)):
            asset.vertices.append(Vertex((x+i*2,y,0),(0,0,1),((0,1),),((x,y),)))
        asset.triangles.append(Triangle(i,(start,start+1,start+2),0))
    with Path(path).open('w',encoding='utf-8') as stream: write_jms(asset,stream)
    return asset


def room_fixture(path):
    """Sealed three-cell BSP for real Halo Tool validation."""
    from mathutils import Vector
    asset=JMS(name='room',version=8200)
    asset.nodes=[Node('implied_root_node',-1,Transform((0,0,0,1),(0,0,0)))]
    asset.materials=[Material(n,'<none>') for n in ('+sky','+exactportal','+portal','+ladder stair%*^','wall@','wall!')]
    asset.regions=['default']
    def quad(points, material):
        normal=(Vector(points[1])-Vector(points[0])).cross(Vector(points[2])-Vector(points[0])).normalized()
        start=len(asset.vertices)
        for i,co in enumerate(points):
            asset.vertices.append(Vertex(co,tuple(normal),((0,1),),(((i==1 or i==2)*1.,(i>=2)*1.),)))
        for indices in ((0,1,2),(0,2,3)):
            asset.triangles.append(Triangle(material,tuple(start+i for i in indices),0))
    cuts=(-400,-100,100,400)
    for a,b in zip(cuts,cuts[1:]):
        quad(((a,-200,0),(b,-200,0),(b,200,0),(a,200,0)),0)
        quad(((a,-200,400),(a,200,400),(b,200,400),(b,-200,400)),0)
        quad(((a,-200,0),(a,-200,400),(b,-200,400),(b,-200,0)),0)
        quad(((a,200,0),(b,200,0),(b,200,400),(a,200,400)),0)
    quad(((-400,-200,0),(-400,200,0),(-400,200,400),(-400,-200,400)),0)
    quad(((400,-200,0),(400,-200,400),(400,200,400),(400,200,0)),0)
    for x,mat in ((-100,1),(100,2)):
        quad(((x,-200,0),(x,200,0),(x,200,400),(x,-200,400)),mat)
    quad(((-350,-150,5),(-250,-150,5),(-250,150,50),(-350,150,50)),3)
    # Ordinary collision-only obstacles must be closed solids for Tool.
    quad(((200,-100,5),(200,100,5),(250,100,5),(250,-100,5)),4)
    quad(((200,-100,30),(250,-100,30),(250,100,30),(200,100,30)),4)
    quad(((200,-100,5),(250,-100,5),(250,-100,30),(200,-100,30)),4)
    quad(((200,100,5),(200,100,30),(250,100,30),(250,100,5)),4)
    quad(((200,-100,5),(200,-100,30),(200,100,30),(200,100,5)),4)
    quad(((250,-100,5),(250,100,5),(250,100,30),(250,-100,30)),4)
    quad(((280,-100,10),(330,-100,10),(330,100,30),(280,100,30)),5)
    with Path(path).open('w') as stream: write_jms(asset,stream)
    return asset


def face_modes(importer):
    counts=Counter()
    for ob in importer.objects:
        if ob.type != 'MESH': continue
        for prop in ob.data.nwo.face_props:
            if prop.type=='face_mode': counts[prop.face_mode]+=prop.face_count
            elif prop.type=='ladder': counts['ladder']+=prop.face_count
    return counts


def signatures(asset):
    # Compare semantics and geometry independently of vertex/material ordering.
    return Counter((asset.materials[t.material].name,
        tuple(tuple(round(c,5) for c in asset.vertices[i].position) for i in t.vertices),
        tuple(tuple(round(c,5) for c in asset.vertices[i].uvs[0]) for i in t.vertices))
        for t in asset.triangles)

def compare_geometry(first, second):
    from mathutils.kdtree import KDTree
    by_material={}
    for asset in (first,second):
        counts=Counter(asset.materials[t.material].name for t in asset.triangles)
        if asset is first: expected=counts
        else: assert counts==expected, 'Material semantics changed on re-export'
    for name in expected:
        source=[t for t in first.triangles if first.materials[t.material].name==name]
        target=[t for t in second.triangles if second.materials[t.material].name==name]
        tree=KDTree(len(source))
        for index,t in enumerate(source):
            tree.insert(tuple(sum(first.vertices[v].position[c] for v in t.vertices)/3 for c in range(3)),index)
        tree.balance(); used=set()
        # H1 portal stabilization occurs in float64 after Blender's float32
        # storage. Permit only its documented bounded displacement on portals.
        tolerance=.025 if name.startswith(('+portal','+exactportal')) else .00001
        for t in target:
            center=tuple(sum(second.vertices[v].position[c] for v in t.vertices)/3 for c in range(3))
            candidates=tree.find_range(center,tolerance)
            for _,index,_ in candidates:
                if index in used: continue
                original=source[index]
                a=[first.vertices[i] for i in original.vertices]
                b=[second.vertices[i] for i in t.vertices]
                if all(abs(x-y)<=tolerance for av,bv in zip(a,b) for x,y in zip(av.position,bv.position)) and all(
                       abs(x-y)<=.00001 for av,bv in zip(a,b) for x,y in zip(av.uvs[0],bv.uvs[0])):
                    used.add(index); break
            else: raise AssertionError('Geometry or UVs changed: '+name)


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source.jms'; fixture(self.source)

    def test_import_and_reexport_preserve_face_semantics(self):
        imported=import_file(self.source)
        self.assertFalse(imported.is_model)
        portals=[o for o in imported.objects if o.type=='MESH' and o.data.nwo.mesh_type.endswith('_portal')]
        self.assertEqual(len(portals),2)
        self.assertEqual(sorted(o.nwo.portal_exact for o in portals),[False,True])
        counts=face_modes(imported)
        self.assertEqual(counts['sphere_collision_only'],2)
        self.assertEqual(counts['ladder'],1)
        self.assertEqual(counts['collision_only'],2)
        first=export_file(imported.objects,self.root/'first.jms')
        reimported=import_file(self.root/'first.jms')
        second=export_file(reimported.objects,self.root/'second.jms')
        self.assertEqual(signatures(first),signatures(second))
        self.assertEqual(face_modes(imported),face_modes(reimported))
        names={m.name for m in second.materials}
        self.assertIn('+exactportal',names)
        self.assertIn('+ladder stair*^',names)
        self.assertIn('+sky3',names)
        self.assertIn('+seamsealer@',names)

    def test_exact_portal_survives_material_replacement(self):
        imported=import_file(self.source)
        portal=next(o for o in imported.objects if o.nwo.portal_exact)
        portal.data.materials.clear(); portal.data.materials.append(bpy.data.materials.new('Portal display'))
        asset=export_file([portal],self.root/'portal.jms')
        self.assertEqual(asset.materials[0].name,'+exactportal')
        portal.nwo.portal_exact=False
        portal.data.materials.clear(); portal.data.materials.append(bpy.data.materials.get('+exactportal'))
        asset=export_file([portal],self.root/'ordinary_portal.jms')
        self.assertEqual(asset.materials[0].name,'+portal')

    def test_scaled_rotated_roundtrip(self):
        owner=Owner(); owner.scale_factor=.03048; owner.from_x_rot=pi/2
        imported=import_file(self.source,owner=owner)
        first=export_file(imported.objects,self.root/'scaled_first.jms',owner.scale_factor,owner.from_x_rot)
        reimported=import_file(self.root/'scaled_first.jms',owner=owner)
        second=export_file(reimported.objects,self.root/'scaled_second.jms',owner.scale_factor,owner.from_x_rot)
        compare_geometry(first,second)
        self.assertEqual(face_modes(imported),face_modes(reimported))

    def test_cleanup_preserves_unresolved_real_plus_shaders(self):
        imported=import_file(self.source)
        structure=next(o for o in imported.objects if o.type=='MESH' and o.data.nwo.mesh_type.endswith('_structure'))
        utils.consolidate_face_attributes(structure.data)
        counts=face_modes(imported)
        self.assertEqual(counts['sphere_collision_only'],2)
        self.assertEqual(counts['ladder'],1)
        self.assertEqual(JMSMaterialSlot.from_name('+ladder stair%*^').mesh_type,'default')

    def assert_bsp_collection(self, imported, name):
        self.assertEqual(imported.collection.nwo.type,'region')
        self.assertEqual(imported.collection.nwo.region,name)
        entry=bpy.context.scene.nwo.regions_table[name]
        self.assertEqual(entry.set_type,'SCENARIO')
        self.assertTrue(imported.objects)
        for ob in imported.objects:
            self.assertIn(imported.collection,ob.users_collection)
            self.assertEqual(ob.nwo.region_name,name)
        self.assertEqual(utils.ExportCollection(imported.collection).region,name)

    def test_jms_bsp_collection_uses_filename_for_all_objects(self):
        from io_scene_foundry.legacy.jms_format import Marker
        path=self.root/'a10e.jms'
        asset=fixture(path)
        asset.regions=['source_model_region']
        asset.markers=[Marker('marker',0,0,Transform((0,0,0,1),(0,0,0)),1)]
        with path.open('w') as stream: write_jms(asset,stream)
        owner=Owner()
        imported=import_file(path,owner=owner)
        self.assert_bsp_collection(imported,'a10e')
        self.assertNotIn('source_model_region',owner.region_names)
        self.assertTrue(any(o.type=='EMPTY' and not o.nwo.is_frame for o in imported.objects))
        self.assertTrue(any(o.nwo.is_frame for o in imported.objects))
        # Blender may suffix the display collection name on repeated imports;
        # the BSP identity must remain the filename, not a10e.001.
        again=import_file(path)
        self.assert_bsp_collection(again,'a10e')

    def test_ass_bsp_collection_includes_instances_and_markers(self):
        from io_scene_foundry.legacy import ass_format as ass
        from io_scene_foundry.legacy.ass_importer import ASSImporter
        from io_scene_foundry.legacy.writers import write_ass
        path=self.root/'ass_bsp.ass'
        asset=ass.ASS(materials=[ass.Material('wall','default source_model_region')])
        asset.geometries=[ass.Geometry('MESH',vertices=[
            Vertex((0,0,0),(0,0,1),(),((0,0,0),)),
            Vertex((1,0,0),(0,0,1),(),((1,0,0),)),
            Vertex((0,1,0),(0,0,1),(),((0,1,0),)),
        ],triangles=[Triangle(0,(0,1,2))])]
        asset.instances=[
            ass.Instance(-1,'frame_root',0,-1,0,ass.Transform(),ass.Transform()),
            ass.Instance(0,'mesh_a',1,0,0,ass.Transform(),ass.Transform()),
            ass.Instance(0,'mesh_b',2,0,0,ass.Transform(translation=(2,0,0)),ass.Transform()),
            ass.Instance(-1,'#marker',3,0,0,ass.Transform(),ass.Transform()),
        ]
        with path.open('w') as stream: write_ass(asset,stream)
        imported=ASSImporter(Owner(),path,'bsp')
        imported.build()
        self.assert_bsp_collection(imported,'ass_bsp')
        self.assertEqual(len([o for o in imported.objects if o.type=='MESH']),2)
        self.assertTrue(any(o.type=='EMPTY' and not o.nwo.is_frame for o in imported.objects))

    def test_model_regions_are_not_replaced_by_filename(self):
        path=self.root/'model.jms'
        asset=fixture(path); asset.nodes=[]; asset.regions=['model_region']
        for v in asset.vertices: v.influences=()
        with path.open('w') as stream: write_jms(asset,stream)
        imported=import_file(path,'model')
        self.assertEqual(imported.collection.nwo.type,'none')
        self.assertTrue(all(o.nwo.region_name=='model_region' for o in imported.objects))

    def test_auto_uses_context_and_explicit_choice(self):
        self.assertTrue(JMSImporter(Owner(),self.source,'model').is_model)
        # Structure without any special material still has an implied root.
        asset=JMS.from_file(self.source); asset.materials=[Material('wall','')]
        for t in asset.triangles: t.material=0
        with self.source.open('w') as stream: write_jms(asset,stream)
        self.assertFalse(JMSImporter(Owner(),self.source,'auto').is_model)
        owner=Owner(); owner.scene_nwo=SimpleNamespace(asset_type='model')
        self.assertTrue(JMSImporter(owner,self.source,'auto').is_model)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source'); parser.add_argument('--output'); parser.add_argument('--tool-fixture')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RoundTripTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise AssertionError('JMS round-trip regression failed')
    if args.source and not args.output:
        parser.error('--source requires --output')
    if args.source:
        output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
        original=import_file(args.source)
        first=export_file(original.objects,output/'a10e_first.jms')
        second_import=import_file(output/'a10e_first.jms')
        second=export_file(second_import.objects,output/'a10e_second.jms')
        compare_geometry(first,second)
        assert face_modes(original)==face_modes(second_import)
        print('REAL_BSP',json.dumps({'triangles':len(second.triangles),'properties':face_modes(second_import),
            'portals':sum(len(o.data.polygons) for o in second_import.objects if o.type=='MESH' and o.data.nwo.mesh_type.endswith('_portal'))}))




    if args.tool_fixture:
        output=Path(args.tool_fixture); output.mkdir(parents=True,exist_ok=True)
        room_fixture(output/'room_source.jms')
        original=import_file(output/'room_source.jms')
        first=export_file(original.objects,output/'room_first.jms')
        reimported=import_file(output/'room_first.jms')
        second=export_file(reimported.objects,output/'room_second.jms')
        assert signatures(first)==signatures(second)
        print('TOOL_FIXTURE',output)
