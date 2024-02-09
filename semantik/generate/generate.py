import subprocess
import os.path
from pathlib import Path

from ..core.type import Type, generate, TypeMetaclass
from ..core.resolve import DirectoryResolver, GeneratedResolver
from ..generate.javascript import js, dumps
from ..generate import code

__all__ = ["generate_code"]


def generate_code(location: Path):

    all_files = set()
    created = set()
    changed = set()
    deleted = set()
    unchanged = set()

    def write_if_changed(file_name: Path, content: str):
        all_files.add(file_name)
        if file_name.exists():
            with file_name.open("rt") as fp:
                if fp.read() == content:
                    return unchanged.add(file_name)
                else:
                    changed.add(file_name)
        else:
            created.add(file_name)

        with file_name.open("wt") as fp:
            fp.write(content)

    with GeneratedResolver(location):

        routes = []

        routes_file = location / "routes.js"

        for cls, target_location in TypeMetaclass.to_generate.items():

            target_location = target_location or location
            target_location.mkdir(parents=True, exist_ok=True)

            cmp = cls()

            cmp, template = cmp.compose()

            imports = dict()
            for canonical, path in TypeMetaclass.resolve(cmp.components).items():
                rel_path = os.path.relpath(str(path), str(location))
                if "/" not in rel_path:
                    rel_path = "./" + rel_path
                imports[f"import {canonical} from '{rel_path}'"] = None
            cmp.imports |= imports

            out = ""
            out += """<script setup>\n"""
            for i in cmp.imports:
                out += i + ";\n"
            if cmp.imports:
                out += "\n"
            if cmp.props:
                cmp.setup += code.Const(vars=["props"], value=js.defineProps(cmp.props))
            out += cmp.setup._as_javascript() if cmp.setup else ""
            out += """</script>\n"""
            out += """<template>\n"""
            out += template.strip()
            out += """\n</template>\n"""

            pretty_out = prettify(out)

            out_file = target_location.joinpath(cls.class_name + ".vue")
            write_if_changed(out_file, pretty_out)

            if getattr(cls, "_route", None):
                desc = dict(**cls._route)
                resolved = TypeMetaclass.resolve({cls.class_name})

                fn = list(resolved.items())[0][1]
                new_path = os.path.relpath(str(fn), str(location))
                if "/" not in new_path:
                    new_path = "./" + new_path
                desc["component"] = js(f"() => import('{new_path}.vue')")
                routes.append(desc)

        pretty_out = prettify(f"export default {dumps(routes)}")
        write_if_changed(routes_file, pretty_out)

        for file in location.glob("**/*.vue"):
            if file not in all_files:
                deleted.add(file)
                file.unlink()

        return dict(created=created, changed=changed, deleted=deleted, unchanged=unchanged)


def prettify(vue_code):
    command = "npx prettier --stdin-filepath file.vue"
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, err = process.communicate(input=vue_code.encode())
    output = output.decode()
    return output
