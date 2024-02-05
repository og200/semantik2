from semantik.core.type import Type
from semantik.core.js_generating import ComposableGeneration
from semantik.generate import code as c
from semantik.generate.javascript import dumps


class ViewType(Type):

    # language=Vue prefix=<template> suffix=</template>
    template = """    
    <div>
        
    </div>
    """


class ComponentType(Type):

    text: str

    def render(self):
        cg = ComposableGeneration()
        cg.setup = c.Let(vars=["text"], value=f"vue.ref({dumps(self.text)})")

    # language=Vue prefix=<template> suffix=</template>
    template = """
    <div>
        {& text &} 
    </div>
    """


class MyView(ViewType):

    class MyComponent1(ComponentType):
        pass

    class MyComponent2(ComponentType):
        pass


v = MyView()

if __name__ == "__main__":
    pass
