from . import javascript


__all__ = [
    "indent",
    "unp",
    "jss",
    "NOVALUE",
    "Property",
    "NamedDescriptorResolver",
    "JSObject",
    "PJS",
    "PJSItems",
    "PStrings",
    "PObject",
    "Argument",
    "Collection",
    "StringCollection",
    "Expression",
    "Statement",
    "Let",
    "Var",
    "Return",
    "Fragment",
    "Block",
    "Spacer",
    "LineComment",
    "File",
    "Class",
    "Method",
    "Import",
    "InlineIf",
    "If",
    "Function",
    "InlineFunction",
    "indentTo",
    "chainFunctions",
]

LINE = 120


def indent(s, i="  "):
    out = ""
    for line in s.split("\n"):
        out += i + line + "\n"
    return out


def indentTo(s, spaces):
    lines = s.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""
    existing = min([len(i) - len(i.lstrip()) for i in lines])
    diff = existing - spaces
    if diff > 0:
        return "\n".join(i[diff:] for i in lines)
    else:
        return s


def unp(s, force=False):
    if not s or len(s) < 2:
        return s
    if s[0] == "(" and s[-1] == ")":
        cut = s[1:-1]
        if force:
            return cut
        elif "(" not in cut and ")" not in cut:
            return cut
    return s


def jss(ob):
    """
    Utility function to translate an object into javascript
    """
    if hasattr(ob, "_as_javascript"):
        return ob._as_javascript()
    elif hasattr(ob, "gen"):
        return ob.gen()._as_javascript()
    elif isinstance(ob, str):
        return ob
    else:
        return javascript.dumps(ob)


class NOVALUE:
    pass


class Property:
    name = None

    def __init__(self, isArgument=False):
        self.isArgument = isArgument

    def __get__(self, instance, owner):
        return getattr(instance, "_" + self.name, None)

    def __set__(self, instance, value):
        setattr(instance, "_" + self.name, value)


class NamedDescriptorResolver(type):
    def __new__(cls, classname, bases, classDict):
        props = {}
        allAttrs = list(classDict.items())
        for base in bases:
            allAttrs += base.__dict__.items()
        for name, attr in allAttrs:
            if isinstance(attr, Property):
                attr.name = name
                props[name] = attr
        classDict["_props"] = props
        return type.__new__(cls, classname, bases, classDict)


class JSObject(metaclass=NamedDescriptorResolver):
    _props = {}

    def __init__(self, *args, **kwargs):
        self._children = []
        arguments = [prop for prop in self._props.values() if prop.isArgument]
        if len(args) > 0 and not len(arguments):
            raise ValueError("Arguments not supported")
        elif len(args) == 1 and arguments:
            setattr(self, arguments[0].name, args[0])
        elif len(args) > 1:
            raise ValueError("Only one argument is supported")

        for k, v in kwargs.items():
            if k not in self._props:
                raise TypeError("%s got unexpected keyword argument %r" % (self.__class__.__name__, k))
            setattr(self, k, v)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self._as_javascript())


class PJS(Property):
    pass


class PJSItems(Property):
    def __init__(self, isArgument=False):
        super(PJSItems, self).__init__(isArgument=isArgument)

    def __get__(self, instance, owner):
        if not hasattr(instance, "_" + self.name):
            setattr(instance, "_" + self.name, Collection())
        return getattr(instance, "_" + self.name)

    def __set__(self, instance, value):
        setattr(instance, "_" + self.name, Collection(value))


class PStrings(Property):
    def __init__(self, isArgument=False):
        super(PStrings, self).__init__(isArgument=isArgument)

    def __get__(self, instance, owner):
        if not hasattr(instance, "_" + self.name):
            setattr(instance, "_" + self.name, StringCollection())
        return getattr(instance, "_" + self.name)

    def __set__(self, instance, value):
        setattr(instance, "_" + self.name, StringCollection(value))


class PObject(Property):
    def __init__(self, kind, isArgument=False):
        super(PObject, self).__init__(isArgument=isArgument)
        self.kind = kind

    def __get__(self, instance, owner):
        if not hasattr(instance, "_" + self.name):
            setattr(instance, "_" + self.name, self.kind())
        return getattr(instance, "_" + self.name)

    def __set__(self, instance, value):
        setattr(instance, "_" + self.name, self.kind(value))


class Argument(JSObject):
    pass


class Collection:
    def __init__(self, *args):
        self._list = []
        for i in args:
            self.__iadd__(i)

    def __iadd__(self, other):
        if isinstance(other, Collection):
            self._list += other._list
        elif type(other) is list:
            self._list += other
        else:
            self._list.append(other)
        return self

    def insert(self, index, item):
        if isinstance(item, Collection):
            self._list = self._list[:index] + item._list + self._list[index:]
        elif isinstance(item, list):
            self._list = self._list[:index] + item + self._list[index:]
        else:
            self._list.insert(index, item)

    def __iter__(self):
        for i in self._list:
            yield i


class StringCollection(Collection):
    def __iadd__(self, other):
        if isinstance(other, Collection):
            self._list += other._list
        elif type(other) is list:
            self._list += other
        elif type(other) is tuple:
            self._list += other
        elif isinstance(other, str):
            self._list.append(other)
        elif hasattr(other, "_as_javascript"):
            self._list.append(other._as_javascript())
        else:
            raise Exception("Can only add strings")
        return self


class Expression(JSObject):
    body = Property(isArgument=True)

    def _as_javascript(self):
        return jss(self.body)


class Statement(JSObject):
    body = Property(isArgument=True)

    def _as_javascript(self):
        return unp(jss(self.body)) + ";\n"


