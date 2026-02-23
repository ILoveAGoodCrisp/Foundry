using Bungie.Project;
using System.IO;
using System.Xml.Linq;

internal static class ProjectInfo
{
    public static string TagsRoot { get; private set; }
    public static string DataRoot { get; private set; }
    public static string ProjectRoot { get; private set; }
    public static string BlenderPath { get; private set; }

    public static bool IsValid { get; private set; }

    public static bool Initialize()
    {
        IsValid = false;

        TagsRoot = ProjectManager.GetCurrentProjectTagsRoot();
        if (string.IsNullOrWhiteSpace(TagsRoot))
            return false;

        ProjectRoot = Directory.GetParent(TagsRoot)?.FullName;
        if (string.IsNullOrWhiteSpace(ProjectRoot))
            return false;

        DataRoot = Path.Combine(ProjectRoot, "data");
        if (!Directory.Exists(DataRoot))
            return false;

        var projectXmlPath = Path.Combine(ProjectRoot, "project.xml");
        if (!File.Exists(projectXmlPath))
            return false;

        var doc = XDocument.Load(projectXmlPath);
        var blenderElement = doc.Root?.Element("blenderPath");

        BlenderPath = blenderElement?.Value.Trim().Trim('"');

        if (string.IsNullOrWhiteSpace(BlenderPath))
            return false;

        if (!File.Exists(BlenderPath))
            return false;

        IsValid = true;
        return true;
    }
}