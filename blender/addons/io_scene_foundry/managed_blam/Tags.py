

# Dummy classes for the ManagedBlam Tags namespace. This is to enable easier use of ManagedBlam through python

from dataclasses import dataclass
from enum import Enum
from ..managed_blam.Game import GameColor, GamePoint2d

# Extras that we need

class Bitmap: pass 
class e_tag_template_help_type: pass
class StringBuilder: pass
class e_tag_field: pass
class s_string_list_definition: pass

# Game Maths

class GamePoint3d:
    Z: float
    def __init__(self):
        pass
    def __init__(self, x: float, y: float, z: float):
        pass
    def Set(self, x: float, y: float, z: float) -> None:
        """Sets the xyz"""
    def ToString(self) -> str:
        """Returns the GamePoint3d as a string"""
        
class GameQuaternion:
    V: float
    W: float
    def __init__(self):
        pass
    def __init__(self, w: float, x: float, y: float, z: float):
        pass
    def Set(self, w: float, x: float, y: float, z: float) -> None:
        """Sets the wxyz"""
    def ToString(self) -> str:
        """Returns the GameQuaternion as a string"""

class GameMatrix4x3:
    Forward: GamePoint3d
    Left: GamePoint3d
    Position: GamePoint3d
    RawArray: list[float]
    Scale: float
    Up: GamePoint3d
    def __init__(self):
        pass
    def Inverse(self, matrix: 'GameMatrix4x3', result: 'GameMatrix4x3'):
        """Inverses the given matrix and places the result in the second"""
    def MatrixFromOrientation(self, quaternion: GameQuaternion, translation: GamePoint3d, scale: float, result: 'GameMatrix4x3'):
        """Creates a matrix from the given parameters and places the result in the supplied Matrix"""
    def Multiply(self, a: 'GameMatrix4x3', b: 'GameMatrix4x3', result: 'GameMatrix4x3'):
        """Multiplies the first matrix by the second and places the result in the final supplied Matrix"""

# Game Animation
class AnimationExporter():
    def __init__(self):
        pass
    def ClearTags(self) -> None:
        """Clears loaded tag data"""
    def GetAnimationCount(self) -> int:
        """Returns the number of animations in the graph"""
    def GetAnimationFrame(self, animation_index: int, frame_index: int, orientation_list: list['GameAnimationNode'], list_size: int) -> bool:
        """Loads animation frame data into the supplied GameAnimationNodes. Outputs true if this was successful"""
    def GetAnimationFrameCount(self, animation_index: int) -> int:
        """Returns the number frames in an animation"""
    def GetAnimationIndexByName(self, animation_name: str) -> int:
        """Gets the index of an animation by its name"""
    def GetGraphNodeCount(self) -> int:
        """Returns the number of nodes in this graph"""
    def GetRenderModelBasePose(self, orientation_list: list['GameAnimationNode'], list_size: int) -> int:
        """Loads animation frame data into the supplied GameAnimationNodes for the base pose of the model. Outputs true if this was sucessful"""
    def IsValid(self) -> bool:
        """Checks that the exporter is valid i.e. has a valid graph and rende model tag associated with it"""
    def LoadTags(self, graph_tag_path: 'TagPath', model_tag_path: 'TagPath') -> bool:
        """Loads the given graph and render model TagPaths"""
    def UseTags(self, graph_tag_file: 'TagFile', model_tag_file: 'TagFile') -> bool:
        """Selects the given TagFiles for use with the exporter"""
    
class GameAnimationNode():
    FrameID1: int
    FrameID2: int
    Matrix: GameMatrix4x3
    Name: str
    ParentIndex: int
    Rotation: GameQuaternion
    Scale: float
    Translation: GamePoint3d
    def __init__(self):
        pass
    def Reset(self) -> None:
        """Clears class instance properties"""

# Enum Classes
class FunctionEditorColorGraphType(Enum):
    Scalar = 0
    OneColor = 1
    TwoColor = 2
    ThreeColor = 3
    FourColor= 4
    
class FunctionEditorMasterType(Enum):
    Basic = 0
    Curve = 1
    Periodic = 2
    Exponent = 3
    Transition = 4
    
class FunctionEditorParameterDataType(Enum):
    BlockIndex = 0
    Enum = 1
    StringList = 2
    StringListUserEditOkay = 3
    
class FunctionEditorParameterType(Enum):
    Input = 0
    InputRange = 1
    OutputOp = 2
    OutputModifier = 3
    
class FunctionEditorPasteType(Enum):
    All = 0
    CurveOnly = 1
    
class FunctionEditorSegmentCornerType(Enum):
    NotApplicable = 0
    Corner = 1
    Smooth = 2
    
class FunctionEditorSegmentType(Enum):
    Linear = 0
    Spline = 1
    Spline2 = 2

class GameBitmapChannel(Enum):
    Argb = 0
    Rgb = 1
    Alpha = 2
    
class GameBitmapUse(Enum):
    RawDisplay = 0
    RawDisplayForSpritePlate = 1
    Rendering = 2
    
class ScenarioType(Enum):
    Solo = 0
    Multiplayer = 1
    MainMenu = 2
    MultiplayerShared = 3
    SinglePlayerShared = 4
    Invalid = -1
    
class StringMenuItemType(Enum):
	Item = 0
	SubMenu = 1
	Separator = 2
    
class TagAlternateStreamType(Enum):
	TagDependencyList = 0
	TagImportInformation = 1
	AssetDepotStorage = 2
    
class TagFieldAttributedDefinitions(Enum):
	Position = 1886349678
	Orientation = 1869769061
	Scale = 1935892844
	BlockWideFieldDefault = 2003395685
	BlockCollapsedFieldDefault = 1936482672
	BlockNameSorted = 1936683636
	BlockGridViewByDefault = 1735551332
	TemplateRefreshField = 1919316840
	CustomBlockFilterField = 1667656820
	StringEditor = 1937007972
	UpdateLayoutField = 1701737837
	ScenarioObjectManualBspFlags = 1835168624
	ScenarioFolderField = 1969712249
 
class TagFieldCustomType(Enum):
    UnknownType = 0
    VerticalLayout = 1986359924
    HorizontalLayout = 1752134266
    GroupBegin = 1735552811
    GroupEnd = 1735552813
    EndLayout = 1819897444
    HideGroupBegin = 1751737445
    HideGroupEnd = 1701079400
    FilterOnNextField = 1718185076
    FilterOnNextFieldFolder = 1718185080
    FilterOnNextFieldBoth = 1718185002
    EditorCommand = 1701079412
    TagTemplateViewCommand = 1734569316
    DesignerZoneBlockIndexFlags = 1651074675
    ToolCommandWithDirectory = 1952675684
    CustomButton = 1668641652
    FieldGroupBegin = 1718055522
    FieldGroupEnd = 1718055525
    SoundMarkerPlayback = 1835757676
    TagGroupTemplate = 1953329260
    CinematicDynamicLight = 1667525748
    CinematicVMFLight = 1668705638
    AuthoredLightProbe = 1635085424
    HologramLight = 1752132716
    CustomChudStateEditorBlock = 1668506978
    CustomChudRenderEditorBlock = 1668441442
    MarkerNameAttribute = 1634560882
    MatchedElementArray = 1835363425
    IndividualFieldPreviewGroupBegin = 1768321067
    IndividualFieldPreviewGroupEnd = 1768321069
    CustomObjectFunctionField = 1668245094
    DoNotCompareGroupBegin = 1684955947
    DoNotCompareGroupEnd = 1684955949
    FunctionEditor = 1718510948
    ScenarioAndZoneSet = 1937404777
    BitmapGroup = 1651730551
    ToolCommand = 1668572004
    EstimateOverdrawCommand = 1701798761
    ModelBulkImportCommand = 1751936372
    ImportParticleModelCommand = 1768975721
    CinematicPlayback = 1668182114
    CinematicPlaybackLoopScene = 1819308899
    CinematicPlaybackLoopShot = 1819308904
    CinematicShotFlags = 1668507251
    CinematicFrame = 1667851881
    Slider = 1936483684