class Let(JSObject):
    kind = "let"

    expression = Property(isArgument=True)
    vars = PJSItems()
    value = Property()

    def _as_javascript(self):
        if self.expression:
            return "%s %s;\n" % (self.kind, unp(jss(self.expression), force=True))
        else:
            return "%s %s = %s;\n" % (self.kind, (", ".join([jss(i) for i in self.vars])), jss(self.value))


class Var(Let):
    kind = "var"


class Const(Let):
    kind = "const"


class Return(Statement):
    body = Property(isArgument=True)

    def _as_javascript(self):
        if self.body:
            return "return " + super(Return, self)._as_javascript()
        else:
            return "return;\n"


class Fragment(JSObject):
    body = PJSItems(isArgument=True)

    def __iadd__(self, other):
        self.body.__iadd__(other)
        return self

    def __add__(self, other):
        return Fragment(self._as_javascript() + (other._as_javascript() if other else ""))

    def insert(self, index, value):
        self.body.insert(index, value)

    def __iter__(self):
        for i in self.body:
            yield i

    def _as_javascript(self):
        return "".join([jss(i) for i in self])


class Block(Fragment):
    def _as_javascript(self):
        return "{\n%s}" % indent(super()._as_javascript().strip())


class Spacer(JSObject):
    def _as_javascript(self):
        return "\n"


class LineComment(JSObject):
    body = Property(isArgument=True)

    def _as_javascript(self):
        return "// %s\n" % self.body


class File(Fragment):
    name = Property()

    def _as_javascript(self):
        return super(File, self)._as_javascript().strip()

    def __repr__(self):
        return "<File %s>" % self.name


class Class(Fragment):
    export = Property()
    default = Property()
    name = Property()
    extends = Property()

    def __iadd__(self, item):
        self.body += item
        return self

    def _as_javascript(self):
        bodyS = ""
        for i in self:
            iStr = i._as_javascript()
            bodyS += iStr.rstrip()
            if "\n" in iStr:
                bodyS += "\n\n"

        return "%sclass %s%s {\n\n%s\n}\n\n" % (
            ("export " if self.export else "") + ("default " if self.default else ""),
            self.name,
            " extends %s" % self.extends if self.extends else "",
            indent(bodyS.rstrip()),
        )


class Method(JSObject):
    name = Property()
    args = PStrings()
    body = PObject(Block)
    static = Property()

    def __iadd__(self, item):
        self.body.__iadd__(item)
        return self

    def _as_javascript(self):
        return "%s%s(%s) %s" % (
            "static " if self.static else "",
            jss(self.name) or "",
            ", ".join([jss(i) for i in self.args]),
            jss(self.body),
        )


class Import(JSObject):
    target = Property()
    source = Property()
    star = Property()

    def _as_javascript(self):
        source = "'%s'" % self.source
        if isinstance(self.target, set):
            target = "{%s}" % ",".join(self.target)
        else:
            target = self.target
        if self.star:
            target = "* as %s" % (self.target)
        if isinstance(self.source, str):
            s = "import %s from %s" % (target, source)
        else:
            s = "import %s from %s"
        return jss(Statement(body=s))


class InlineIf(JSObject):
    condition = Property()
    true = Property()
    false = Property()

    def _as_javascript(self):
        s = ""
        conditionS = jss(self.condition)
        trueS = falseS = ""
        if self.true is not NOVALUE:
            trueS = jss(self.true)
        if self.false is not NOVALUE:
            falseS = jss(self.false)

        if falseS:
            if len(conditionS + trueS + falseS) > LINE:
                s += "(%s) ?\n%s:\n%s" % (conditionS, indent(trueS), indent(falseS))
            else:
                s += "(%s) ? %s : %s" % (conditionS, trueS, falseS)
        else:
            if len(conditionS + trueS) > LINE:
                s += "(%s) ?\n%s" % (conditionS, indent(trueS))
            else:
                s += "(%s) ? %s" % (conditionS, trueS)
        return s


class If(InlineIf):
    condition = Property()
    true = Property()
    false = Property()

    def _as_javascript(self):
        s = ""

        conditionS = jss(self.condition)
        trueS = falseS = ""
        if self.true is not NOVALUE:
            trueS = jss(self.true)
        if self.false is not NOVALUE:
            falseS = jss(self.false)

        if falseS:
            s += "if(%s) {\n%s} else {\n%s}" % (conditionS, indent(trueS), indent(falseS))
        else:
            s += "if(%s) {\n%s}" % (conditionS, indent(trueS))
        return s


class Function(JSObject):
    name = Property()
    args = PStrings()
    body = PObject(Block)
    export = Property()
    default = Property()
    bind = Property()

    def __iadd__(self, item):
        self.body.__iadd__(item)
        return self

    def _as_javascript_ed(self):
        return ("export " if self.export else "") + ("default " if self.default else "")

    def _as_javascript(self):
        out = self._as_javascript_ed() + "function %s(%s) %s" % (
            jss(self.name) if self.name else "",
            ", ".join([jss(i) for i in self.args]),
            jss(self.body),
        )
        if self.bind:
            out = "%s.bind(%s)" % (out, jss(self.bind))
        return out


class InlineFunction(JSObject):
    args = PStrings()
    body = PObject(Expression)

    def _as_javascript(self):
        bodyS = jss(self.body)
        return "(%s)=>%s" % (", ".join([jss(i) for i in self.args]), bodyS)


def chainFunctions(*functions):
    return javascript.js(
        f"""
    function() {{ 
        const functions = [{', '.join([jss(i) for i in functions])}];
        functions.map((i) => i.bind(this).apply(arguments));
    }}"""
    )
