using Bungie.Tags;
using System.Collections.Generic;
using System.Linq;

namespace FoundryBlam
{
    public class ScenarioStructureBspTag : Tag
    {
        protected new string tagExt = ".scenario_structure_bsp";

        public ScenarioStructureBspTag(string path) : base(path) { }

        public void WritePrefabs(List<Prefab> prefabs)
        {
            if (!is_corinth)
                return;

            TagFieldBlock prefabBlock = (TagFieldBlock)tag.SelectField("external references");
            prefabBlock.RemoveAllElements();
            foreach(Prefab prefab in prefabs)
            {
                TagElement element = prefabBlock.AddElement();
                ((TagFieldReference)element.SelectField("prefab reference")).Path = TagPathFromString(prefab.Reference);
                ((TagFieldElementStringID)element.SelectField("name")).SetStringData(prefab.Name);
                ((TagFieldElement)element.SelectField("scale")).SetStringData(prefab.Scale.ToString());
                ((TagFieldElementArray)element.SelectField("forward")).SetStringData(prefab.Forward.Select(f => f.ToString()).ToArray());
                ((TagFieldElementArray)element.SelectField("left")).SetStringData(prefab.Left.Select(f => f.ToString()).ToArray());
                ((TagFieldElementArray)element.SelectField("up")).SetStringData(prefab.Up.Select(f => f.ToString()).ToArray());
                ((TagFieldElementArray)element.SelectField("position")).SetStringData(prefab.Position.Select(f => f.ToString()).ToArray());
            }

            tagHasChanges = true;
        }
    }

    public class Prefab
    {
        public string Name { get; set; }
        public string Bsp { get; set; }
        public string Reference { get; set; }
        public float Scale { get; set; }
        public float[] Forward { get; set; }
        public float[] Left { get; set; }
        public float[] Up { get; set; }
        public float[] Position { get; set; }
        public bool NotInLightProbes { get; set; }
        public bool RenderOnly { get; set; }
        public bool AOE { get; set; }
        public bool DecalSpacing { get; set; }
        public bool Shadow { get; set; }
        public bool CinemaOnly { get; set; }
        public bool ExcludeCinema { get; set; }
        public bool DisallowLighting { get; set; }
        public int Pathfinding { get; set; }
        public int LightMapping { get; set; }
        public int Imposter { get; set; }
        public float ImposterTransition { get; set; }
        public float ImposterBrightness { get; set; }
    }

}
