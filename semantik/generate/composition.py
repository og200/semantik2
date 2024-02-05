import copy
from .javascript import dumps
from ..generate import code

__all__ = ["Composition"]


class Composition:
    # language=rst
    """
    Class for future support of the composition API (to replace our use of the options API)
    """

    def __init__(self):
        self.body = code.Fragment()
        self.imports = ["import * as vue from 'vue'"]
        self.exports = []

    def statement(self, statement) -> None:
        self.body += code.Statement(statement)

    def _make_const(self, name, function, *args) -> None:
        s_args = ", ".join([dumps(arg) for arg in args])
        self.statement(f"const {name} = {function}({s_args})")

    def _format_function(self, function) -> str:
        if hasattr(function, "_as_javascript"):
            return function._as_javascript()
        else:
            return function

    # Vue Reactive API

    def ref(self, name, *args):
        self._make_const(name, "ref", *args)

    def computed(self, name, *args):
        self._make_const(name, "computed", *args)

    def reactive(self, name, *args):
        self._make_const(name, "reactive", *args)

    def readonly(self, name, *args):
        self._make_const(name, "readonly", *args)

    def watchEffect(self, name, *args):
        self._make_const(name, "watchEffect", *args)

    def watchPostEffect(self, name, *args):
        self._make_const(name, "watchPostEffect", *args)

    def watchSyncEffect(self, name, *args):
        self._make_const(name, "watchSyncEffect", *args)

    def watch(self, name, *args):
        self._make_const(name, "watch", *args)

    # Vue Lifecycle API

    def lifecycle(self, name, callback):
        assert name in (
            "onMounted",
            "onUpdated",
            "onUnmounted",
            "onBeforeMount",
            "onBeforeUpdate",
            "onBeforeUnmount",
            "onErrorCaptured",
            "onRenderTracked",
            "onRenderTriggered",
            "onActivated",
            "onDeactivated",
        )
        fn = self._format_function(callback)
        self.statement(f"{name}({fn})")

    # Vue Dependency Injection API

    def provide(self, name, *args):
        self._make_const(name, "provide", *args)

    def inject(self, name, *args):
        self._make_const(name, "inject", *args)

    # Props and Emits

    def exported(self, name, expression):
        self.statement(f"{name} = {dumps(expression)}")

    def imp(self, statement):
        out = copy.deepcopy(self)
        out.imports.append(statement)
        return out

    def __call__(self, statement):
        return self.statement(statement)

    def _as_javascript(self):
        out = "function(props, {attrs, slots, emit, expose}) {\n"
        out += code.indent(self.body._as_javascript()).strip() + "\n"
        if self.exports:
            out += "  return {" + ", ".join(self.exports) + "};\n"
        out += "}\n"
        return code.indent(out)
