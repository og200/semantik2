import inspect
import typing_utils
import typing as t_
import warnings
from pathlib import Path
from collections import ChainMap, defaultdict

import jinja2

from . import composable
from ..generate.javascript import dumps, format_object
from ..utils.cases import *
from ..utils.classproperty import classproperty
from ..utils.auto_importer import ModifyingTemplateParser

__all__ = ["Type"]


def all_annotations(cls) -> ChainMap:
    """Returns a dictionary-like ChainMap that includes annotations for all
    attributes defined in cls or inherited from superclasses."""
    return ChainMap(*(c.__annotations__ for c in cls.__mro__ if "__annotations__" in c.__dict__))


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
    def resolve(mcs, components: set[str] or list[str]) -> dict[str, None]:
        imports = dict()
        for c in components:
            for r in mcs.resolvers:
                resolved = r(c)
                if resolved:
                    imports[resolved] = None
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
        c = composable.Composable()
        already_used = dict()

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
            undefined=jinja2.StrictUndefined,
        )
        compiled = env.compile(
            self.template, name=f"{self.__class__.__name__}", filename=inspect.getfile(self.__class__) + f"/{self.__class__.__name__}/template"
        )
        template = jinja2.Template.from_code(env, compiled, {}, None)
        context = self.get_template_context(composable=c, already_used=already_used) | kwargs
        rendered = template.render(context)
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

    def get_template_context(self, already_used, composable: composable.Composable) -> dict:
        c = dict()
        c["type"] = self
        c["attrs"] = self.attrs
        c["dumps"] = dumps
        c["format_object"] = format_object
        c["use"] = lambda renderable, **kwargs: self.use_renderable(already_used, composable, renderable, **kwargs)
        return c

    @staticmethod
    def use_renderable(already_used, composable, renderable, **kwargs) -> str:
        if renderable in already_used:
            return already_used[renderable]

        new_composable, rendered = renderable.compose(**kwargs)
        if renderable not in composable.included:
            composable.included.add(renderable)
            composable += new_composable
        already_used[renderable] = rendered
        return rendered

    def __repr__(self):
        return "<Type %s %s>" % (self.class_name, hex(id(self))[-4:])