class TagFieldStringMenuType(Enum):
    Material = 0
    ObjectFunction = 1
    AIDialogue = 2
    AIFormations = 3
    AIActivities = 4
    CinematicObjectVariant = 5
    Unknown = 6
    
class TagFieldType(Enum):
    String = 0
    LongString = 1
    StringId = 2
    OldStringId = 3
    CharInteger = 4
    ShortInteger = 5
    LongInteger = 6
    Int64Integer = 7
    Angle = 8
    Tag = 9
    CharEnum = 10
    ShortEnum = 11
    LongEnum = 12
    Flags = 13
    WordFlags = 14
    ByteFlags = 15
    Point2d = 16
    Rectangle2d = 17
    RgbPixel32 = 18
    ArgbPixel32 = 19
    Real = 20
    RealFraction = 21
    RealPoint2d = 22
    RealPoint3d = 23
    RealVector2d = 24
    RealVector3d = 25
    RealQuaternion = 26
    RealEulerAngles2d = 27
    RealEulerAngles3d = 28
    RealPlane2d = 29
    RealPlane3d = 30
    RealRgbColor = 31
    RealArgbColor = 32
    RealHsvColor = 33
    RealAhsvColor = 34
    ShortIntegerBounds = 35
    AngleBounds = 36
    RealBounds = 37
    RealFractionBounds = 38
    Reference = 39
    Block = 40
    BlockFlags = 41
    WordBlockFlags = 42
    ByteBlockFlags = 43
    CharBlockIndex = 44
    CharBlockIndexCustomSearch = 45
    ShortBlockIndex = 46
    ShortBlockIndexCustomSearch = 47
    LongBlockIndex = 48
    LongBlockIndexCustomSearch = 49
    Data = 50
    VertexBuffer = 51
    Pad = 52
    UselessPad = 53
    Skip = 54
    RuntimeHandle = 55
    Explanation = 56
    Custom = 57
    Struct = 58
    Array = 59
    Resource = 60
    Interop = 61
    Terminator = 62
    ByteInteger = 63
    WordInteger = 64
    DwordInteger = 65
    QwordInteger = 66
 
class TagGroupFlag(Enum):
    IsGameCritical = 0
    CanBeReloaded = 1
    ForcesMapReload = 2
    ForcesLightingReset = 3
    DoesNotExistInCacheBuild = 4
    CanSaveWhenNotLoadedForEditing = 5
    DoNotAttemptToPredictOnCacheMiss = 6
    DoNotAttemptToPredictThroughDependencies = 7
    DoNotAttemptToPredictChildren = 8
    DoNotXsyncToTargetPlatform = 9
    RestrictedOnXsync = 10
    CreateAsGlobalCacheFileTag = 11
    DoNotAddChildrenToGlobalZone = 12
    InvalidatesStructureMaterials = 13
    ChildrenResolvedManually = 14
    ForcesScriptRecompile = 15
    ForcesActiveZoneSetReload = 16
    RestrictedForcesActiveZoneSetReload = 17
    CannotBeCreated = 18
    ShouldNotBeUsedAsAResolvingReference = 19
    DoNotMakeScriptDependency = 20
    DoNotWriteOutUntilCacheFileLinkTime = 21
    NotLanguageNeutral = 22
    InvalidatesStructureBspGeometry = 23
    HasDependencies = 24
    IsADependent = 25
    XSyncStopsCinematic = 26
    XSyncNoDependencies = 27
    ForcesCinematicLightingReset = 28
    DiscardForDedicatedServer = 29
    
class TagSoundPlayFractionType(Enum):
    Never = 0
    AlmostNever = 1
    Rarely = 2
    Somewhat = 3
    Often = 4
    Always = 5
    Secret = 6
    
class TagTemplateFieldLocking(Enum):
    Emphasize = 0
    ReadOnly = 1
    Editable = 2
    Locked = 3
    Visible = 4
    
class TagTemplateFieldUI(Enum):
    LockFunctionType = 0
    LockFunctionColor = 1
    InlineFunction = 2
    
class TagTemplateMenuType(Enum):
    Item = 0
    SubMenu = 1
    Separator = 2
    
class VectorartPathStretchType(Enum):
    PathStretchNon = 0
    PathStretchFill = 1
    PathStretchUniform = 2
    PathStretchUniformToFill = 3
    
class VectorHudAnimatedPropertyType(Enum):
    VisualScaleX = 0
    VisualScaleY = 1
    VisualTranslateX = 2
    VisualTranslateY = 3
    VisualRotateZ = 4
    VisualOpacity = 5
    LinePoint = 6
    BezierPoint1 = 7
    BezierPoint2 = 8
    BezierPoint3 = 9
    PathfigureStartpoint = 10
    PathfigureStrokeThickness = 11
    
class VectorHudPathStretchType(Enum):
	PathStretchNone = 0
	PathStretchFill = 1
	PathStretchUniform = 2
	PathStretchUniformToFill = 3
 
# helper classes. Never to be called, but saves code duplication.
class _IEnumerator:
    def GetEnumerator(self) -> list['TagField']:
        """"""
    def GetEnumeratorNonGeneric(self) -> Enum:
        """"""
    
class _Serializer:
    def Deserialize(self, data: bytes):
        """"""
    def Serialize(self) -> bytes:
        """"""
        
class _StringData:
    def GetStringData(self) -> str:
        """"""
    def SetStringData(self, value: str) -> bool:
        """"""
        
class _StringDataArray:
    def GetStringData(self) -> list[str]:
        """"""
    def SetStringData(self, value: list[str]) -> bool:
        """"""
        
class _HashEquals:
    def Equals(self, other: object) -> bool:
        """"""
    def GetHashCode(self) -> int:
        """"""

class _GetParent:
    def GetParent(self) -> 'ITagFieldSelector':
        """"""
    def GetParentElement(self) -> 'TagElement':
        """"""
        
class _ToString:
    def ToString(self) -> str:
        """"""

class _IDisposable:
    def Dispose(self):
        """"""

class _ValueString:
    def GetValueString(self) -> str:
        """"""
    def SetValueString(self, value: str) -> bool:
        """"""
        
class _ValueStringArray:
    def GetValueString(self) -> list[str]:
        """"""
    def SetValueString(self, value: list[str]) -> bool:
        """"""

# Actual classes
class CacheFile():
    HeaderSize: int
    def __init__(self):
        pass
    def GetHeaderInfo(self, headerData: bytes) -> 'CacheFileHeaderInfo':
        pass

class CacheFileHeaderInfo:
    BuildNumber: str
    HeaderSignature: int
    Path: str
    Size: int
    TagPath: str
    TotalTagsSize: int
    Version: int
    def __init__(self, headerData: bytes):
        pass
    
class FunctionEditorParameter:
    DataType: FunctionEditorParameterDataType
    Type: FunctionEditorParameterType
    ValueAsIndex: int
    ValueAsString: str
    def GetText(self) -> list[str]:
        pass
    
class FunctionEditorSerialized:
    def InspectColorGraphType(self, serialized_function: bytes) -> FunctionEditorColorGraphType:
        pass
    
