using Bungie.Tags;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace FoundryBlam
{
    public class ScenarioStructureLightingInfoTag: Tag
    {
        protected new string tagExt = ".scenario_structure_lighting_info";
        private TagFieldBlock GenericLightDefinitions;
        private TagFieldBlock GenericLightInstances;

        public ScenarioStructureLightingInfoTag(string path, bool corinth) : base(path, corinth) { }

        public void BuildTag(List<LightInstance> lightsInstances, List<LightDefinition> lightDefinitions)
        {
            GenericLightDefinitions = (TagFieldBlock)tag.SelectField("generic light definitions");
            GenericLightInstances = (TagFieldBlock)tag.SelectField("generic light instances");

            if (!lightDefinitions.Any())
            {
                GenericLightDefinitions.RemoveAllElements();
                GenericLightInstances.RemoveAllElements();
            }
            else
            {
                if (corinth)
                {
                    WriteCorinthLightDefinitions(lightDefinitions);
                    WriteCorinthLightInstances(lightsInstances, lightDefinitions);
                }
                else
                {
                    WriteReachLightDefinitions(lightDefinitions);
                    WriteReachLightInstances(lightsInstances, lightDefinitions);
                }
            }
            tagHasChanges = true;
        }

        private void WriteCorinthLightDefinitions(List<LightDefinition> lights)
        {
            List<int> remainingLightIndexes = Enumerable.Range(0, lights.Count).ToList();
            List<int> removeIndexes = new List<int>();
            foreach (TagElement element in GenericLightDefinitions.Elements)
            {
                string elementId = ((TagFieldElementInteger)element.SelectField("Definition Identifier")).GetStringData();
                LightDefinition foundLight = lights.Find(light => light.Id == elementId);
                if (foundLight == null)
                {
                    removeIndexes.Add(element.ElementIndex);
                }
                else
                {
                    remainingLightIndexes.Remove(lights.IndexOf(foundLight));
                    UpdateCorinthLightDefinitions(foundLight, element);
                }    
            }

            if (removeIndexes.Any())
            {
                removeIndexes.Reverse();

                foreach (int i in removeIndexes)
                {
                    GenericLightDefinitions.RemoveElement(i);
                }
            }

            foreach(int i in remainingLightIndexes)
            {
                UpdateCorinthLightDefinitions(lights[i], GenericLightDefinitions.AddElement());
            }

        }

        private void UpdateCorinthLightDefinitions(LightDefinition light, TagElement element)
        {
            light.Index = element.ElementIndex;
            ((TagFieldElementInteger)element.SelectField("Definition Identifier")).SetStringData(light.Id);
            TagFieldStruct parametersStruct = (TagFieldStruct)element.SelectField("Midnight_Light_Parameters");
            TagElement parameters = parametersStruct.Elements[0];
            ((TagFieldElementStringID)parameters.SelectField("haloLightNode")).SetStringData(light.DataName);
            ((TagFieldEnum)parameters.SelectField("Light Type")).Value = light.Type;
            ((TagFieldElementArray)parameters.SelectField("Light Color")).SetStringData(light.Color.Select(f => f.ToString()).ToArray());
            TagFieldStruct intensityStruct = (TagFieldStruct)parameters.SelectField("Intensity");
            TagElement intensity = intensityStruct.Elements[0];
            TagFieldCustomFunctionEditor intensityMapping = (TagFieldCustomFunctionEditor)intensity.SelectField("Custom:Mapping");
            intensityMapping.Value.ClampRangeMin = light.Intensity;

            if (light.FarAttenuationEnd > 0)
            {
                ((TagFieldEnum)parameters.SelectField("Lighting Mode")).Value = 1; // artistic
                ((TagFieldElement)parameters.SelectField("Distance Attenuation Start")).SetStringData(light.FarAttenuationStart.ToString());
                TagFieldStruct attenStruct = (TagFieldStruct)parameters.SelectField("Distance Attenuation End");
                TagElement atten = attenStruct.Elements[0];
                TagFieldCustomFunctionEditor attenMapping = (TagFieldCustomFunctionEditor)atten.SelectField("Custom:Mapping");
                attenMapping.Value.ClampRangeMin = light.FarAttenuationEnd;
            }
            else
            {
                ((TagFieldEnum)parameters.SelectField("Lighting Mode")).Value = 0; // physically accurate
            }
            if (light.Type == 1) // SPOT
            {
                ((TagFieldElement)parameters.SelectField("Inner Cone Angle")).SetStringData(light.HotspotFalloff.ToString());
                TagFieldStruct hotspotStruct = (TagFieldStruct)parameters.SelectField("Outer Cone End");
                TagElement hotspot = hotspotStruct.Elements[0];
                TagFieldCustomFunctionEditor hotspotMapping = (TagFieldCustomFunctionEditor)hotspot.SelectField("Custom:Mapping");
                hotspotMapping.Value.ClampRangeMin = light.HotspotCutoff;
                ((TagFieldEnum)parameters.SelectField("Cone Projection Shape")).Value = light.ConeShape;
            }

            if (light.Type == 2) // SUN
                ((TagFieldEnum)element.SelectField("sun")).Value = 1;
            else
                ((TagFieldEnum)element.SelectField("sun")).Value = 0;
            // Dynamic Only
            ((TagFieldElement)parameters.SelectField("Shadow Near Clip Plane")).SetStringData(light.ShadowNearClip.ToString());
            ((TagFieldElement)parameters.SelectField("Shadow Far Clip Plane")).SetStringData(light.ShadowFarClip.ToString());
            ((TagFieldElement)parameters.SelectField("Shadow Bias Offset")).SetStringData(light.ShadowBias.ToString());
            ((TagFieldElementArray)parameters.SelectField("Shadow Color")).SetStringData(light.ShadowColor.Select(f => f.ToString()).ToArray());
            ((TagFieldEnum)parameters.SelectField("Dynamic Shadow Quality")).Value = light.ShadowQuality;
            ((TagFieldEnum)parameters.SelectField("Shadows")).Value = light.Shadows;
            ((TagFieldEnum)parameters.SelectField("Screenspace Light")).Value = light.ScreenSpace;
            ((TagFieldEnum)parameters.SelectField("Ignore Dynamic Objects")).Value = light.IgnoreDynamicObjects;
            ((TagFieldEnum)parameters.SelectField("Cinema Only")).Value = light.CinemaOnly;
            ((TagFieldEnum)parameters.SelectField("Cinema Exclude")).Value = light.CinemaExclude;
            ((TagFieldEnum)parameters.SelectField("Specular Contribution")).Value = light.SpecularContribution;
            ((TagFieldEnum)parameters.SelectField("Diffuse Contribution")).Value = light.DiffuseContribution;
            // Static Only
            ((TagFieldElement)element.SelectField("indirect amplification factor")).SetStringData(light.IndirectAmp.ToString());
            ((TagFieldElement)element.SelectField("jitter sphere radius")).SetStringData(light.JitterSphere.ToString());
            ((TagFieldElement)element.SelectField("jitter angle")).SetStringData(light.JitterAngle.ToString());
            ((TagFieldEnum)element.SelectField("jitter quality")).Value = light.JitterQuality;
            ((TagFieldEnum)element.SelectField("static analytic")).Value = light.StaticAnalytic;
        }

        private void WriteCorinthLightInstances(List<LightInstance> lights, List<LightDefinition> lightDefinitions)
        {
            GenericLightInstances.RemoveAllElements();
            foreach (LightInstance light in lights)
            {
                TagElement element = GenericLightInstances.AddElement();
                ((TagFieldElement)element.SelectField("Light Definition Index")).SetStringData(DefinitionIndexFromDataName(light.DataName, lightDefinitions).ToString());
                ((TagFieldEnum)element.SelectField("light mode")).Value = light.LightMode;
                TagFieldElementArray origin = (TagFieldElementArray)element.SelectField("origin");
                TagFieldElementArray forward = (TagFieldElementArray)element.SelectField("forward");
                TagFieldElementArray up = (TagFieldElementArray)element.SelectField("up");
                origin.SetStringData(light.Origin.Select(f => f.ToString()).ToArray());
                forward.SetStringData(light.Forward.Select(f => f.ToString()).ToArray());
                up.SetStringData(light.Up.Select(f => f.ToString()).ToArray());
            }
        }

        private void WriteReachLightDefinitions(List<LightDefinition> lights)
        {
            GenericLightDefinitions.RemoveAllElements();
            foreach (LightDefinition light in lights)
            {
                TagElement element = GenericLightDefinitions.AddElement();
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
            GenericLightInstances.RemoveAllElements();
            foreach (LightInstance light in lights)
            {
                TagElement element = GenericLightInstances.AddElement();
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

    public class LightId
    {
        public string IdFromString(string name)
        {
            var rand = new Random(GetSeed(name));
            return rand.Next(-2147483647, 2147483647).ToString();
        }

        private static int GetSeed(string name)
        {
            using (var sha256 = SHA256.Create())
            {
                byte[] hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(name));
                int seed = BitConverter.ToInt32(hash, 0);
                return seed;
            }
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
        public int LightMode { get; set; }
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
        public int ConeShape { get; set; }
        public float ShadowNearClip { get; set; }
        public float ShadowFarClip { get; set; }
        public float ShadowBias { get; set; }
        public float[] ShadowColor { get; set; }
        public int ShadowQuality { get; set; }
        public int Shadows { get; set; }
        public int ScreenSpace { get; set; }
        public int IgnoreDynamicObjects { get; set; }
        public int CinemaOnly { get; set; }
        public int CinemaExclude { get; set; }
        public int SpecularContribution { get; set; }
        public int DiffuseContribution { get; set; }
        public float IndirectAmp { get; set; }
        public float JitterSphere { get; set; }
        public float JitterAngle { get; set; }
        public int JitterQuality { get; set; }
        public int IndirectOnly { get; set; }
        public int StaticAnalytic { get; set; }
        public int Index { get; set; }
        public string Id
        {
            get
            {
                LightId lightId = new LightId();
                return lightId.IdFromString(DataName);
            }
        }
    }
}
