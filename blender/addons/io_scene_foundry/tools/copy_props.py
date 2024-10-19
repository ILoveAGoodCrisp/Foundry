

from ..utils import all_prefixes


def CopyProps(report, template, targets):
    # Apply prefixes from template object
    template_name = template.name
    template_prefix = ""
    for prefix in all_prefixes:
        if template_name.startswith(prefix):
            template_prefix = prefix
    for ob in targets:
        if ob != template:
            target_name = ob.name
            for prefix in all_prefixes:
                target_name = target_name.replace(prefix, "")

            target_name = template_prefix + target_name
            ob.name = target_name

    # Apply halo properties to target objects
    template_props = template.nwo
    target_count = 0
    for ob in targets:
        if ob != template:
            target_count += 1
            target_props = ob.nwo

            target_props.object_type_items_all = template_props.object_type_items_all

    report(
        {"INFO"},
        f"Copied properties from {template_name} to {target_count} target objects",
    )
    return {"FINISHED"}
