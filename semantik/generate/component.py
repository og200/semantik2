"""
Generate a control from a Type instance
"""


class ComposableComponent:
    template: str = ""
    props: list = []
    setup: str = ""
    imports: set = {}

    def __add__(self, other):
        cc = ComposableComponent()
        cc.template = self.template + other.template
        cc.props = self.props + other.props
        cc.setup = self.setup + other.setup
        cc.imports = self.imports.union(other.imports)
        return cc

    def __or__(self, other):
        cc = ComposableComponent()
        cc.props = self.props + other.props
        cc.setup = self.setup + other.setup
        cc.imports = self.imports.union(other.imports)
        return cc