class GameBitmap(_IDisposable):
    AreAxisFlipped: bool
    Height: int
    HighPixelDataSize: int
    MediumPixelDataSize: int
    RequiredPixelDataSize: int
    SequenceIndex: int
    SpriteFrameIndex: int
    Width: int
    def __init__(self, bitmapTag: 'TagFile', sequenceIndex: int, spriteFrameIndex: int, showMipLevels: bool, use: GameBitmapUse):
        pass
    def __init__(self, bitmapTag: 'TagFile', sequenceIndex: int, spriteFrameIndex: int, use: bool):
        pass
    def __init__(self, bitmapTag: 'TagFile', sequenceIndex: int, spriteFrameIndex: int):
        pass
    def GetBitmap(self, channel: GameBitmapChannel) -> Bitmap:
        """"""
    def GetBitmap(self) -> Bitmap:
        """"""
    def GetBitmapArgb(self, channel: GameBitmapChannel) -> bytes:
        """"""
    def GetSequenceCount(self, bitmapTag: 'TagFile') -> int:
        """"""
    def GetSpriteFrameCount(self, bitmapTag: 'TagFile', use: GameBitmapUse, sequenceIndex: int) -> int:
        """"""
    def GetSpriteSeparation(self, bitmapTag: 'TagFile') -> int:
        """"""
    def IsSpritePlate(self, bitmapTag: 'TagFile', sequenceIndex: int) -> bool:
        """"""
    
class GameDesignerZoneInfo:
    Name: str
    references: list[str]
    def __init__(self, name: bytes):
        pass
    
class GameRenderGeometry:
    def __init__(self):
        pass
    def GetMeshInfo(self, renderGeometryBloc: 'TagFieldStruct', meshIndex: int) -> 'GameRenderGeometryInfo':
        """"""
    def GetMeshInfo(self, renderGeometryBloc: 'TagFieldStruct') -> 'GameRenderGeometryInfo':
        """"""
    def GetModelInfo(self, tag_path: str) -> 'GameRenderModelInfo':
        """"""
    
class GameRenderGeometryInfo:
    index_bytes: int
    index_count: int
    parts: int
    subparts: int
    triangle_count: int
    vertex_bytes: int
    vertex_count: int
    vertex_type: int
    def __init__(self):
        pass
    
class GameRenderMaterialInfo:
    bitmap_usage: list[int]
    mesh_usage: list[int]
    name: str
    def __init__(self):
        pass
    
class GameRenderModel:
    def __init__(self):
        pass
    def GetNodeIndiciesFromMesh(self, rawDataBlock: 'TagFieldBlock', meshIndex: int) -> bytes:
        """"""
    def GetNodeWeightsFromMesh(self, rawDataBlock: 'TagFieldBlock', meshIndex: int) -> list[float]:
        """"""
    def GetNormalsFromMesh(self, rawDataBlock: 'TagFieldBlock', meshIndex: int) -> list[float]:
        """"""
    def GetPositionsFromMesh(self, rawDataBlock: 'TagFieldBlock', meshIndex: int) -> list[float]:
        """"""
    def GetTexCoordsFromMesh(self, rawDataBlock: 'TagFieldBlock', meshIndex: int) -> list[float]:
        """"""
    
class GameRenderModelBitmapInfo:
    bytes: int
    count: int
    depth: int
    format: int
    height: int
    bitmap_usage: list[int]
    mesh_usage: list[int]
    mipmaps: int
    name: int
    type: int
    width: int
    def __init__(self):
        pass
    
class GameRenderModelInfo:
    animation_bytes: int
    collision_bytes: int
    geo: list[GameRenderGeometryInfo]
    imposter_bytes:int
    material: list[GameRenderMaterialInfo]
    model_bytes: int
    name: str
    physics_bytes: int
    texture: list[GameRenderModelBitmapInfo]
    texture_bytes: int
    total_bytes: int
    total_geo: GameRenderGeometryInfo
    variations: list['GameRenderModelVariationInfo']
    def __init__(self):
        pass
    
class GameRenderModelVariationInfo:
    children: list[GameRenderModelInfo]
    geo: GameRenderGeometryInfo
    material_used: list[int]
    meshes_used: list[int]
    name: str
    parent_model: GameRenderModelInfo
    textures_used: list[int]
    def __init__(self):
        pass
    
class GameScenario:
    def __init__(self):
        pass
    def GetScenarioDesignerZones(self, scenarioTagPath: str) -> list[GameDesignerZoneInfo]:
        """"""
    def GetScenarioObjectsNeedingToBeAssignedToDesignerZones(self, scenarioTagPath: str) -> list[str]:
        """"""
 
class ITagElementCollection(list):
    Count: int
    def this(self, element_index: int) -> 'TagElement':
        """Returns the tag element of the given index"""
        
class ITagElementContainer:
    Elements: ITagElementCollection
    IsRoot: bool
    def GetParentElement(self) -> 'TagElement':
        """"""
        
class ITagFieldInlined:
    def SumInlinedAddressOffsets(self) -> int:
        """"""
    def SumInlinedLocatorOffsets(self) -> int:
        """"""
        
class ITagFieldSelector:
    @staticmethod
    def SelectField(fieldPath: str) -> 'TagField | TagFieldBlock | TagFieldCustom | TagFieldElementString | TagFieldElementStringID | TagFieldReference | TagFieldEnum | TagElement | TagFieldFlags':
        """"""
    @staticmethod
    def SelectFields(fieldPath: str) -> list['TagField']:
        """"""
    @staticmethod
    def SelectFieldType(fieldPath: str) -> 'TagField':
        """"""
        
class ITagFieldSerializable:
    def Deserialize(self, data: bytes):
        """"""
    def Serialize(self) -> bytes:
        """"""

class ObjectFunctionStringEditor:
    def __init__(self, tag_file: 'TagFile'):
        pass
    def GetMenuEntryId(self, parent_menu_entry_id: int, entry_index: int) -> int:
        """"""
    def GetMenuEntryText(self, menu_entry_id: int) -> str:
        """"""
    def GetMenuEntryType(self, menu_entry_id: int) -> StringMenuItemType:
        """"""
    def GetStringMenuCount(self, menu_entry_id: int) -> int:
        """"""
    def ValidString(text: str) -> bool:
        """"""
        
class PolyartImporterMB:
    NumberOfIndices: int
    NumberOfVertices: int
    ResourceSize: int
    def __init__(self, tag_file: 'TagFile'):
        pass
    def Import(dataFilename: str):
        """Imports a polyart asset from the given source fbx file"""

class TagElement(ITagFieldSelector, ITagFieldSerializable, _IEnumerator):
    ElementDefinition: 'TagElementDefinition'
    ElementHeaderText: str
    ElementIndex: int
    FieldPath: str
    FieldPathWithoutindices: str
    Fields: list['TagField']
    Size: int
    def GetParentContainer(self) -> ITagElementContainer:
        """"""
    def GetTagFieldPath(self) -> 'TagFieldPath':
        """"""
    
class TagElementDefinition:
    ElementSize: int
    Fields: list['TagFieldDefinition']
    def Equals(self, other: object) -> bool:
        """"""
    def GetHashCode(self) -> int:
        """"""
@dataclass
class TagField(ITagFieldSerializable, _GetParent, _HashEquals, _ToString):
    Address: int
    Description: str
    DisplayName: str
    FieldDefinition: 'TagFieldDefinition'
    FieldName: str
    FieldPath: str
    FieldPathWithoutindices: str
    FieldSubtype: str
    FieldType: TagFieldType
    File: 'TagFile'
    ReadOnly: bool
    Size: int
    SupportsFastIndividualFieldPreview: bool
    Units: str
    Visible: bool
    def CalculateFiledChecksum(self) -> int:
        """"""
    def GetRawData(self) -> bytes:
        """"""
    def GetTagFieldPath(self) -> 'TagFieldPath':
        """"""
    def __init__(self):
        pass
        
class TagFieldArray(_IEnumerator, ITagFieldSerializable, ITagElementContainer, _GetParent):
    Elements: list[TagElement]
    IsRoot: bool
    Size: int
        
class TagFieldArrayElement(TagElement, ITagFieldInlined, ITagFieldSerializable):
    ElementDefinition: TagElementDefinition
    Fields: list[TagField]
    Size: int
    
