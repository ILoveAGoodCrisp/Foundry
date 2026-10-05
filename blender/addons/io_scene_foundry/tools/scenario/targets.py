"""Shared child-scenario routing for scenario authoring."""
from contextlib import contextmanager, ExitStack
from pathlib import Path

from ...tags.scenario import ScenarioDocument
from ...tags.scenario_objects import supports_child_scenarios
from ...tags.scenario_markers import block_definition


def child_target(main_path, child_name, game):
    main_path = Path(main_path)
    child_name = child_name.strip()
    if not child_name:
        return main_path
    if not supports_child_scenarios(game):
        raise ValueError(f'{game} does not support child scenario authoring')
    name = child_name.removesuffix('.scenario')
    if not name or name in {'.', '..'} or any(c in name for c in '/\\:*?"<>|'):
        raise ValueError('Child scenario must be a file name in the asset scenario folder')
    target = main_path.with_name(name + '.scenario')
    if target.name.casefold() == main_path.name.casefold():
        raise ValueError('Child scenario cannot be the asset scenario itself')
    return target


@contextmanager
def scenario_targets(objects, *, scenario_path, tags_root, game, default_child='', include_existing_children=False):
    """Validate all targets before yielding; commit tags only after all writes succeed."""
    scenario_path = (Path(tags_root) / scenario_path).resolve().relative_to(Path(tags_root).resolve())
    grouped = {scenario_path: []}
    for ob in objects:
        target = child_target(scenario_path, getattr(ob.nwo, 'scenario_child_scenario', '') or default_child, game)
        grouped.setdefault(target, []).append(ob)
    with ExitStack() as stack:
        parent = stack.enter_context(ScenarioDocument(scenario_path, tags_root=tags_root, game=game, must_exist=True))
        if parent.read_only:
            raise RuntimeError('Cannot export during a read-only tag operation')
        parent.authoring_context = parent
        children_name = 'child scenario' if game == 'halo1' else 'tag'
        documents = {scenario_path: parent}
        if supports_child_scenarios(game) and include_existing_children:
            def read_children(owner):
                for row in owner.block(owner.tag.root(), 'child scenarios'):
                    ref = owner.reference(row, children_name)
                    if ref is None:
                        continue
                    target = Path(ref.RelativePathWithExtension)
                    if target.parent != scenario_path.parent or target in documents:
                        continue
                    child = stack.enter_context(ScenarioDocument(target, tags_root=tags_root, game=game, must_exist=True))
                    child.authoring_context = owner
                    documents[target] = child
                    grouped.setdefault(target, [])
                    read_children(child)
            read_children(parent)
        for target in grouped:
            if target in documents:
                continue
            child = stack.enter_context(ScenarioDocument(target, tags_root=tags_root, game=game))
            child.authoring_context = parent
            documents[target] = child
            references = parent.block(parent.tag.root(), 'child scenarios')
            if not any((ref := parent.reference(row, children_name)) is not None and
                       Path(ref.RelativePathWithExtension) == target for row in references):
                if len(references) >= block_definition(game, 'child scenarios')['max_count']:
                    raise ValueError('Too many child scenarios')
                index = references.add()
                parent.set_reference(parent.block(parent.tag.root(), 'child scenarios')[index], children_name, target)
        yield [(documents[target], objects_) for target, objects_ in grouped.items()]
