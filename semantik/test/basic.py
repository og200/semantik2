import subprocess
from pathlib import Path

from semantik.core.type import Type, Endpoint, Composable, generate, DirectoryResolver, GeneratedResolver, TypeMetaclass
from semantik.generate import code
from semantik.generate.javascript import js

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
                {& use(field) &}
            </div>
        </div>
        {% endfor %}
    </div>
    """

    def compose(self, **kwargs):
        composable, rendered = super().compose(**kwargs)
        composable.setup += code.Const(vars=["state"], value=js.vue.reactive({}))
        return composable, rendered


class FormField(Type):

    model: str
    label: str


class Input(FormField):

    model: str
    label: str
    type: str = "text"
    placeholder: str

    # language=Vue prefix=<template> suffix=</template>
    template = """
    <input v-model="{& type.model &}" type="text" placeholder="{& self.placeholder &}"/>
    """


class DropDown(FormField):

    model: str
    label: str
    items: Endpoint

    # language=Vue prefix=<template> suffix=</template>
    template = """
    <div>
        <input v-model="{& type.model &}" type="text" placeholder="Search"/>
        <ul class="sk-test-component">
            <li class="sk-test-item" v-for="item in {& use(type.items) &}">{{ item.label }}</li>
        </ul>
        <MyView/>
    </div>
    """


class VQEndpoint(Endpoint):

    def __init__(self, name, url, parameters=None):
        self.name = name
        self.url = url
        self.parameters = parameters

    def compose(self):
        c = Composable()
        c.imports = {"import { useQuery } from 'vue-query'"}
        c.setup = code.Const(
            vars=[self.name],
            value=js.useQuery(dict(queryKey=[self.name, *self.parameters.values()], queryFn=js.api.get(self.url, self.parameters))),
        )
        return c, self.name


DirectoryResolver(Path(mova2.__file__).parent / "web" / "src" / "components" / "screen")


@generate
class MyView(Form):

    class MyComponent1(Input):
        model = "field_1"
        label = "no 1"

    class MyComponent2(Input):
        model = "field_2"
        label = "no 2"

    class MyColumnPicker(DropDown):
        model = "column"
        title = "Pick a column"
        items = VQEndpoint("columns", "/api/screen/test/columns", {"search": js("search")})


def do_generate(location):

    with GeneratedResolver(location):

        for cls, target_location in TypeMetaclass.to_generate.items():

            target_location = target_location or location
            target_location.mkdir(parents=True, exist_ok=True)

            cmp = cls()

            cmp, template = cmp.compose()

            cmp.imports |= TypeMetaclass.resolve(cmp.components)

            out = ""
            out += """<script setup>\n"""
            for i in cmp.imports:
                out += i + ";\n"
            if cmp.imports:
                out += "\n"
            if cmp.props:
                pass  # TODO
            out += cmp.setup._as_javascript() if cmp.setup else ""
            out += """</script>\n"""
            out += """<template>\n"""
            out += template.strip()
            out += """\n</template>\n"""

            pretty_out = prettify(out)

            with target_location.joinpath(cls.class_name + ".vue").open("wt") as f:
                f.write(pretty_out)

            return pretty_out


def prettify(vue_code):
    command = "npx prettier --stdin-filepath file.vue"
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, err = process.communicate(input=vue_code.encode())
    output = output.decode()
    return output


if __name__ == "__main__":
    rc = do_generate(Path(mova2.__file__).parent / "web" / "src" / "generated")
    print(rc)