class TagFieldBlock(TagField, ITagElementContainer, ITagFieldSerializable, _IEnumerator, _GetParent):
    Elements: list[TagElement]
    IsCollapsedByDefault: bool
    IsGridViewByDefault: bool
    IsRoot: bool
    IsSortedByDefault: bool
    IsWideByDefault: bool
    MaximumElementCount: int
    Size: int
    def AddElement(self) -> 'TagFieldBlockElement':
        """Adds an element to the block and returns it"""
    def ClipboardContainsBlockElement(self) -> bool:
        """"""
    def ClipboardContainsEntireBlock(self) -> bool:
        """"""
    def CopyElement(self, elementIndex: int):
        """"""
    def CopyEntireTagBlock(self):
        """"""
    def DuplicateElement(self, elementIndex: int) -> 'TagFieldBlockElement':
        """"""
    def InsertElement(self, elementIndex: int) -> 'TagFieldBlockElement':
        """"""
    def PasteAppendElement(self):
        """"""
    def PasteAppendEntireBlock(self):
        """"""
    def PasteInsertElement(self, elementIndex: int):
        """"""
    def PasteReplaceElement(self, elementIndex: int):
        """"""
    def PasteReplaceEntireBlock(self):
        """"""
    def RemoveAllElements(self):
        """"""
    def RemoveElement(self, elementIndex: int):
        """"""
 
class TagAlternateStream(TagFieldBlock):
    IsRoot: bool
    def __init__(self, tag_file: 'TagFile', block: int, locator_offset: int):
        pass
 
class TagFieldBlockElement(TagElement, ITagFieldSerializable, _ToString):
    ElementDefinition: TagElementDefinition
    ElementHeaderText: str
    Fields: list[TagField]
    Size: int
        
class TagFieldBlockElementCollection(ITagElementCollection):
    Count: int
    def this(self, element_index: int) -> TagElement:
        """Returns the tag element of the given index"""

class TagFieldBlockFlags(TagField):
    class TagFieldBlockFlagsItem(_ToString):
        Description: str
        DisplayName: str
        FlagBit: int
        FlagName: str
        IsSet: bool
        ReadOnly: bool
        Units: str
        Visible: bool

    Items: list[TagFieldBlockFlagsItem]
    ReferencedBlockAddress: int
    Value: int
 
class TagFieldBlockIndex(TagField):
    class TagFieldBlockIndexItem(_ToString):
        BlockIndex: int
        BlockIndexName: str
        Description: str
        DisplayName: str
        Visible: bool

    Items: list[TagFieldBlockIndexItem]
    ReferencedBlockAddress: int
    Value: int
    def GetReferencedBlock(self) -> TagFieldBlock:
        """"""
    def GetReferencedBlockElement(self) -> TagFieldBlockElement:
        """"""
        
class TagFieldCustom(TagField):
    CustomType: TagFieldCustomType
    
class TagFieldCustomAuthoredLightProbe(TagFieldCustom):
    pass

class TagFieldCustomCinematicDynamicLight(TagFieldCustom):
    pass

class TagFieldCustomCinematicFrame(TagFieldCustom):
    MaxFrame: int
    MinFrame: int
    
class TagFieldCustomCinematicLoopScene(TagFieldCustom):
    def GetLoopText(self, cinematicPath: 'TagPath') -> str:
        """"""
    def GetStopCinematicText(self) -> str:
        """"""

class TagFieldCustomCinematicLoopShot(TagFieldCustomCinematicLoopScene):
    pass

class TagFieldCustomCinematicPlayback(TagFieldCustom):
    def GetBspChecked(self, index: int) -> bool:
        """"""
    def GetBspCount(self) -> int:
        """"""
    def GetBspText(self, index: int) -> str:
        """"""
    def GetPauseCinematicText(self) -> str:
        """"""
    def GetPlayCinematicText(self, loop: bool) -> str:
        """"""
    def GetScenarioCinematicIndex(self) -> int:
        """"""
    def GetScenarioName(self) -> str:
        """"""
    def GetSceneChecked(self, scene_index: int) -> bool:
        """"""
    def GetSceneCount(self) -> int:
        """"""
    def GetSceneExpanded(self, scene_index: int) -> bool:
        """"""
    def GetSceneText(self, scene_index: int) -> str:
        """"""
    def GetShotChecked(self, scene_index: int, shot_index: int) -> bool:
        """"""
    def GetShotCount(self, scene_index: int) -> str:
        """"""
    def GetShotChecked(self, scene_index: int, shot_index: int) -> str:
        """"""
    def GetStepCinematicText(self) -> str:
        """"""
    def GetStopCinematicText(self, loop: bool, cinematicInProgressIndex: int) -> str:
        """"""
    def GetZoneSetIndex(self) -> int:
        """"""
    def GetZoneSetName(self) -> str:
        """"""
    def IsCinematicTypePerspective(self) -> bool:
        """"""
    def IsScenarioReferenceValid(self) -> bool:
        """"""
    def IsZoneSetIndexValid(self) -> bool:
        """"""
    def RefreshBspZones(self):
        """"""
    def RefreshScenes(self):
        """"""
    def SetBspChecked(self, index: int, checked: bool):
        """"""
    def SetSceneChecked(self, scene_index: int, checked: bool):
        """"""
    def SetSceneExpanded(self, scene_index: int, expanded: bool):
        """"""
    def SetShotChecked(self, scene_index: int, shot_index: int, checked: bool):
        """"""
    def SynchronizeFieldData(self):
        """"""

class TagFieldCustomCinematicShotFlags(TagFieldCustom):
    ShotBlockAddress: int
    ShotCount: int
    def ClearShots(self):
        """"""
    def GetShotChecked(self, shotIndex: int) -> bool:
        """"""
    def GetShotText(self, shotIndex: int) -> str:
        """"""
    def RefreshShots(self):
        """"""
    def SetShotChecked(self, shotIndex: int, checked: bool):
        """"""

class TagFieldCustomCinematicVMFLight(TagFieldCustom):
    pass

class TagFieldCustomEditorCommand(TagFieldCustom):
    class CommandResultFlags(Enum):
        none = 0,
        Modified = 1,
        Refresh = 2,
        NeedsRemoteConnection = 3
    def RunCommand(self) -> CommandResultFlags:
        """Executes the command"""
    
class TagFieldCustomFunctionEditor(TagFieldCustom):
    FunctionName: str
    Value: 'TagValueCustomFunctionEditor'

class TagFieldCustomHologramLight(TagFieldCustom):
    pass

class TagFieldCustomScenarioAndZoneSet(TagFieldCustom):
    Items: list[str]
    ScenarioPath: str
    ZoneSet: int
    def SetScenarioPath(self, tagPath: 'TagPath'):
        """"""
        
class TagFieldCustomSlider(TagFieldCustom):
    Increment: float
    MaxValue: float
    MinValue: float
    
class TagFieldCustomTagGroupTemplate(TagFieldCustom):
    GroupTag: str
    
class TagFieldCustomToolCommand(TagFieldCustom):
    ArgumentList: list[str]
    ToolCommandDisplayName: str
    ToolCommandName: str
    def RefreshArgumentList(self):
        """"""
        
class TagFieldData(TagField):
    ByteCount: int
    DataAsText: str
    DataAsTextExtension: str
    DataAsTextMaxLength: int
    IsEditableAsText: bool
    def GetData(self) -> bytes:
        """"""
    def GetData(self, bytes):
        """"""
        
class TagFieldDefinition(_HashEquals):
    Element: TagElementDefinition
    FieldInfo: 'TagFieldNameInfo'
    FieldSize: int
    FieldSubtype: str
    FieldType: TagFieldType
    Parent: TagElementDefinition
    RawFieldName: str
        
class TagFieldElement(TagField, _StringData):
    pass
        
