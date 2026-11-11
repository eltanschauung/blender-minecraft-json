"""Resolve resource identifiers against assets/<namespace>, never the process cwd."""
from pathlib import Path, PurePosixPath


def asset_layout(model_path):
    path = Path(model_path).resolve()
    for parent in path.parents:
        if parent.name == 'assets':
            return parent, path.relative_to(parent).parts[0]
    return None, None


def resolve_resource(model_path, identifier, kind='textures'):
    root, owner = asset_layout(model_path)
    suffix = '.png' if kind == 'textures' else '.json'
    explicit = ':' in identifier
    namespace, name = identifier.split(':', 1) if explicit else ('minecraft', identifier)
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name or '/' in namespace or namespace in ('.', '..'):
        raise ValueError('Unsafe resource identifier: ' + identifier)
    canonical = namespace + ':' + name
    if root:
        path = root / namespace / kind / (name + suffix)
        if path.is_file():
            return canonical, path
        # Repair unqualified exports only when an actual, unambiguous local image exists.
        if not explicit:
            local = root / owner / kind / (name + suffix)
            if local.is_file():
                return owner + ':' + name, local
            source = Path(model_path).resolve().relative_to(root / owner / 'models')
            relative = source.parent / (name + suffix)
            local = root / owner / kind / relative
            if local.is_file():
                return owner + ':' + relative.with_suffix('').as_posix(), local
        return canonical, path
    return canonical, Path(model_path).resolve().parent / (name + suffix)
