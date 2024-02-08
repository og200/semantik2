from pathlib import Path
import warnings
import re

from ..utils.cases import *
from . import type

__all__ = ["resolver", "DirectoryResolver", "GeneratedResolver"]


def resolver(func):
    """
    Decorator to register a function to resolve a tag name to an import statement
    """
    type.TypeMetaclass.resolvers.append(func)
    return func


def tag_to_file_names(tag_name):
    candidates = {tag_name}
    if "-" in tag_name:
        candidates.add(kebab_to_pascal(tag_name))
        candidates.add(tag_name.replace("-", ""))
        candidates.add(tag_name.replace("-", "").lower())
    else:
        candidates.add(pascal_to_kebab(tag_name))
        candidates.add(kebab_to_pascal(tag_name))
        candidates.add(tag_name.lower())
    return candidates


class BaseResolver:
    """
    Resolver for a collections of components
    """

    def __enter__(self):
        type.TypeMetaclass.resolvers.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        type.TypeMetaclass.resolvers.remove(self)


class DirectoryResolver(BaseResolver):
    """
    Resolver for a directory of components
    """

    def __init__(self, directory: str or Path):
        self.directory = Path(directory) if isinstance(directory, str) else directory
        self.files = {i.stem: i for i in self.directory.glob("**/*.vue")} | {i.stem: i for i in self.directory.glob("**/*.js")}
        type.TypeMetaclass.resolvers.append(self)

    def __call__(self, tag_name):
        candidates = tag_to_file_names(tag_name)
        canonical = kebab_to_pascal(tag_name) if "-" in tag_name else tag_name
        for candidate in candidates:
            if candidate in self.files:
                return f"import {canonical} from '{str(self.files[candidate])}'"


class GeneratedResolver(DirectoryResolver):

    def __call__(self, c):
        if c in type.TypeMetaclass.by_tag or c in type.TypeMetaclass.by_class_name:
            target = type.TypeMetaclass.by_tag.get(c, None) or type.TypeMetaclass.by_class_name.get(c, None)
            if target._location:
                return f"import {c} from '{target._location}'"
            else:
                return f"import {c} from '{self.directory / target.class_name}.vue'"


class DevExtremeResolver(BaseResolver):
    """
    Resolver for DevExtreme components
    """

    PAT_EXPORTS = re.compile(r"export \{(.*)}")

    def read(self):
        for file in list(self.directory.glob("**/*.js")):
            text = file.open("rt").read()
            for i in self.PAT_EXPORTS.findall(text):
                for component in [x.strip() for x in i.split(",")]:
                    cn = component.lower()
                    if not cn.startswith("dx") or "_" in cn:
                        # an export of something other than a component
                        continue
                    if cn in self.components:
                        # the component name already exists (this is an ambiguous name that appears in different .js files so we will add a prefix)
                        old_component, old_file = self.components[cn]
                        old_prefix = "Dx" + kebab_to_pascal(old_file.stem)
                        new_prefix = "Dx" + kebab_to_pascal(file.stem)
                        if old_component != old_prefix:
                            # the old component is not the canonical one, add a prefix to its entry in self.components
                            del self.components[cn]
                            self.components[old_prefix.lower() + old_component[2:].lower()] = (old_prefix + old_component[2:], old_file)
                        if component != new_prefix:
                            # the new component is not the canonical one, add a prefix to its entry in self.components
                            self.components[new_prefix.lower() + component[2:].lower()] = (component, file)
                        else:
                            # the new component *is* the canonical one so it gets to replace the old one as the one accessed with no prefix
                            self.components[cn] = (component, file)
                    else:
                        self.components[cn] = (component, file)

    def __init__(self, directory: str or Path):
        self.directory = Path(directory) if isinstance(directory, str) else directory
        type.TypeMetaclass.resolvers.append(self)
        self.components = dict()
        self.read()
        pass

    def __call__(self, tag_name):
        candidates = tag_to_file_names(tag_name)
        for candidate in candidates:
            if candidate in self.components:
                canonical, file = self.components[candidate]
                return f"import {canonical} from '{str(file)}'"