class TagFieldElementArray(TagField, _StringDataArray):
    Count: int
        
class TagFieldElementArrayInteger(TagFieldElementArray, _StringDataArray):
    Data: list[int]
        
class TagFieldElementArraySingle(TagFieldElementArray, _StringDataArray):
    Data: list[int]
        
class TagFieldElementInteger(TagFieldElement):
    Data: int

class TagFieldElementOldStringID(TagFieldElement):
    Data: str
    MaxLength: int
        
class TagFieldElementSingle(TagFieldElement):
    Data: float

class TagFieldElementString(TagFieldElement):
    Data: str
    MaxLength: int
    
class TagFieldElementLongString(TagFieldElementString):
    pass
    
class TagFieldElementStringID(TagFieldElement):
    Data: str
    MaxLength: int
    
class TagFieldElementStringIDWithMenu(TagFieldElementStringID):
    ContextMenu: 'TagFieldStringMenu'
    MenuType: TagFieldStringMenuType

class TagFieldElementStringNormal(TagFieldElementString):
    pass

class TagFieldElementTag(TagFieldElement):
    Data: str
    MaxLength: int
    
class TagFieldElementUnsignedInteger(TagFieldElement):
    Data: int

class TagFieldEnum(TagField):
    BitCount: int
    Items: list['TagValueEnumItem']
    Value: int
    def SetValue(self, itemName: str):
        """"""

class TagFieldExplanation(TagField):
    Explanation: str

class TagFieldFlags(TagField):
    BitCount: int
    Items: list['TagValueFlagItem']
    RawValue: int
    def SetBit(self, flagName: str, value: bool):
        """"""
    def TestBit(self, flagName: str) -> bool:
        """"""

class TagFieldInterop(TagField):
    pass

class TagFieldNameInfo:
    Description: str
    DisplayName: str
    FieldName: str
    IsLabelOfBlockElement: bool
    ReadOnly: bool
    Units: str
    Visible: bool
    def GetSpecialCharacters(self) -> str:
        """"""

class TagFieldPath(_HashEquals, _ToString):
    Field: 'TagFieldPath'
    FieldIndex: int
    FieldName: str
    FieldType: TagFieldType
    Name: str
    NameWithoutindices: str
    Parent: 'TagFieldPath'
    Path: str
    PathWithoutindices: str
    def __init__(self, name: str, type: TagFieldType, index: int, parent: 'TagFieldPath'):
        pass
    def __init__(self, name: str, type: TagFieldType, parent: 'TagFieldPath'):
        pass
    def __init__(self, name: str, type: TagFieldType, index: int):
        pass
    def __init__(self, name: str, type: TagFieldType):
        pass
    def CanParseTagFieldType(typeString: str) -> bool:
        """"""
    def Clone(typeString: str) -> object:
        """"""
    def Combine(start: 'TagFieldPath', end: 'TagFieldPath') -> 'TagFieldPath':
        """"""
    def GrandestParent(path: 'TagFieldPath') -> 'TagFieldPath':
        """"""
    def Parse(fullPath: str) -> 'TagFieldPath':
        """"""
    def ParseTagFieldPath(path: str) -> 'TagFieldPath':
        """"""
    def ParseTagFieldType(typeString: str) -> 'TagFieldPath':
        """"""
    def RemoveGrandestParent(path: 'TagFieldPath') -> 'TagFieldPath':
        """"""

class TagFieldReference(TagField):
    Definition: 'TagReferenceDefinition'
    Path: 'TagPath'
    Reference: 'TagReference'
    
class TagFieldResource(TagField):
    pass

class TagFieldStringMenu:
    RootMenuItem: 'TagFieldStringMenuItem'
    def RefreshMenuItems(self):
        """"""
        
class TagFieldStringMenuItem:
    Items: list['TagFieldStringMenuItem']
    MenuType: StringMenuItemType
    Parent: 'TagFieldStringMenuItem'
    Text: str

class TagFieldStruct(TagField, ITagElementContainer, ITagFieldInlined, ITagFieldSerializable, _IEnumerator):
    Element: ITagElementCollection
    IsRoot: bool
    
class TagFieldStructElement(TagElement, ITagFieldInlined, ITagFieldSerializable):
    ElementDefinition: TagElementDefinition
    Fields: list[TagField]
    Size: int
    
class TagFieldVertexBuffer(TagField):
    pass

class TagFile(ITagFieldSelector, ITagElementContainer, ITagFieldSerializable, _IEnumerator, _IDisposable):
    Checksum: int
    Elements: ITagElementCollection
    FieldPath: str
    FieldPathWithoutindices: str
    Fields: list[TagField]
    HasPostprocessOnSyncProc: bool
    HasPostprocessProc: bool
    IsFutureVersion: bool
    IsReadOnly: bool
    IsRoot: bool
    Path: 'TagPath'
    Root: TagElement
    RootDefinition: TagElementDefinition
    Size: int
    def __init__(self, tagPath: 'TagPath', isWeak: bool):
        pass
    def __init__(self, tagPath: 'TagPath'):
        pass
    def __init__(self):
        pass
    @staticmethod
    def CalculateFieldChecksum() -> int:
        """"""
    @staticmethod
    def Copy() -> 'TagFile':
        """"""
    @staticmethod
    def DoesAlternateStreamExist(type: TagAlternateStreamType) -> bool:
        """"""
    @staticmethod
    def GetAlternateStream(type: TagAlternateStreamType) -> ITagFieldSelector:
        """"""
    @staticmethod
    def GetAlternateStreamTypes() -> list[TagAlternateStreamType]:
        """"""
    @staticmethod
    def GetChecksum(tagPath: 'TagPath') -> int:
        """"""
    @staticmethod
    def GetOrCreateAlternateStrea(type: TagAlternateStreamType) -> ITagFieldSelector:
        """"""
    @staticmethod
    def GetTagFieldPath() -> TagFieldPath:
        """"""
    @staticmethod
    def Load(tagPath: 'TagPath'):
        """Loads a tag for editing/reading"""
    @staticmethod
    def New(tagPath: 'TagPath'):
        """Creates a new TagFile instance. Saves a new tag when Save() called"""
    @staticmethod
    def Save(tagPath: 'TagPath'):
        """Saves the loaded tag"""
    @staticmethod
    def SaveAs(tagPath: 'TagPath'):
        """Saves the loaded tag to the given TagPath and loads it"""
    @staticmethod
    def SaveAsCopy(tagPath: 'TagPath'):
        """Saves the loaded tag to the given TagPath, keeping the original loaded"""
    @staticmethod
    def SelectField(fieldPath: str) -> 'TagField | TagFieldBlock | TagFieldCustom | TagFieldElementString | TagFieldElementStringID | TagFieldReference | TagFieldEnum | TagElement | TagFieldFlags':
        """"""
    @staticmethod
    def SelectFields(fieldPath: str) -> list[TagField]:
        """Gets the TagFields at the given path"""
    @staticmethod
    def SelectFieldType(fieldPath: str) -> TagField:
        """"""
    @staticmethod
    def SelectTagFieldReferencesFast() -> list[TagFieldReference]:
        """"""
    @staticmethod
    def SerializeForQuickPreview() -> bytes:
        """"""
    
class TagFileElement(TagElement, ITagFieldSerializable):
    ElementDefinition: TagElementDefinition
    Fields: list[TagField]
    Size: int
    
class TagGroupType:
    CanBeCreated: bool
    ChildCount: int
    DefaultDirectory: str
    ElementDefinition: TagElementDefinition
    Extension: str
    Flags: list[TagGroupFlag]
    GroupTag: str
    HasPostprocessOnSyncProc: bool
    HasPostprocessProc: bool
    HasTagReferenceFields: bool
    ParentGroupTag: bool
    def GetDefinition(self, groupType: str) -> 'TagGroupType':
        """"""
    def GetDefinition(self, groupType: str) -> 'TagGroupType':
        """"""
    def GetExtensionFromGroupType(self, groupType: str) -> str:
        """"""
    def GetGroupTypeFromExtension(self, extension: str) -> str:
        """"""
    def GetTagGroups(self) -> list['TagGroupType']:
        """"""
    def GroupTypeHasTagReferenceFields(self, groupType: str) -> bool:
        """"""
        
