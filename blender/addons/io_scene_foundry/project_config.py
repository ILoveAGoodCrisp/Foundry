"""Persisted editing-kit configurations, independent of Blender.

One executable root may own several independent tags/data configurations.
Paths in the settings file are root-relative when possible; runtime paths are
absolute. Display names are labels, never configuration identities.
"""
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import tempfile
from uuid import NAMESPACE_URL, uuid4, uuid5


CONFIG_VERSION = 2
KIT_CONFIG_VERSION = 1
DEFAULT_PROJECT_IMAGE = r"bin\thumbnail.jpg"
CUSTOM_DIRECTORY_GAMES = {"halo1", "halo2"}
PROJECT_FIELDS = (
    "game", "project_name", "image_path",
    "last_scenario",
)


def directory_path(root, value, default):
    path = Path(str(value or default).strip().strip('"'))
    if not path.is_absolute():
        path = Path(root) / path
    return path.expanduser().resolve()


def path_key(path):
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def stored_directory(root, directory):
    root = Path(root).expanduser().resolve()
    directory = Path(directory).expanduser().resolve()
    try:
        return str(directory.relative_to(root))
    except ValueError:
        return str(directory)


def project_image_path(root, value):
    """Keep thumbnail paths within the editing kit, including resolved links."""
    value = str(value).strip().strip('"')
    if not value:
        return ''
    root = Path(root).expanduser().resolve()
    image = directory_path(root, value, '')
    if not image.is_relative_to(root):
        raise ValueError('The project image must be inside the editing kit folder')
    return str(image.relative_to(root))


def relative_content_path(value, tags_root, data_root, legacy_names=True):
    """Resolve current paths first; keep old embedded source paths readable."""
    path = PureWindowsPath(str(value).replace('/', '\\'))
    if not path.is_absolute():
        return path if not any(part == '..' for part in path.parts) else None
    for root in (data_root, tags_root):
        if root:
            try:
                return path.relative_to(PureWindowsPath(root))
            except ValueError:
                pass
    # Embedded import information may refer to a kit on the author's machine.
    # Match configured folder names as well as the old standard folder names.
    names = {PureWindowsPath(root).name.casefold() for root in (data_root, tags_root) if root}
    names.discard('')
    if legacy_names:
        names.update(('data', 'tags'))
    for index, part in enumerate(path.parts):
        if part.casefold() in names:
            relative = PureWindowsPath(*path.parts[index + 1:])
            return relative if '..' not in relative.parts else None
    return None


def configuration_key(record):
    root = record["project_path"]
    return (
        path_key(root),
        path_key(directory_path(root, record.get("tags_directory"), "tags")),
        path_key(directory_path(root, record.get("data_directory"), "data")),
    )


def new_project_record(root, name="", tags="tags", data="data", *, use_project_thumbnail=False, **metadata):
    root = str(Path(root).expanduser().resolve())
    return {
        "id": str(uuid4()), "name": name, "project_path": root,
        "tags_directory": stored_directory(root, directory_path(root, tags, "tags")),
        "data_directory": stored_directory(root, directory_path(root, data, "data")),
        "image_path": DEFAULT_PROJECT_IMAGE,
        "use_project_thumbnail": use_project_thumbnail,
        **{key: value for key, value in metadata.items() if key in PROJECT_FIELDS},
    }


def normalize_projects(payload):
    """Read v2 or migrate the old list without discarding unavailable kits."""
    if isinstance(payload, dict):
        if payload.get("version") != CONFIG_VERSION:
            raise ValueError("Unsupported Foundry projects settings version")
        entries = payload.get("projects")
    else:
        entries = payload
    if not isinstance(entries, list):
        raise ValueError("Foundry projects settings must contain a project list")
    records, identities = [], set()
    legacy_roots = set()
    for entry in entries:
        if isinstance(entry, str):
            if path_key(entry) in legacy_roots:
                continue
            legacy_roots.add(path_key(entry))
            record = new_project_record(entry)
            record["id"] = str(uuid5(NAMESPACE_URL, "foundry:" + path_key(entry)))
        elif isinstance(entry, dict):
            if not isinstance(entry.get("project_path"), str) or not entry["project_path"]:
                raise ValueError("Project is missing its editing kit path")
            record = dict(entry)
            for field in ("name", "tags_directory", "data_directory", *PROJECT_FIELDS):
                if field in record and not isinstance(record[field], str):
                    raise ValueError(f"Project {field} must be text")
            record["project_path"] = str(Path(record["project_path"]).expanduser().resolve())
            for field, default in (("tags_directory", "tags"), ("data_directory", "data")):
                record[field] = stored_directory(record["project_path"], directory_path(
                    record["project_path"], record.get(field), default))
            record.setdefault("name", "")
            record.setdefault("id", str(uuid5(NAMESPACE_URL, "foundry:" + repr(configuration_key(record)))))
        else:
            raise ValueError("Invalid Foundry project entry")
        record.setdefault('image_path', DEFAULT_PROJECT_IMAGE)
        record.setdefault('use_project_thumbnail', False)
        if not isinstance(record['use_project_thumbnail'], bool):
            raise ValueError('Project use_project_thumbnail must be a boolean')
        if not isinstance(record["id"], str) or not record["id"] or record["id"] in identities:
            raise ValueError("Project IDs must be nonempty and unique")
        identities.add(record["id"])
        records.append(record)
    return records


