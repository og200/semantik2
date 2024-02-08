import subprocess
from pathlib import Path

from semantik.core.type import Type
from semantik.core.resolve import DirectoryResolver, DevExtremeResolver
from semantik.core.composable import Endpoint, Composable
from semantik.generate import code
from semantik.generate.generate import generate_code, generate
from semantik.generate.javascript import js, dumps

import mova2


class Form(Type):

    default: list[Type]
    model: str

    # language=Vue prefix=<template> suffix=</template>
    template = """    
    <div class="sk-test-form">
        {% for field in type.default %}
        <div class="sk-test-row" {& 'v-if="' + field.condition + '"' if field.condition else '' &}>
            {% if field.label %}
                <label>{& field.label &}</label>
            {% endif %}
            <div class="sk-test-field">
                {& use(field, model=type.model) &}
            </div>
            <dx-button text="Submit"/>
        </div>
        {% endfor %}
    </div>
    """

    def compose(self, **kwargs):
        composable = Composable()
        composable.props |= {self.model: js.Object}

        defaults = {}
        for field in self.default:
            defaults |= field.get_default_values()
        composable.setup += code.Const(vars=["state"], value=js.vue.reactive(defaults))
        new_composable, rendered = super().compose(**kwargs)
        c = composable + new_composable
        return c, rendered


class FormField(Type):

    model: str
    label: str = None
    condition = None

    def get_default_values(self):
        return {self.model: js.null}


class Input(FormField):

    model: str
    label: str
    type: str = "text"
    placeholder: str

    # language=Vue prefix=<template> suffix=</template>
    template = """
    <input v-model="{& parent_model &}.{& type.model &}" type="text" placeholder="{& type &}"/>
    """

    def compose(self, model=None):
        return super().compose(parent_model=model)


class DropDown(FormField):

    model: str
    label: str
    items: Endpoint

    # language=Vue prefix=<template> suffix=</template>
    template = """
    <div>
        <input v-model="state.search" type="text" placeholder="Search"/>
        <ul class="sk-test-component">
            <li class="sk-test-item" v-for="item in {& use(type.items) &}.data">{{ item.flow_name }}.{{ item.insight_name }}</li>
        </ul>
    </div>
    """

    def get_default_values(self):
        return {self.model: js.null, "search": "test"}


class VQEndpoint(Endpoint):

    def __init__(self, name, url, parameters=None):
        self.name = name
        self.url = url
        self.parameters = parameters

    def compose(self):
        c = Composable()
        c.imports = {"import { useQuery } from '@tanstack/vue-query'": None}
        c.setup = code.Fragment()
        c.setup += code.Const(vars=["api"], value=js.vue.inject("api"))
        parameters = []
        for parameter in self.parameters.values():
            parameter = parameter._as_javascript() if hasattr(parameter, "_as_javascript") else parameter
            if "." in parameter:
                index = parameter.rindex(".")
                parameters.append(getattr(js.vue.toRefs(js[parameter[:index]]), parameter[index + 1 :]))
            else:
                parameters = [i for i in self.parameters.values()]
        c.setup += code.Const(
            vars=[self.name],
            value=js.vue.reactive(
                js.useQuery(
                    dict(
                        queryKey=[self.name, *parameters],
                        queryFn=js("async () => " + js.api.get(self.url, self.parameters)._as_javascript()),
                    )
                ),
            ),
        )
        return c, self.name


DirectoryResolver(Path(mova2.__file__).parent / "web" / "src" / "components")
DirectoryResolver(Path(mova2.__file__).parent / "web" / "src" / "views")
DevExtremeResolver(Path(mova2.__file__).parent / "web" / "node_modules" / "devextreme-vue" / "esm")


@generate
class MyView(Form):

    model = "state"

    class MyComponent1(Input):
        model = "field_1"
        label = "no 1"

    class MyComponent2(Input):
        model = "field_2"
        label = "no 2"

    class MyColumnPicker(DropDown):
        model = "column"
        title = "Pick a column"
        items = VQEndpoint("columns", "/api/screen/calls/columns", {"search": js("state.search")})


if __name__ == "__main__":
    rc = generate_code(Path(mova2.__file__).parent / "web" / "src" / "generated")
    print(rc)