class TagLoadException:
    IsStringIDCountMaxedOut: bool
    IsStringIDStorageMaxedOut: bool
    def __init__(self, message: str, inner: Exception):
        pass
    def __init__(self, message: str):
        pass
    
class TagPath(_HashEquals, _ToString):
    Extension: str
    Filename: str
    GroupType: TagGroupType
    RelativePath: str
    RelativePathWithExtension: str
    ShortName: str
    ShortNameWithExtension: str
    Type: str
    @staticmethod
    def FromFilename(filename: str) -> 'TagPath':
        """Returns a TagPath from a full filepath"""
    @staticmethod
    def FromPathAndExtension(tagPath: str, extension: str) -> 'TagPath':
        """Returns a TagPath from the tags relative filepath to a file without extension, plus extension"""
    @staticmethod
    def FromPathAndType(tagPath: str, type: str) -> 'TagPath':
        """Returns a TagPath from the tags relative filepath to a file without extension, plus the tag type"""
    @staticmethod
    def IsTagFileAccessible() -> bool:
        """"""
        
class TagReference:
    DefaultExtension: str
    Path: TagPath
    def GetDefaultTagDirectory(self) -> str:
        """"""
    def ReferencePointsSomewhere(self) -> bool:
        """"""
    def ReferencePointsToValidTagFile(self) -> bool:
        """"""
        
class TagReferenceDefinition:
    DefaultExtension: str
    IsWeakReference: bool
    def GetAllowedGroupTypes(self) -> list[TagGroupType]:
        """"""
    def GetDefaultTagDirectory(self) -> str:
        """"""
    def TagPathIsAllowable(self, tagPath: TagPath) -> bool:
        """"""
        
class TagSaveException:
    def __init__(self, message: str, inner: Exception):
        pass
    def __init__(self, message: str):
        pass
    
class TagSoundPlayFraction(_ToString):
    DisplayName: str
    Name: str
    PlayFractionType: TagSoundPlayFractionType
    
class TagSoundPlayFractionCollection:
    PlayFractions: list[TagSoundPlayFraction]
    def __init__(self):
        pass
    def GetPlayFraction(self, name: str) -> TagSoundPlayFraction:
        """"""
    def GetPlayFraction(self, type: TagSoundPlayFractionType) -> TagSoundPlayFraction:
        """"""

class TagSystem:
    HardResetRequested: bool
    IsInitialized: bool
    def __init__(self):
        pass
    def Reset(self):
        """"""
    def Start(self):
        """"""
    def Stop(self):
        """"""
        
class TagTemplate(_IDisposable):
    ShowTemplateReference: bool
    TemplateReference: 'TagValueReference'
    def __init__(self, tagFile: TagFile, templateField: TagFieldCustomTagGroupTemplate):
        pass
    def __init__(self, tagFile: TagFile):
        pass
    def GetIsTagTemplate(self, groupTag: str) -> bool:
        """"""
    def GetLayout(self) -> 'TagTemplateLayout':
        """"""
    def ShowTagTemplateByDefault(self, groupTag: str) -> bool:
        """"""
    

class TagTemplateCategory:
    Explanation: str
    Name: str
    Parameters: list['TagTemplateParameter']
    
class TagTemplateLayout(_IDisposable):
    Categories: list[TagTemplateCategory]
    Dependencies: list[TagReference]
    
class TagTemplateMenu:
    Items: list['TagTemplateMenuItem']
    def MenuItemClicked(self, menuItem: 'TagTemplateMenuItem'):
        """"""
    def MenuPopup(self, menuItem: 'TagTemplateMenuItem'):
        """"""
        
class TagTemplateMenuItem:
    Items: list['TagTemplateMenuItem']
    MenuType: TagTemplateMenuType
    Parent: 'TagTemplateMenuItem'
    Text: str
    
class TagTemplateParameter:
    CausesTemplateReload: bool
    DefaultParameterHelp: 'TagTemplateParameterHelp'
    DefaultValue: 'TagValue'
    HeaderHelp: 'TagTemplateParameterHelp'
    MaxValue: float
    MinValue: float
    Name: str
    ParameterHelp: 'TagTemplateParameterHelp'
    TicksFromMinToMaxValue: int
    UIFlags: list[TagTemplateFieldUI]
    UnfriendlyName: str
    Value: 'TagValue'
    def ClearValue(self):
        """"""
    def CreateValue(self):
        """"""
    def GetContextMenu(self) -> TagTemplateMenu:
        """"""
    def GetLockingFlags(self) -> list[TagTemplateFieldLocking]:
        """"""
    def SetLocked(self, value: bool):
        """"""
    
class TagTemplateParameterHelp:
    IsHelpAvailable: bool
    def __init__(self, tag_template: TagTemplate, category_context: int, parameter_context: int, help_type: e_tag_template_help_type):
        pass
    def GetHelp(self, text: str, bitmap: Bitmap):
        """"""

class TagUnitTest:
    def __init__(self):
        pass
    def DebugGetLocatorOffsets(self, tagFile: TagFile, debugString: StringBuilder):
        """"""
    def FillOutTestTag(self, tagFile: TagFile):
        """"""
    def DebugGetLocatorOffsets(self, tagFile: TagFile):
        """"""
        
class TagSaveException:
    def __init__(self, message: str, inner: Exception):
        pass
    def __init__(self, message: str):
        pass
    
class TagValue:
    FieldType: TagFieldType
    def __init__(self, field_type: e_tag_field, data: None, definition: None, id: int):
        pass
    def OnValueChanged(self, args: None):
        """"""
    
class TagValueCustom(TagValue):
    CustomType: TagFieldCustomType
    
