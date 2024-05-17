using Bungie.Tags;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace FoundryBlam
{
    public class ScenarioStructureLightingInfoTag: Tag
    {
        protected new string tagExt = ".scenario_structure_lighting_info";
        public ScenarioStructureLightingInfoTag(string path) : base(path) { }

        public void BuildTag(List<LightInstance> lightsInstances, List<LightDefinition> lightDefinitions)
        {
            WriteReachLightDefinitions(lightDefinitions);
            WriteReachLightInstances(lightsInstances, lightDefinitions);
            tagHasChanges = true;
        }

        private void WriteReachLightDefinitions(List<LightDefinition> lights)
        {
            TagFieldBlock definitions = (TagFieldBlock)tag.SelectField("generic light definitions");
            definitions.RemoveAllElements();
            foreach (LightDefinition light in lights)
            {
                TagElement element = definitions.AddElement();
                light.Index = element.ElementIndex;
                ((TagFieldEnum)element.SelectField("type")).Value = light.Type;
                ((TagFieldEnum)element.SelectField("shape")).Value = light.Shape;
                ((TagFieldElementArray)element.SelectField("color")).SetStringData(light.Color.Select(f => f.ToString()).ToArray());
                ((TagFieldElement)element.SelectField("intensity")).SetStringData(light.Intensity.ToString());
                if (light.Type == 1) // is spot light
                {
                    ((TagFieldElement)element.SelectField("hotspot size")).SetStringData(light.HotspotSize.ToString());
                    ((TagFieldElement)element.SelectField("hotspot cutoff size")).SetStringData(light.HotspotCutoff.ToString());
                    ((TagFieldElement)element.SelectField("hotspot falloff speed")).SetStringData(light.HotspotFalloff.ToString());
                }
                string[] nearAttenuation = { light.NearAttenuationStart.ToString(), light.NearAttenuationEnd.ToString() };
                ((TagFieldElementArray)element.SelectField("near attenuation bounds")).SetStringData(nearAttenuation);

                TagFieldFlags flags = (TagFieldFlags)element.SelectField("flags");
                flags.SetBit("use far attenuation", true);
                if (light.FarAttenuationEnd > 0)
                {
                    flags.SetBit("invere squared falloff", false);
                    string[] farAttenuation = { light.FarAttenuationStart.ToString(), light.FarAttenuationEnd.ToString() };
                    ((TagFieldElementArray)element.SelectField("far attenuation bounds")).SetStringData(farAttenuation);
                }
                else
                {
                    flags.SetBit("invere squared falloff", true);
                    string[] farAttenuation = { "900", "4000" };
                    ((TagFieldElementArray)element.SelectField("far attenuation bounds")).SetStringData(farAttenuation);
                }
                ((TagFieldElement)element.SelectField("aspect")).SetStringData(light.Aspect.ToString());

            }
        }

        private void WriteReachLightInstances(List<LightInstance> lights, List<LightDefinition> lightDefinitions)
        {
            TagFieldBlock instances = (TagFieldBlock)tag.SelectField("generic light instances");
            instances.RemoveAllElements();
            foreach (LightInstance light in lights)
            {
                TagElement element = instances.AddElement();
                ((TagFieldElement)element.SelectField("definition index")).SetStringData(DefinitionIndexFromDataName(light.DataName, lightDefinitions).ToString());
                TagFieldElementArray origin = (TagFieldElementArray)element.SelectField("origin");
                TagFieldElementArray forward = (TagFieldElementArray)element.SelectField("forward");
                TagFieldElementArray up = (TagFieldElementArray)element.SelectField("up");
                origin.SetStringData(light.Origin.Select(f => f.ToString()).ToArray());
                forward.SetStringData(light.Forward.Select(f => f.ToString()).ToArray());
                up.SetStringData(light.Up.Select(f => f.ToString()).ToArray());
                ((TagFieldEnum)element.SelectField("bungie light type")).Value = light.GameType;
                TagFieldFlags flags = (TagFieldFlags)element.SelectField("screen space specular");
                flags.SetBit("screen space light has specular", light.ScreenSpaceSpecular);
                ((TagFieldElement)element.SelectField("bounce light control")).SetStringData(light.BounceRatio.ToString());
                ((TagFieldElement)element.SelectField("light volume distance")).SetStringData(light.VolumeDistance.ToString());
                ((TagFieldElement)element.SelectField("light volume intensity scalar")).SetStringData(light.VolumeIntensity.ToString());
                if (!string.IsNullOrEmpty(light.LightTag))
                    ((TagFieldReference)element.SelectField("user control")).Path = TagPathFromString(light.LightTag);
                if (!string.IsNullOrEmpty(light.Shader))
                    ((TagFieldReference)element.SelectField("shader reference")).Path = TagPathFromString(light.Shader);
                if (!string.IsNullOrEmpty(light.Gel))
                    ((TagFieldReference)element.SelectField("gel reference")).Path = TagPathFromString(light.Gel);
                if (!string.IsNullOrEmpty(light.LensFlare))
                    ((TagFieldReference)element.SelectField("lens flare reference")).Path = TagPathFromString(light.LensFlare);
            }
        }

        private int DefinitionIndexFromDataName(string name, List<LightDefinition> lightDefinitions)
        {
            foreach(LightDefinition definition in lightDefinitions)
            {
                if (name == definition.DataName)
                    return definition.Index;
            }

            return 0;
        }
    }

    public class LightInstance
    {
        public string DataName { get; set; }
        public string Bsp { get; set; }
        public float[] Origin { get; set; }
        public float[] Forward { get; set; }
        public float[] Up { get; set; }
        public int GameType { get; set; }
        public float VolumeDistance { get; set; }
        public float VolumeIntensity { get; set; }
        public float BounceRatio { get; set; }
        public bool ScreenSpaceSpecular { get; set; }
        public string LightTag { get; set; }
        public string Shader { get; set; }
        public string Gel { get; set; }
        public string LensFlare { get; set; }
    }

    public class LightDefinition
    {
        public string DataName { get; set; }
        public int Type { get; set; }
        public int Shape { get; set; }
        public float[] Color { get; set; }
        public float Intensity { get; set; }
        public float HotspotSize { get; set; }
        public float HotspotCutoff { get; set; }
        public float HotspotFalloff { get; set; }
        public float NearAttenuationStart { get; set; }
        public float NearAttenuationEnd { get; set; }
        public float FarAttenuationStart { get; set; }
        public float FarAttenuationEnd { get; set; }
        public float Aspect { get; set; }
        public int Index { get; set; }
    }
}
