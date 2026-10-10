"""Authored Granny 2.8/2.9 standard descriptions for Foundry's LE64 profile.

No native data-tree blob, generated baseline JSON, or external Python library
is used at runtime. These are declarations, not asset or curve codecs.
"""
from .schema import SchemaMember as F, SchemaRegistry


STANDARD_DEFINITIONS = {
    'FileInfo': (
        F('ArtToolInfo', 2, reference='ArtToolInfo'), F('ExporterInfo', 2, reference='ExporterInfo'),
        F('FromFileName', 8), F('Textures', 4, reference='Texture'), F('Materials', 4, reference='Material'),
        F('Skeletons', 4, reference='Skeleton'), F('VertexDatas', 4, reference='VertexData'),
        F('TriTopologies', 4, reference='TriTopology'), F('Meshes', 4, reference='Mesh'),
        F('Models', 4, reference='Model'), F('TrackGroups', 4, reference='TrackGroup'),
        F('Animations', 4, reference='Animation'), F('ExtendedData', 5)),
    'ArtToolInfo': (F('FromArtToolName', 8), F('ArtToolMajorRevision', 19), F('ArtToolMinorRevision', 19),
        F('ArtToolPointerSize', 19), F('UnitsPerMeter', 10), F('Origin', 10, 3), F('RightVector', 10, 3),
        F('UpVector', 10, 3), F('BackVector', 10, 3), F('ExtendedData', 5)),
    'ExporterInfo': (F('ExporterName', 8), F('ExporterMajorRevision', 19), F('ExporterMinorRevision', 19),
        F('ExporterCustomization', 19), F('ExporterBuildNumber', 19), F('ExtendedData', 5)),
    'Texture': (F('FromFileName', 8), F('TextureType', 19), F('Width', 19), F('Height', 19),
        F('Encoding', 19), F('SubFormat', 19), F('Layout', 1, reference='PixelLayout'),
        F('Images', 3, reference='TextureImage'), F('ExtendedData', 5)),
    'PixelLayout': (F('BytesPerPixel', 19), F('ShiftForComponent', 19, 4), F('BitsForComponent', 19, 4)),
    'TextureImage': (F('MIPLevels', 3, reference='TextureMIPLevel'),),
    'TextureMIPLevel': (F('Stride', 19), F('PixelBytes', 3, reference='UInt8')),
    'UInt8': (F('UInt8', 12),),
    'Material': (F('Name', 8), F('Maps', 3, reference='MaterialMap'), F('Texture', 2, reference='Texture'), F('ExtendedData', 5)),
    'MaterialMap': (F('Usage', 8), F('Map', 2, reference='Material')),
    'Skeleton': (F('Name', 8), F('Bones', 3, reference='Bone'), F('LODType', 19), F('ExtendedData', 5)),
    'Bone': (F('Name', 8), F('ParentIndex', 19), F('Transform', 9), F('InverseWorldTransform', 10, 16),
        F('LODError', 10), F('ExtendedData', 5)),
    'VertexData': (F('Vertices', 7), F('VertexComponentNames', 3, reference='String'),
        F('VertexAnnotationSets', 3, reference='VertexAnnotationSet')),
    'String': (F('String', 8),),
    'VertexAnnotationSet': (F('Name', 8), F('VertexAnnotations', 7), F('IndicesMapFromVertexToAnnotation', 19),
        F('VertexAnnotationIndices', 3, reference='Int32')),
    'Int32': (F('Int32', 19),),
    'TriTopology': (F('Groups', 3, reference='TriMaterialGroup'), F('Indices', 3, reference='Int32'),
        F('Indices16', 3, reference='Int16'), F('VertexToVertexMap', 3, reference='Int32'),
        F('VertexToTriangleMap', 3, reference='Int32'), F('SideToNeighborMap', 3, reference='Int32'),
        F('BonesForTriangle', 3, reference='Int32'), F('TriangleToBoneIndices', 3, reference='Int32'),
        F('TriAnnotationSets', 3, reference='TriAnnotationSet')),
    'TriMaterialGroup': (F('MaterialIndex', 19), F('TriFirst', 19), F('TriCount', 19)),
    'Int16': (F('Int16', 15),),
    'TriAnnotationSet': (F('Name', 8), F('TriAnnotations', 7), F('IndicesMapFromTriToAnnotation', 19),
        F('TriAnnotationIndices', 3, reference='Int32')),
    'Mesh': (F('Name', 8), F('PrimaryVertexData', 2, reference='VertexData'),
        F('MorphTargets', 3, reference='MorphTarget'), F('PrimaryTopology', 2, reference='TriTopology'),
        F('MaterialBindings', 3, reference='MaterialBinding'), F('BoneBindings', 3, reference='BoneBinding'), F('ExtendedData', 5)),
    'MorphTarget': (F('ScalarName', 8), F('VertexData', 2, reference='VertexData'), F('DataIsDeltas', 19)),
    'MaterialBinding': (F('Material', 2, reference='Material'),),
    'BoneBinding': (F('BoneName', 8), F('OBBMin', 10, 3), F('OBBMax', 10, 3), F('TriangleIndices', 3, reference='Int32')),
    'Model': (F('Name', 8), F('Skeleton', 2, reference='Skeleton'), F('InitialPlacement', 9),
        F('MeshBindings', 3, reference='ModelMeshBinding'), F('ExtendedData', 5)),
    'ModelMeshBinding': (F('Mesh', 2, reference='Mesh'),),
    'TrackGroup': (F('Name', 8), F('VectorTracks', 3, reference='VectorTrack'),
        F('TransformTracks', 3, reference='TransformTrack'), F('TransformLODErrors', 3, reference='Real32'),
        F('TextTracks', 3, reference='TextTrack'), F('InitialPlacement', 9), F('AccumulationFlags', 19),
        F('LoopTranslation', 10, 3), F('PeriodicLoop', 2, reference='PeriodicLoop'), F('ExtendedData', 5)),
    'VectorTrack': (F('Name', 8), F('TrackKey', 20), F('Dimension', 19), F('ValueCurve', 1, reference='Curve2')),
    'Curve2': (F('CurveData', 5),),
    'TransformTrack': (F('Name', 8), F('Flags', 19), F('OrientationCurve', 1, reference='Curve2'),
        F('PositionCurve', 1, reference='Curve2'), F('ScaleShearCurve', 1, reference='Curve2')),
    'Real32': (F('Real32', 10),),
    'TextTrack': (F('Name', 8), F('Entries', 3, reference='TextTrackEntry')),
    'TextTrackEntry': (F('TimeStamp', 10), F('Text', 8)),
    'PeriodicLoop': (F('Radius', 10), F('dAngle', 10), F('dZ', 10), F('BasisX', 10, 3), F('BasisY', 10, 3), F('Axis', 10, 3)),
    'Animation': (F('Name', 8), F('Duration', 10), F('TimeStep', 10), F('Oversampling', 10),
        F('TrackGroups', 4, reference='TrackGroup'), F('DefaultLoopCount', 19), F('Flags', 19), F('ExtendedData', 5)),
    'Variant': (F('Variant', 5),),
    'UInt16': (F('UInt16', 16),),
    'UInt32': (F('UInt32', 20),),
    'Empty': (),
    'CurveDataHeader': (F('Format', 12), F('Degree', 12)),
}