class TagValueCustomFunctionEditor(TagValueCustom):
    ClampRangeMax: float
    ClampRangeMin: float
    ColorCount: int
    ColorGraphType: FunctionEditorColorGraphType
    ExclusionMax: float
    ExclusionMin: float
    GraphCount: int
    IsClamped: bool
    IsColorLocked: bool
    IsCyclic: bool
    IsExclusion: bool
    IsRanged: bool
    IsTypeLocked: bool
    MasterType: FunctionEditorMasterType
    def BeginUpdate(self):
        """"""
    def DeleteControlPoint(self, graphIndex: int, pointIndex: int):
        """"""
    def Deserialize(self, tag_file: TagFile, tagField: TagField, data: bytes, paste_type: FunctionEditorPasteType):
        """"""
    def BeginUpdate(self):
        """"""
    def Evaluate(self, input: float, range: float) -> float:
        """"""
    def EvaluateColor(self, input: float, range: float) -> GameColor:
        """"""
    def GetAmplitudeMax(self, graphIndex: int) -> float:
        """"""
    def GetAmplitudeMin(self, graphIndex: int) -> float:
        """"""
    def GetCanChangeColorCount(self, tagFile: TagFile) -> bool:
        """"""
    def GetColor(self, colorIndex: int) -> GameColor:
        """"""
    def GetControlPoint(self, graphIndex: int, pointIndex: int) -> GamePoint2d:
        """"""
    def GetControlPointCornerType(self, graphIndex: int, pointIndex: int) -> FunctionEditorSegmentCornerType:
        """"""
    def GetControlPointCount(self, graphIndex: int) -> int:
        """"""
    def GetExponent(self, graphIndex: int) -> float:
        """"""
    def GetFieldCount(self) -> int:
        """"""
    def GetFields(self, tagFile: TagFile, tagField: TagField) -> list[TagField]:
        """"""
    def GetFields(self, tagFile: TagFile) -> list[TagField]:
        """"""
    def GetFrequency(self, graphIndex: int) -> float:
        """"""
    def GetFunctionIndex(self, graphIndex: int) -> int:
        """"""
    def GetFunctionMaximumGraphCount(self) -> int:
        """"""
    def GetIsGraphPoint(self, graphIndex: int, segmentIndex: int) -> bool:
        """"""
    def GetMaximumSegmentCount(self) -> int:
        """"""
    def GetParameter(self, tagFile: TagFile, tagField: TagField, type: FunctionEditorParameterType) -> FunctionEditorParameter:
        """"""
    def GetPeriodicFunctionCount(self) -> int:
        """"""
    def GetPeriodicFunctionText(self, periodicFunctionIndex: int) -> str:
        """"""
    def GetPhase(self, graphIndex: int) -> float:
        """"""
    def GetPointIndexFromSegment(self, graphIndex: int, segmentIndex: int) -> int:
        """"""
    def GetPossibleColorCount(self, tagFile: TagFile) -> int:
        """"""
    def GetPossibleColorCountText(self, tagFile: TagFile, colorIndex: int) -> str:
        """"""
    def GetSegmentCount(self, graphIndex: int) -> int:
        """"""
    def GetSegmentType(self, graphIndex: int, segmentIndex: int) -> FunctionEditorSegmentType:
        """"""
    def GetTransitionFunctionCount(self) -> int:
        """"""
    def GetTransitionFunctionCount(self, transitionFunctionIndex: int) -> str:
        """"""
    def GetValidColorTypeFlagRange(self, tagFile: TagFile) -> int:
        """"""
    def InsertControlPoint(self, graphIndex: int, x: float):
        """"""
    def Serialize(self, tag_file: TagFile, tag_field: TagField):
        """"""
    def SetAmplitudeMax(self, graphIndex: int, value: float):
        """"""
    def SetAmplitudeMin(self, graphIndex: int, value: float):
        """"""
    def SetColor(self, colorIndex: int, value: GameColor):
        """"""
    def SetControlPoint(self, graphIndex: int, pointIndex: int, point: GamePoint2d):
        """"""
    def SetControlPointCornerType(self, graphIndex: int, pointIndex: int, value: FunctionEditorSegmentCornerType):
        """"""
    def SetExponent(self, graphIndex: int, value: float):
        """"""
    def SetFrequency(self, graphIndex: int, value: float):
        """"""
    def SetFunctionIndex(self, graphIndex: int, value: int):
        """"""
    def SetPhase(self, graphIndex: int, value: float):
        """"""
    def SetPossibleColorCount(self, tagFile: TagFile, colorCountIndex: int):
        """"""
    def SetSegmentType(self, graphIndex: int, segmentIndex: int, value: FunctionEditorSegmentType):
        """"""

class TagValueCustomToolCommand(TagValueCustom):
    ArgumentList: list[str]
    ToolCommandName: str
    
class TagValueEnum(TagValue):
    BitCount: int
    EnumDefinition: s_string_list_definition
    Items: list['TagValueEnumItem']
    Value: int
    
class TagValueEnumItem(_ToString):
    Description: str
    DisplayName: str
    EnumIndex: int
    EnumName: str
    Visible: bool
    
class TagValueExplanation(TagValue):
    Explanation: str
    def __init__(self, type: e_tag_field, data: None, defintion: None, id: int):
        pass
    
class TagValueFlagItem:
    Description: str
    DisplayName: str
    FlagIndex: int
    FlagName: str
    Visible: bool
    
class TagValueFlags(TagValue):
    BitCount: int
    FlagsDefinition: s_string_list_definition
    Items: list[TagValueFlagItem]
    RawValue: int
    def SetBit(self, flagIndex: int, value: bool):
        """"""
    def SetBit(self, flagName: str, value: bool):
        """"""
    def TestBit(self, flagIndex: int) -> bool:
        """"""
    def TestBit(self, flagName: str) -> bool:
        """"""

class TagValueReference(TagValue):
    Definition: TagReferenceDefinition
    Reference: TagReference
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueSimple(TagValue, _ValueString):
    Value: int
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueSimpleArray(TagValue, _ValueStringArray):
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueInteger(TagValueSimple, _ValueString):
    Value: int
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueArrayInteger(TagValueSimpleArray, _ValueStringArray):
    Count: int
    Value: list[int]
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass

class TagValueArraySingle(TagValueSimpleArray, _ValueStringArray):
    Count: int
    Value: list[int]
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass

class TagValueSingle(TagValueSimple):
    Value: float
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueString(TagValueSimple):
    Value: str
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueStringID(TagValueSimple):
    Value: str
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueStringIDWithMenu(TagValueStringID):
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    def GetContextMenu(self, tagFile: TagFile):
        """"""

class TagValueStringLong(TagValueString):
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueStringNormal(TagValueString):
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class TagValueUnsignedInteger(TagValueSimple):
    Value: int
    def __init__(self, type: e_tag_field, data: None, definition: None, id: int):
        pass
    
class VectorartImporterMB:
    NumberOfIndices: int
    NumberOfVertices: int
    ResourceSize: int
    def __init__(self, tagFile: TagFile):
        pass
    def BeginVectorartWrite(self):
        """"""
    def EndCanvas(self):
        """"""
    def EndFigure(self):
        """"""
    def EndPath(self):
        """"""
    def EndVectorartWrite(self):
        """"""
    def WriteCanvas(self, width: float, height: float, x: float, y: float, opacity: float, rotateZ: float, scaleX: float, scaleY: float, translateX: float, translateY: float):
        """"""
    def WriteFigure(self, startPointX: float, startPointY: float, isClosed: bool):
        """"""
    def WritePath(self, width: float, height: float, x: float, y: float, opacity: float, rotateZ: float, scaleX: float, scaleY: float, translateX: float, translateY: float, fillColor: int, strokeColor: int, strokeThickness: float, boundsX: float, boundsY: float, boundsWidth: float, boundsHeight: float, stretchType: VectorartPathStretchType):
        """"""
    def WritePathBezierSegment(point1X: float, point1Y: float, point2X: float, point2Y: float, point3X: float, point3Y: float):
        """"""
    def WritePathLineSegment(pointX: float, pointY: float):
        """"""
    def WriteRectangle(self, width: float, height: float, x: float, y: float, opacity: float, rotateZ: float, scaleX: float, scaleY: float, translateX: float, translateY: float, fillColor: int, strokeColor: int, strokeThickness: float, radiusX: float, radiusY: float):
        """"""
    def WriteViewbox(self, width: float, height: float):
        """"""
        
class VectorHudData:
    NumberOfStoryboards: int
    NumberOfTimelines: int
    NumberOfVisuals: int
    def __init__(self, tagFile: TagFile):
        pass
    def AddChildVisual(self, parent_offset: int, child_offset: int):
        """"""
    def BeginVectorHudDataWrite(self):
        """"""
    def ClearData(self):
        """"""
    def EndPath(self):
        """"""
    def EndVectorHudDataWrite(self):
        """"""
    def SetStoryboardRootVisual(self, storyboard_offset: int, root_visual_offset: int):
        """"""
    def SetTimelineAffectedVisual(self, timeline_offset: int, object_offset: int):
        """"""
    def WriteCanvas(self, width: float, height: float, x: float, y: float, opacity: float, rotateZ: float, scaleX: float, scaleY: float, translateX: float, translateY: float) -> int:
        """"""
    def WritePath(self, width: float, height: float, x: float, y: float, opacity: float, rotateZ: float, scaleX: float, scaleY: float, translateX: float, translateY: float, fillColor: int, strokeColor: int, strokeThickness: float, boundsX: float, boundsY: float, boundsWidth: float, boundsHeight: float, stretchType: VectorartPathStretchType, is_closed: bool) -> int:
        """"""
    def WritePathBezierSegment(point1X: float, point1Y: float, point2X: float, point2Y: float, point3X: float, point3Y: float) -> int:
        """"""
    def WritePathLineSegment(pointX: float, pointY: float) -> int:
        """"""
    def WriteRealKeyframe(key_time: float, value: float) -> int:
        """"""
    def WriteRectangle(self, width: float, height: float, x: float, y: float, opacity: float, rotateZ: float, scaleX: float, scaleY: float, translateX: float, translateY: float, fillColor: int, strokeColor: int, strokeThickness: float, radiusX: float, radiusY: float) -> int:
        """"""
    def WriteStoryboard(self) -> int:
        """"""
    def WriteViewbox(self, animation_type: VectorHudAnimatedPropertyType) -> int:
        """"""
        
