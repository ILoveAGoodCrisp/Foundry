using Bungie.Tags;

namespace FoundryBlam
{
    public class ModelTag : Tag
    {
        protected new string tagExt = ".model";

        public ModelTag(string path) : base(path) { }

        public void ModelAssignScenarioStructureLightingInfo(string lightingInfoPath)
        {
            if (!is_corinth)
                return;

            TagPath infoTagPath = TagPathFromString(lightingInfoPath);
            TagFieldReference infoField = (TagFieldReference)tag.SelectField("Lighting Info");
            if (infoField.Path != infoTagPath)
            {
                infoField.Path = infoTagPath;
                tagHasChanges = true;
            }
        }
    }
}
