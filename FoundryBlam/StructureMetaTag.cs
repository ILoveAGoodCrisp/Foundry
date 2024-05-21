using Bungie.Tags;
using System.Collections.Generic;

namespace FoundryBlam
{
    public class StructureMeta : Tag
    {
        protected new string tagExt = ".structure_meta";

        public StructureMeta(string path) : base(path) { }

        public void WriteTag(List<EffectMarker> effectMarkers, List<Airprobe> airpobes, List<LightCone> lightCones, List<ScenarioObject> scenarioObjects)
        {
            if (!is_corinth)
                return;

        }
    }
}

public class EffectMarker
{
    public string Name { get; set; }
    public string Bsp { get; set; }
    public float[] Position { get; set; }
    public float[] Rotation { get; set; }
    public string Effect { get; set; }
}

public class Airprobe
{
    public string Name { get; set; }
    public string Bsp { get; set; }
    public float[] Position { get; set; }
}

public class LightCone
{
    public string Name { get; set; }
    public string Bsp { get; set; }
    public float[] Position { get; set; }
    public float[] Rotation { get; set; }
    public float Length { get; set; }
    public float Width { get; set; }
    public float Intensity { get; set; }
    public float[] Color { get; set; }
    public string Cone { get; set; }
    public string Curve { get; set; }
}

public class ScenarioObject
{
    public string Name { get; set; }
    public string Bsp { get; set; }
    public float[] Rotation { get; set; }
    public float[] Translation { get; set; }
    public float Scale { get; set; }
    public bool RunScripts { get; set; }
    public string Definition { get; set; }
    public string Variant { get; set; }
}