CURVE_NAMES = (
    'DaKeyframes32f', 'DaK32fC32f', 'DaIdentity', 'DaConstant32f', 'D3Constant32f', 'D4Constant32f',
    'DaK16uC16u', 'DaK8uC8u', 'D4nK16uC15u', 'D4nK8uC7u', 'D3K16uC16u', 'D3K8uC8u',
    'D9I1K16uC16u', 'D9I3K16uC16u', 'D9I1K8uC8u', 'D9I3K8uC8u',
    'D3I1K32fC32f', 'D3I1K16uC16u', 'D3I1K8uC8u',
)


def curve_definitions():
    result = {}
    for name in CURVE_NAMES:
        header = F('CurveDataHeader_' + name, 1, reference='CurveDataHeader')
        if name in ('DaKeyframes32f', 'DaIdentity'):
            members = (F('Dimension', 15),)
            if name == 'DaKeyframes32f':
                members += (F('Controls', 3, reference='Real32'),)
        elif name in ('DaK32fC32f', 'DaConstant32f'):
            members = (F('Padding', 15),)
            if name == 'DaK32fC32f':
                members += (F('Knots', 3, reference='Real32'),)
            members += (F('Controls', 3, reference='Real32'),)
        elif name in ('D3Constant32f', 'D4Constant32f'):
            members = (F('Padding', 15), F('Controls', 10, 3 if name == 'D3Constant32f' else 4))
        elif name.startswith('D4n'):
            members = (F('ScaleOffsetTableEntries', 16), F('OneOverKnotScale', 10),
                       F('KnotsControls', 3, reference='UInt16' if '16u' in name else 'UInt8'))
        elif name.startswith('DaK'):
            members = (F('OneOverKnotScaleTrunc', 16), F('ControlScaleOffsets', 3, reference='Real32'),
                       F('KnotsControls', 3, reference='UInt16' if '16u' in name else 'UInt8'))
        else:
            element = 'Real32' if '32f' in name else 'UInt16' if '16u' in name else 'UInt8'
            members = (F('Padding', 16),) if element == 'Real32' else (F('OneOverKnotScaleTrunc', 16),)
            members += ((F('ControlScale', 10), F('ControlOffset', 10)) if name.startswith('D9I1')
                        else (F('ControlScales', 10, 3), F('ControlOffsets', 10, 3)))
            members += (F('KnotsControls', 3, reference=element),)
        result['CurveData' + name] = (header, *members)
    return result


def standard_registry():
    definitions = {**STANDARD_DEFINITIONS, **curve_definitions()}
    registry = SchemaRegistry()
    for name in definitions:
        registry.declare(name)
    for name, members in definitions.items():
        registry.define(name, members)
    # Validate forward references and packed/marshalling layouts now, before
    # any file allocation or recursive type-tree emission.
    for name in registry.names:
        registry.layout(name)
    return registry
