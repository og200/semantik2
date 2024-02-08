import subprocess
from pathlib import Path

from ..core.type import Type, generate, TypeMetaclass
from ..core.resolve import DirectoryResolver, GeneratedResolver
from ..generate.javascript import js
from ..generate import code


def generate_code(location: Path):

    all_files = set()
    created = set()
    changed = set()
    deleted = set()
    unchanged = set()

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
                cmp.setup += code.Const(vars=["props"], value=js.defineProps(cmp.props))
            out += cmp.setup._as_javascript() if cmp.setup else ""
            out += """</script>\n"""
            out += """<template>\n"""
            out += template.strip()
            out += """\n</template>\n"""

            pretty_out = prettify(out)

            out_file = target_location.joinpath(cls.class_name + ".vue")
            all_files.add(out_file)
            if out_file.exists():
                with out_file.open("rt") as f:
                    if f.read() == pretty_out:
                        unchanged.add(out_file)
                        continue
                    else:
                        changed.add(out_file)
            else:
                created.add(out_file)

            with out_file.open("wt") as f:
                f.write(pretty_out)

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
