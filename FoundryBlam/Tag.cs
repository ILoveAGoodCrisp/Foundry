using Bungie;
using Bungie.Tags;
using System;
using System.IO;

namespace FoundryBlam
{
    public class Tag : IDisposable
    {
        protected string tagExt = "";
        protected bool tagHasChanges = false;
        protected string relativePath = "";
        protected TagFile tag;
        protected TagPath tagPath;

        public Tag(string path)
        {
            tagPath = TagPathFromString(path);
            tag = new TagFile();

            if (tagPath.IsTagFileAccessible())
            {
                tag.Load(tagPath);
            }
            else
            {
                tag.New(tagPath);
            }
        }

        public void Dispose()
        {
            if (tag != null)
            {
                if (tagHasChanges)
                {
                    tag.Save();
                }
                tag.Dispose();
            }
        }

        public TagPath TagPathFromString(string path)
        {
            if (path.StartsWith(ManagedBlamSystem.TagRootPath))
            {
                Uri fullPath = new Uri(path);
                Uri tagsDir = new Uri(ManagedBlamSystem.TagRootPath);
                Uri relativePath = fullPath.MakeRelativeUri(tagsDir);
                path = Uri.UnescapeDataString(relativePath.ToString());
            }

            string dir = Path.GetDirectoryName(path);
            string pathNoExt = Path.Combine(dir, Path.GetFileNameWithoutExtension(path));
            string ext = Path.GetExtension(path).Substring(1);

            return TagPath.FromPathAndExtension(pathNoExt, ext);
        }
    }
}