def read_project_records(path):
    path = Path(path)
    if not path.exists():
        return []
    return normalize_projects(json.loads(path.read_text(encoding="utf-8")))


def read_kit_settings(path, default_name, blender_path):
    """Read only Foundry JSON metadata; engine detection belongs to Tool."""
    path = Path(path)
    values = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(values, dict) or values.get('version', KIT_CONFIG_VERSION) != KIT_CONFIG_VERSION:
        raise ValueError('Unsupported Foundry project.json settings version')
    for field in ('name', 'display_name', 'blender_path'):
        if field in values and not isinstance(values[field], str):
            raise ValueError(f'Project {field} must be text')
    return {'version': KIT_CONFIG_VERSION, 'name': values.get('name') or default_name,
            'display_name': values.get('display_name') or default_name,
            'blender_path': str(blender_path)}


def write_kit_settings(path, settings):
    path = Path(path)
    values = read_kit_settings(path, settings['name'], settings['blender_path'])
    values.update({field: settings[field] for field in ('name', 'display_name', 'blender_path')})
    if path.exists() and json.loads(path.read_text(encoding='utf-8')) == values:
        return
    _write_json(path, values)


def write_project_records(path, records):
    """Replace settings atomically, backing up the old format before migration."""
    path = Path(path)
    records = normalize_projects({"version": CONFIG_VERSION, "projects": records})
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        normalize_projects(previous)  # Never overwrite unreadable/future settings.
        if isinstance(previous, list):
            backup = path.with_name(path.name + ".legacy.bak")
            if not backup.exists():
                shutil.copy2(path, backup)
        if previous == {"version": CONFIG_VERSION, "projects": records}:
            return
    _write_json(path, {"version": CONFIG_VERSION, "projects": records})


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=4)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def project_record(project):
    root = project.project_path
    return {
        "id": project.project_id, "name": project.name, "project_path": root,
        "tags_directory": stored_directory(root, project.tags_directory),
        "data_directory": stored_directory(root, project.data_directory),
        **{field: getattr(project, field, "") for field in PROJECT_FIELDS},
        "use_project_thumbnail": getattr(project, 'use_project_thumbnail', False),
    }


def unique_project_name(name, projects):
    names = {project.name.casefold() for project in projects}
    candidate, number = name, 2
    while candidate.casefold() in names:
        candidate = f"{name} ({number})"
        number += 1
    return candidate


def matching_project(path, projects, *, data=False, preferred_id=""):
    """Choose the most specific owning folder, refusing ambiguous shared roots."""
    path = Path(path).resolve()
    matches = []
    for project in projects:
        root = Path(project.data_directory if data else project.tags_directory).resolve()
        if path.is_relative_to(root):
            matches.append((len(root.parts), project))
    if not matches:
        return None
    depth = max(depth for depth, _ in matches)
    candidates = [project for size, project in matches if size == depth]
    if len(candidates) == 1:
        return candidates[0]
    preferred = next((project for project in candidates
                      if getattr(project, "project_id", "") == preferred_id), None)
    if preferred is not None:
        return preferred
    raise ValueError("Several project configurations share this folder. Select the source project in Foundry first.")


def snapshot_project(project):
    record = project_record(project)
    return json.dumps({key: record[key] for key in (
        "project_path", "tags_directory", "data_directory", "game")}, sort_keys=True)


def resolve_scene_project(projects, project_id="", name="", snapshot=""):
    projects = list(projects)
    if project_id:
        match = next((project for project in projects if project.project_id == project_id), None)
        if match is not None:
            return match
        # A .blend from another computer can be relinked by the complete folder pair.
        try:
            record = json.loads(snapshot)
            key = configuration_key(record)
            matches = [project for project in projects
                       if configuration_key(project_record(project)) == key
                       and project.game == record.get("game")]
            return matches[0] if len(matches) == 1 else None
        except (ValueError, TypeError, KeyError, AttributeError):
            return None
    matches = [project for project in projects if project.name == name or project.project_id == name]
    return matches[0] if len(matches) == 1 else None


def content_directory_args(project, executable):
    """Only MCC H1/H2 kit executables understand these global switches."""
    if project is None or project.game not in CUSTOM_DIRECTORY_GAMES:
        return []
    executable = Path(executable)
    # Do not send kit switches to third-party editors or auxiliary programs.
    if executable.is_absolute() and path_key(executable.parent) != path_key(project.project_path):
        return []
    name = executable.stem.casefold()
    allowed = {"tool", "tool_fast", "guerilla", "sapien", "sapien_play",
               "halo_tag_test", "halo_tag_play", "halo2_tag_test", "halo2_tag_play"}
    if name not in allowed or len(executable.parts) > 1 and not executable.is_absolute():
        return []
    args = []
    if path_key(project.tags_directory) != path_key(Path(project.project_path, "tags")):
        args.extend(("-tags_dir", str(Path(project.tags_directory).resolve())))
    if not (project.game == "halo1" and name == "guerilla"):
        if path_key(project.data_directory) != path_key(Path(project.project_path, "data")):
            args.extend(("-data_dir", str(Path(project.data_directory).resolve())))
    return args
