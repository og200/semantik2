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

    def __init__(self):
        pass

    def process_template(self) -> (list[str], str):
        """
        Process the JINJA template and return the Vue code string that results
        """
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

    @staticmethod
    def get_template_context(self):
        return dict()

    def generate(self):
        components, rendered = self.process_template()
        return rendered

    def __repr__(self):
        return "<Type %s %s>" % (self.class_name, hex(id(self))[-4:])
