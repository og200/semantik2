import inspect
import typing_utils
import typing as t_
import warnings
from pathlib import Path
from collections import ChainMap, defaultdict

import jinja2

from ..generate import code
from ..utils.cases import *
from ..utils.classproperty import classproperty
from ..utils.auto_importer import ModifyingTemplateParser


__all__ = ["Type", "Endpoint", "Composable", "GeneratingAttribute", "resolver", "generated", "slot", "DirectoryResolver"]


def all_annotations(cls) -> ChainMap:
    """Returns a dictionary-like ChainMap that includes annotations for all
    attributes defined in cls or inherited from superclasses."""
    return ChainMap(*(c.__annotations__ for c in cls.__mro__ if "__annotations__" in c.__dict__))


def resolver(func):
    """
    Decorator to register a function to resolve a tag name to an import statement
    """
    TypeMetaclass.resolvers.append(func)
    return func


def generate(location: str or Path or None = None):
    """
    Decorator to mark a class to be generated as a SFC component
    """

    def func(cls):
        TypeMetaclass.to_generate[cls] = location
        return cls

    if isinstance(location, type) and issubclass(location, Type):
        TypeMetaclass.to_generate[location] = None
        return location
    else:
        return func


class DirectoryResolver:
    """
    Resolver for a directory of components
    """

    def __init__(self, directory: str or Path):
        self.directory = Path(directory) if isinstance(directory, str) else directory
        TypeMetaclass.resolvers.append(self)

    def __call__(self, tag_name):
        if "-" in tag_name:
            kebab = tag_name
            pascal = kebab_to_pascal(tag_name)
        elif tag_name[0].isupper():
            pascal = tag_name
            kebab = pascal_to_kebab(tag_name)
        elif tag_name[0].islower():
            kebab = tag_name
            pascal = kebab_to_pascal(tag_name)
        else:
            raise ValueError(f"Cannot determine type of tag name {tag_name!r}, only kebab-case and PascalCase tags are supported.")
        for candidate in {kebab, pascal}:
            if (self.directory / f"{candidate}.vue").exists():
                return f"import {pascal} from '{self.directory / candidate}.vue'"

    def __enter__(self):
        TypeMetaclass.resolvers.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        TypeMetaclass.resolvers.remove(self)


class GeneratedResolver(DirectoryResolver):

    def __call__(self, c):
        if c in TypeMetaclass.by_tag or c in TypeMetaclass.by_class_name:
            target = TypeMetaclass.by_tag.get(c, None) or TypeMetaclass.by_class_name.get(c, None)
            if target._location:
                return f"import {c} from '{target._location}'"
            else:
                return f"import {c} from '{self.directory / target.class_name}.vue'"


class Composable:

    props: dict = {}  #: defineProps values
    setup: code.JSObject or None  #: <script setup> code
    imports: set = set()  #: set of import strings
    components: set = set()  #: components referenced in the template
    included: set = set()  #: set of other generated components that have already been included

    def __init__(self):
        self.imports = {"import * as vue from 'vue'"}
        self.setup = code.Fragment()

    def __add__(self, other: "Composable"):
        cg = Composable()
        cg += other
        return cg

    def __iadd__(self, other):
        self.props = self.props | other.props
        self.setup += other.setup
        self.imports = self.imports.union(other.imports)
        self.components = self.components.union(other.components)
        self.included = self.included.union(other.included)
        return self

    def __repr__(self):
        return (
            f"<Composable props={self.props} setup={self.setup._as_javascript() if self.setup else None!r} "
            f"imports={self.imports} components={self.components} included={self.included}>"
        )


class TypeMetaclass(type):
    """
    Metaclass for types

    This makes it easier to work with nested classes by giving each nested class an C{_order} attribute automatically representing the order in
    which the class was declared as well as providing a central registry of classes which is useful for resolving classes and automating code
    generation
    """

    by_tag = {}
    by_class_name = {}
    instances = {}
    context = {}
    in_reload = False
    resolvers: list[callable] = []  #: a list of functions to resolve a tag name and return an import statement to import the components referenced
    to_generate: dict[t_.Type["Type"], str or None] = dict()

    def __new__(mcs: t_.Type["Type"], klass_name: str, bases: tuple[t_.Type], klass_dict: dict) -> "Type":

        klass = type.__new__(mcs, klass_name, bases, klass_dict)

        class_name = klass.class_name
        tag_name = klass.tag_name

        if tag_name in mcs.by_tag:
            if not mcs.in_reload:
                warnings.warn(
                    f"Type tag names must be unique ({tag_name} in {mcs.by_tag[tag_name]!r} "
                    f"({mcs.by_tag[tag_name].__module__}) & {klass!r} in {klass.__module__})"
                )

        mcs.by_class_name[class_name] = klass
        mcs.by_tag[tag_name] = klass

        return klass

    @classmethod
    def resolve(mcs, components: set[str] or list[str]) -> set[str]:
        imports = set()
        for c in components:
            for r in mcs.resolvers:
                resolved = r(c)
                if resolved:
                    imports.add(resolved)
                    break
        return imports

    def __repr__(cls):
        return "|Type class %s %s|" % (cls.class_name, hex(id(cls))[-4:])

    @classmethod
    def get_by_classname(mcs, item):
        return mcs.instances[item]


