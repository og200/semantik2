import inspect
import typing as t_
import warnings

import jinja2

from ..utils.cases import *
from ..utils.classproperty import classproperty
from ..utils.auto_importer import ModifyingTemplateParser


__all__ = ["Type"]


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

    def __repr__(cls):
        return "|Type class %s %s|" % (cls.class_name, hex(id(cls))[-4:])

    @classmethod
    def re_instantiate(mcs):
        for class_name, klass in mcs.by_class_name.items():
            if class_name in mcs.instances:
                instance = klass()
                mcs.instances[class_name] = instance

    @classmethod
    def use(mcs, class_name):
        if not isinstance(class_name, str):
            raise ValueError("class_name must be string not %r" % class_name)
        if class_name in mcs.instances:
            return mcs.instances[class_name]
        klass = mcs.by_class_name[class_name]
        instance = klass()
        mcs.instances[class_name] = instance
        return instance

    @classmethod
    def get_by_classname(mcs, item):
        return mcs.instances[item]


class Type(metaclass=TypeMetaclass):
    """
    Base class for all types

    This class represents python-backed front-end vue components.

    Class names and ids:

        - `self.class_name`: Python class name (must be unique across the application)
        - `self.tag_name`: kebab-case version of `class_name`
    """

    #
    # CLASS ATTRIBUTES (overridden)
    #

    parent: "Type" or None
    children: list["Type"]
    template: str

    @classproperty
    def class_name(self):
        """The Python class name for this component (also used to attach instances to parents)"""
        return self.__name__

    @classproperty
    def tag_name(self):
        """The name of this component in kebab-case as used in HTML tags in a vue template"""
        return pascal_to_kebab(self.class_name)

    #
    # INSTANCE ATTRIBUTES
    #

    #
    # INSTANCE METHODS
    #

    def __init__(self, parent=None, **kwargs):
        # TODO: allow subclasses of Type in type annotations

        self.parent = parent
        self.children = []

        for k in kwargs:
            if k not in self.__class__.__annotations__:
                raise ValueError(f"Unknown attribute {k} for {self.__class__.__name__}")

        for k, typ in self.__class__.__annotations__.items():
            if k in kwargs:
                v = kwargs[k]
                if typ == list[Type]:
                    if not isinstance(v, list):
                        raise ValueError(f"Expected list for {k} but got {v!r}")
                    if not all(isinstance(i, Type) for i in v):
                        raise ValueError(f"Expected list of {Type} for {k} but got {v!r}")
                    instances = [i(parent=self) for i in v]
                    setattr(self, k, instances)
                    self.children += instances
                if typ == Type:
                    instance = v(parent=self)
                    setattr(self, k, instance)
                    self.children.append(instance)
                else:
                    setattr(self, k, kwargs[k])

    def process_template(self) -> (list[str], str):
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
        rendered = template.render(self.get_template_context())

        return p.components, rendered

    def slot(self, slot_name="default"):
        """
        Render a slot in the template
        :param slot_name: name of the slot
        :param args: arguments to pass to the slot
        :param kwargs: keyword arguments to pass to the slot
        """
        to_render = getattr(self, slot_name)
        if to_render is None:
            return ""
        out = ""
        components = set()
        if isinstance(to_render, list):
            for child_type in to_render:
                new_components, rendered = child_type.process_template()
                components = components.union(new_components)
                out += rendered
        elif isinstance(to_render, Type):
            new_components, rendered = to_render.process_template()
            components = components.union(new_components)
            out += rendered
        else:
            raise TypeError(f"Expected list of Type or Type for {self!r}.{slot_name} but got {to_render!r}")

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

    @staticmethod
    def get_template_context(self):
        c = dict()
        c["t"] = self
        c["attrs"] = self.attrs
        return c

    def __repr__(self):
        return "<Type %s %s>" % (self.class_name, hex(id(self))[-4:])
