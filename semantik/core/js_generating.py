class JSGenerating:

    def generate(self, context: dict or None = None) -> "ComposableGeneration":
        """
        :param context:
        :return:
        """
        return


class ComposableGeneration:

    props: dict = {}
    setup: str = ""
    imports: set = set()

    def __add__(self, other: "ComposableGeneration"):
        cg = ComposableGeneration()
        cg.props = self.props + other.props
        cg.setup = self.setup + other.setup
        cg.imports = self.imports.union(other.imports)