class GameAnimation:
    AnimationExporter = AnimationExporter
    GameAnimationNode = GameAnimationNode

class TagsNameSpace:
    CacheFile = CacheFile
    CacheFileHeaderInfo = CacheFileHeaderInfo
    FunctionEditorParameter = FunctionEditorParameter
    FunctionEditorSerialized = FunctionEditorSerialized
    GameBitmap = GameBitmap
    GameDesignerZoneInfo = GameDesignerZoneInfo
    GameRenderGeometry = GameRenderGeometry
    GameRenderGeometryInfo = GameRenderGeometryInfo
    GameRenderMaterialInfo = GameRenderMaterialInfo
    GameRenderModel = GameRenderModel
    GameRenderModelBitmapInfo = GameRenderModelBitmapInfo
    GameRenderModelInfo = GameRenderModelInfo
    GameRenderModelVariationInfo = GameRenderModelVariationInfo
    GameScenario = GameScenario
    ITagElementCollection = ITagElementCollection
    ITagElementContainer = ITagElementContainer
    ITagFieldInlined = ITagFieldInlined
    ITagFieldSelector = ITagFieldSelector
    ITagFieldSerializable = ITagFieldSerializable
    ObjectFunctionStringEditor = ObjectFunctionStringEditor
    PolyartImporterMB = PolyartImporterMB
    TagAlternateStream = TagAlternateStream
    TagElement = TagElement
    TagElementDefinition = TagElementDefinition
    TagField = TagField
    TagFieldArray = TagFieldArray
    TagFieldArrayElement = TagFieldArrayElement
    TagFieldBlock = TagFieldBlock
    TagFieldBlockElement = TagFieldBlockElement
    TagFieldBlockElementCollection = TagFieldBlockElementCollection
    TagFieldBlockFlags = TagFieldBlockFlags
    TagFieldBlockIndex = TagFieldBlockIndex
    TagFieldCustom = TagFieldCustom
    TagFieldCustomAuthoredLightProbe = TagFieldCustomAuthoredLightProbe
    TagFieldCustomCinematicDynamicLight = TagFieldCustomCinematicDynamicLight
    TagFieldCustomCinematicFrame = TagFieldCustomCinematicFrame
    TagFieldCustomCinematicLoopScene = TagFieldCustomCinematicLoopScene
    TagFieldCustomCinematicLoopShot = TagFieldCustomCinematicLoopShot
    TagFieldCustomCinematicPlayback = TagFieldCustomCinematicPlayback
    TagFieldCustomCinematicShotFlags = TagFieldCustomCinematicShotFlags
    TagFieldCustomCinematicVMFLight = TagFieldCustomCinematicVMFLight
    TagFieldCustomEditorCommand = TagFieldCustomEditorCommand
    TagFieldCustomFunctionEditor = TagFieldCustomFunctionEditor
    TagFieldCustomHologramLight = TagFieldCustomHologramLight
    TagFieldCustomScenarioAndZoneSet = TagFieldCustomScenarioAndZoneSet
    TagFieldCustomSlider = TagFieldCustomSlider
    TagFieldCustomTagGroupTemplate = TagFieldCustomTagGroupTemplate
    TagFieldCustomToolCommand = TagFieldCustomToolCommand
    TagFieldData = TagFieldData
    TagFieldDefinition = TagFieldDefinition
    TagFieldElement = TagFieldElement
    TagFieldElementArray = TagFieldElementArray
    TagFieldElementArrayInteger = TagFieldElementArrayInteger
    TagFieldElementArraySingle = TagFieldElementArraySingle
    TagFieldElementInteger = TagFieldElementInteger
    TagFieldElementLongString = TagFieldElementLongString
    TagFieldElementOldStringID = TagFieldElementOldStringID
    TagFieldElementSingle = TagFieldElementSingle
    TagFieldElementString = TagFieldElementString
    TagFieldElementStringID = TagFieldElementStringID
    TagFieldElementStringIDWithMenu = TagFieldElementStringIDWithMenu
    TagFieldElementStringNormal = TagFieldElementStringNormal
    TagFieldElementTag = TagFieldElementTag
    TagFieldElementUnsignedInteger = TagFieldElementUnsignedInteger
    TagFieldEnum = TagFieldEnum
    TagFieldExplanation = TagFieldExplanation
    TagFieldFlags = TagFieldFlags
    TagFieldInterop = TagFieldInterop
    TagFieldNameInfo = TagFieldNameInfo
    TagFieldPath = TagFieldPath
    TagFieldReference = TagFieldReference
    TagFieldResource = TagFieldResource
    TagFieldStringMenu = TagFieldStringMenu
    TagFieldStringMenuItem = TagFieldStringMenuItem
    TagFieldStruct = TagFieldStruct
    TagFieldStructElement = TagFieldStructElement
    TagFieldVertexBuffer = TagFieldVertexBuffer
    TagFile = TagFile
    TagFileElement = TagFileElement
    TagGroupType = TagGroupType
    TagLoadException = TagLoadException
    TagPath = TagPath
    TagReference = TagReference
    TagReferenceDefinition = TagReferenceDefinition
    TagSaveException = TagSaveException
    TagSoundPlayFraction = TagSoundPlayFraction
    TagSoundPlayFractionCollection = TagSoundPlayFractionCollection
    TagSystem = TagSystem
    TagTemplate = TagTemplate
    TagTemplateCategory = TagTemplateCategory
    TagTemplateLayout = TagTemplateLayout
    TagTemplateMenu = TagTemplateMenu
    TagTemplateMenuItem = TagTemplateMenuItem
    TagTemplateParameter = TagTemplateParameter
    TagTemplateParameterHelp = TagTemplateParameterHelp
    TagUnitTest = TagUnitTest
    TagValue = TagValue
    TagValueArrayInteger = TagValueArrayInteger
    TagValueArraySingle = TagValueArraySingle
    TagValueCustom = TagValueCustom
    TagValueCustomFunctionEditor = TagValueCustomFunctionEditor
    TagValueCustomToolCommand = TagValueCustomToolCommand
    TagValueEnum = TagValueEnum
    TagValueEnumItem = TagValueEnumItem
    TagValueExplanation = TagValueExplanation
    TagValueFlagItem = TagValueFlagItem
    TagValueFlags = TagValueFlags
    TagValueInteger = TagValueInteger
    TagValueReference = TagValueReference
    TagValueSimple = TagValueSimple
    TagValueSimpleArray = TagValueSimpleArray
    TagValueSingle = TagValueSingle
    TagValueString = TagValueString
    TagValueStringID = TagValueStringID
    TagValueStringIDWithMenu = TagValueStringIDWithMenu
    TagValueStringLong = TagValueStringLong
    TagValueStringNormal = TagValueStringNormal
    TagValueUnsignedInteger = TagValueUnsignedInteger
    VectorartImporterMB = VectorartImporterMB
    VectorHudData = VectorHudData
    def __init__(self):
        pass