def slot(name: str):
    """
    Class decorator that associates a contained Type class with a slot other than default
    """

    def f(cls):
        cls.slot_name = name
        return cls

    return f


class Type(metaclass=TypeMetaclass):
    """
    Base class for all types

    This class represents python-backed front-end vue components.

    Class names and ids:

        - `self.class_name`: Python class name (must be unique across the application)
        - `self.tag_name`: kebab-case version of `class_name`
    """

    slot_name: str or None
    parent: "Type" or None = None
    template: str = ""

    _location: str or Path or None = None  #: location to save the generated component (overrides default generation location)

    @classproperty
    def class_name(self):
        """The Python class name for this component (also used to attach instances to parents)"""
        return self.__name__

    @classproperty
    def tag_name(self):
        """The name of this component in kebab-case as used in HTML tags in a vue template"""
        return pascal_to_kebab(self.class_name)

    def __init__(self, parent: "Type" or t_.Type["Type"] = None):
        self.parent = parent
        ann = all_annotations(self.__class__)
        for k, a in ann.items():
            v = getattr(self, k, None)
            if a == list[Type]:
                setattr(self, k, [i(parent=self) for i in v] if v else [])
            elif a == Type:
                setattr(self, k, v(parent=self) if v else None)

        children = defaultdict(list)
        for k, v in inspect.getmembers(self.__class__, lambda o: isinstance(o, type) and issubclass(o, Type)):
            if isinstance(v, type) and issubclass(v, Type):
                slot_name = getattr(v, "slot_name", "default")
                children[slot_name].append(v(parent=self))

        for k, v in ann.items():
            if typing_utils.issubtype(v, list[Type]):
                if k in children:
                    setattr(self, k, children[k])
            elif typing_utils.issubtype(v, Type) and k != "parent":
                if k in children:
                    if len(children[k]) > 1:
                        raise ValueError(f"Expected at most one contained Type class for {self!r} but got {getattr(self, k, None)!r}")
                    setattr(self, k, children[k][0])

    def compose(self, **kwargs) -> (list[str], str):
        c = Composable()

        p = ModifyingTemplateParser(parent=self)
        p.feed(self.template)
        p.close()
        env = jinja2.Environment(
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            variable_start_string="{&",
            variable_end_string="&}",
            extensions=["jinja2.ext.i18n"],
        )
        template = jinja2.Template.from_code(env, env.compile(self.template, filename=inspect.getfile(self.__class__)), {}, None)
        rendered = template.render(self.get_template_context(composable=c) | kwargs)
        c.components = c.components.union(p.components)

        return c, rendered

    @staticmethod
    def attrs(**kwargs):
        """
        Format HTML attributes for a vue component (for use in templates)
        :param kwargs: attributes
        :return: a string of HTML attributes
        """
        out = ""
        for k, v in kwargs.items():
            if v is not None:
                out += f'{k}="{v}" '
        return out.strip()

    def get_template_context(self, composable: Composable) -> dict:
        c = dict()
        c["type"] = self
        c["attrs"] = self.attrs
        c["use"] = lambda attribute: self.use_generating_attribute(composable, attribute)
        return c

    @staticmethod
    def use_generating_attribute(composable, generating_attribute) -> t_.Any:
        new_composable, rendered = generating_attribute.compose()
        if generating_attribute not in composable.included:
            composable.included.add(generating_attribute)
            composable += new_composable
        return rendered

    def __repr__(self):
        return "<Type %s %s>" % (self.class_name, hex(id(self))[-4:])


class GeneratingAttribute:
    pass


class Endpoint(GeneratingAttribute):
    pass
