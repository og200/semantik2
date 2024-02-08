from ..generate import code

__all__ = ["Composable", "GeneratingAttribute", "Endpoint"]


class Composable:

    props: dict = {}  #: defineProps values
    setup: code.JSObject or None  #: <script setup> code
    imports: dict[str, None] = dict()  #: set of import strings
    components: set = set()  #: components referenced in the template
    included: set = set()  #: set of other generated components that have already been included

    def __init__(self):
        self.imports = {"import * as vue from 'vue'": None}
        self.setup = code.Fragment()

    def __add__(self, other: "Composable"):
        cg = Composable()
        cg += self
        cg += other
        return cg

    def __iadd__(self, other):
        self.props = self.props | other.props
        self.setup += other.setup
        self.imports |= other.imports
        self.components = self.components.union(other.components)
        self.included = self.included.union(other.included)
        return self

    def __repr__(self):
        return (
            f"<Composable props={self.props} setup={self.setup._as_javascript() if self.setup else None!r} "
            f"imports={list(self.imports.keys())} components={self.components} included={self.included}>"
        )


class GeneratingAttribute:
    pass


class Endpoint(GeneratingAttribute):
    pass
