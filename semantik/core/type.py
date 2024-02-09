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

__all__ = ["Type", "parameter", "slot", "as_slot", "generate", "route", "NO_DEFAULT"]


def all_annotations(cls) -> ChainMap:
    """Returns a dictionary-like ChainMap that includes annotations for all
    attributes defined in cls or inherited from superclasses."""
    return ChainMap(*(c.__annotations__ for c in cls.__mro__ if "__annotations__" in c.__dict__))


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
    order = 0

    def __new__(mcs: t_.Type["Type"], klass_name: str, bases: tuple[t_.Type], klass_dict: dict) -> "Type":

        klass_dict["_order"] = mcs.order
        mcs.order += 1

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
    def resolve(mcs, components: set[str] or list[str]) -> dict[(str, Path), None]:
        out = dict()
        for c in components:
            for r in mcs.resolvers:
                resolved = r(c)
                if resolved:
                    canonical, path = resolved
                    out[canonical] = path
                    break
        return out

    def __repr__(cls):
        return "|Type class %s %s|" % (cls.class_name, hex(id(cls))[-4:])

    @classmethod
    def get_by_classname(mcs, item):
        return mcs.instances[item]


class NO_DEFAULT:
    pass


class Parameter:

    def __init__(self, required=False, default=NO_DEFAULT):
        self.required = required
        self.default = default

    def process(self, parent, value):
        if not value:
            if self.default is not NO_DEFAULT:
                return self.default
        if isinstance(value, type):
            # instantiate subclasses
            return value(parent=parent)
        else:
            return value


class Slot:

    def __init__(self, required=False, multiple=False):
        self.required = required
        self.default = multiple


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
    _route: dict[str, t_.Any] or None = None  #: details on the route to use for this component

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

        #
        # Step 1: Process parameters (type-annotated attributes marked with the Parameter annotation)
        #
        done = set()
        for k, a in ann.items():

            if not (getattr(a, "__metadata__", None) and isinstance(a.__metadata__[0], Parameter)):
                continue

            done.add(k)
            if not hasattr(self, k):
                continue
            v = getattr(self, k, NO_DEFAULT)
            processed = a.__metadata__[0].process(self, v)
            if processed is not NO_DEFAULT:
                setattr(self, k, processed)

        #
        # Step 2: Process slots (type-annotated attributes marked with the Slot annotation)
        #

        # First gather all Type classes
        children = defaultdict(list)
        for k, v in inspect.getmembers(self.__class__, lambda o: isinstance(o, type) and issubclass(o, Type)):
            if k in done:
                continue
            if isinstance(v, type) and issubclass(v, Type):
                slot_name = getattr(v, "slot_name", "default")
                children[slot_name].append(v)

        for k, a in ann.items():

            if not (getattr(a, "__metadata__", None) and isinstance(a.__metadata__[0], Slot)):
                continue

            if typing_utils.issubtype(a.__args__[0], list[Type]):
                if k in children:
                    setattr(self, k, sorted([i(parent=self) for i in children[k]], key=lambda o: o._order))
            elif typing_utils.issubtype(a.__args__[0], Type) and k != "parent":
                if k in children:
                    if len(children[k]) > 1:
                        raise ValueError(f"Expected at most one contained Type class for {self!r} but got {getattr(self, k, None)!r}")
                    setattr(self, k, children[k][0](parent=self))

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


#
# Annotated type factories and decorators
#


def parameter(typ: type, required=False, default=NO_DEFAULT):
    """Build an annotated type for a parameter"""
    return t_.Annotated[typ, Parameter(required=required, default=default)]


def slot(typ: type = list[Type], required=False, default=NO_DEFAULT):
    """Build an annotated type for a slot"""
    return t_.Annotated[typ, Slot(required=required)]


def as_slot(name: str):
    """
    Class decorator that associates a contained Type class with a slot other than default
    """

    def f(cls):
        cls.slot_name = name
        return cls

    return f


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


def route(path, name=None, before_enter=None):
    """
    Decorator to mark a class as a route
    """

    if isinstance(path, type) and issubclass(path, Type):
        cls = path
        cls._route = dict(path="/" + cls.tag_name.replace("-", "_"), name=cls.tag_name.replace("-", "_"))
        return cls

    def func(cls):
        cls._route = {k: v for k, v in dict(path=path, name=name, before_enter=before_enter).items() if v is not None}
        return cls

    return func
