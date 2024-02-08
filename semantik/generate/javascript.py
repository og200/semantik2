import datetime
import json
from . import encoder

__all__ = ["js", "format_object", "string_or_js"]


_encoder = None


def dumps(o):
    global _encoder
    if not _encoder:
        _encoder = encoder.JSONEncoder()
    if hasattr(o, "_as_javascript"):
        return o._as_javascript()  # test here for performance
    return _encoder.encode(o)


def indent_string(s, i="  "):
    out = ""
    for line in s.split("\n"):
        out += i + line + "\n"
    if not s.endswith("\n") and out:
        return out[:-1]
    return out


def format_object(o, indent="", nl="\n"):
    if hasattr(o, "_as_javascript"):
        return o._as_javascript()
    s = "{" + nl
    for k, v in o.items():
        if k.isidentifier():
            ks = k
        else:
            ks = dumps(k)
        if isinstance(v, dict):
            s += indent + ("  " if nl else "") + "%s: %s,%s" % (ks, format_object(v, indent=indent + "  "), nl or " ")
        else:
            vs = dumps(v)
            if vs == k == ks:
                s += indent + ("  " if nl else "") + "%s,%s" % (indent_string(ks, indent + "  ").lstrip(), nl or " ")
            else:
                s += indent + ("  " if nl else "") + "%s: %s,%s" % (ks, indent_string(vs, indent + "  ").lstrip(), nl or " ")
    if o:
        s = s[:-2] + nl
    s += indent + "}"
    if len(s) < 50 and nl:
        return format_object(o, indent="", nl="")
    return s


def _json_handler(o):
    if isinstance(o, datetime.datetime):
        if o.tzinfo:
            return "new Date(%s)" % o.isoformat()
        else:
            return "new Date(%s)" % (o.isoformat() + "Z")
    elif isinstance(o, datetime.date):
        return "new Date(%s)" % o.isoformat()
    elif hasattr(o, "_as_javascript"):
        return o._as_javascript()


class Op(object):
    _is_javascript_op = True  # needed to allow context.py to identify Op objects without circular imports

    @property
    def _is_js_this(self):
        return getattr(self._p_remote, "_is_js_this", False)

    @property
    def _is_js_state(self):
        return getattr(self._p_remote, "_is_js_state", False)

    def __init__(self, remote):
        self.__dict__["_p_queued"] = False
        self.__dict__["_p_remote"] = remote

    def __hash__(self):
        return id(self)

    def __call__(self, *args):
        return CallOp(self._p_remote, self, args)

    def __getattr__(self, k):
        if k.startswith("_d_"):
            k = "$" + k[3:]
        return DotOp(self._p_remote, self, k)

    def __setattr__(self, k, v):
        self.__dict__["_p_queued"] = True
        return self._p_remote._queue(DotOp(self._p_remote, self, k)._do_simple_operation("=", v))

    def __getitem__(self, k):
        return IndexOp(self._p_remote, self, k)

    def __setitem__(self, k, v):
        return SetOp(self._p_remote, IndexOp(self._p_remote, self, k), v)

    def __len__(self):
        return self.length

    def __nonzero__(self):
        return True

    def __bool__(self):
        return True

    def __lshift__(self, v):
        """
        Repurposing the left-shift (<<) operator to do bindings
        """
        return SetOp(self._p_remote, self, v)

    def __rshift__(self, operand):
        """
        Repurposing the right-shift (>>) operator and or (|) to do conditionals
        """
        return IfOp(remote=self._p_remote, condition=self, then_=operand)

    def __invert__(self):
        return UnaryPrefixOp(self._p_remote, self, "!")

    def __iadd__(self, v):
        return self._do_simple_operation("+=", v)

    def __isub__(self, v):
        return self._do_simple_operation("-=", v)

    def __imul__(self, v):
        return self._do_simple_operation("*=", v)

    def __idiv__(self, v):
        return self._do_simple_operation("/=", v)

    def __imod__(self, v):
        return self._do_simple_operation("%=", v)

    def __ilshift__(self, v):
        return self._do_simple_operation("<<=", v)

    def __irshift__(self, v):
        return self._do_simple_operation(">>=", v)

    def __ipow__(self, v):
        return self._do_simple_operation("**=", v)

    def __ior__(self, v):
        return self._do_simple_operation("||=", v)

    def __ixor__(self, v):
        return self._do_simple_operation("^^=", v)

    def __iand__(self, v):
        return self._do_simple_operation("&&=", v)

    def __neg__(self):
        return UnaryPrefixOp(self._p_remote, self, "-")

    def __pos__(self):
        return UnaryPrefixOp(self._p_remote, self, "+")

    def __add__(self, v):
        return self._do_simple_operation("+", v)

    def __sub__(self, v):
        return self._do_simple_operation("-", v)

    def __mul__(self, v):
        return self._do_simple_operation("*", v)

    def __truediv__(self, v):
        return self._do_simple_operation("/", v)

    def __floordiv__(self, v):
        return self._do_simple_operation("/", v)._do_simple_operation(">>", 0)

    def __mod__(self, v):
        return self._do_simple_operation("%", v)

    def __pow__(self, v):
        return self._do_simple_operation("**", v)

    def __or__(self, v):
        return self._do_simple_operation("||", v)

    def __xor__(self, v):
        return self._do_simple_operation("^^", v)

    def __and__(self, v):
        return self._do_simple_operation("&&", v)

    def __eq__(self, v):
        return self._do_simple_operation("===", v)

    def __ne__(self, v):
        return self._do_simple_operation("!==", v)

    def __ge__(self, v):
        return self._do_simple_operation(">=", v)

    def __le__(self, v):
        return self._do_simple_operation("<=", v)

    def __gt__(self, v):
        return self._do_simple_operation(">", v)

    def __lt__(self, v):
        return self._do_simple_operation("<", v)

    def __radd__(self, v):
        return self._do_simple_operationr("+", v)

    def __rsub__(self, v):
        return self._do_simple_operationr("-", v)

    def __rmul__(self, v):
        return self._do_simple_operationr("*", v)

    def __rdiv__(self, v):
        return self._do_simple_operationr("/", v)

    def __rmod__(self, v):
        return self._do_simple_operationr("%", v)

    def __rpow__(self, v):
        return self._do_simple_operationr("**", v)

    def __deepcopy__(self, memodict={}):
        op = JSValue(self._as_javascript())
        memodict[id(self)] = op
        return op

    def _unqueue(self):
        if self._p_queued:
            self._p_remote._unqueue(self)
            self.__dict__["_p_queued"] = False

    def _do_simple_operation(self, operator, v):
        return BinaryOp(self._p_remote, self, v, operator)

    def _do_simple_operationr(self, operator, v):
        return BinaryOp(self._p_remote, v, self, operator)

    def _as_javascript(self):
        raise ValueError("Cannot translate base operation class to js")

    def _as_update(self, v):
        raise ValueError("LHS of a << operation can only consist of . and [] operations on javascript.store [%r]" % self._as_javascript())

    def _get_children(self):
        out = []
        for k in "_p_l_operand", "_p_r_operand", "_p_operand", "_p_object", "_p_condition", "_p_then", "_p_else":
            if k in self.__dict__:
                out.append((k, self.__dict__[k]))
        return out

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self._as_javascript())

    def copy(self):
        rc = self.__class__(self._p_remote)
        rc.__dict__.update(self.__dict__)
        return rc


class NoOp(Op):
    def __init__(self, remote, obj):
        super(NoOp, self).__init__(remote)
        self.__dict__["_p_object"] = obj
        if isinstance(object, Op):
            obj._unqueue()

    def _as_javascript(self):
        return self._p_object

    def _as_update(self, v):
        if hasattr(self._p_object, "_as_update"):
            return self._p_object._as_update(v)
        else:
            if self._p_object == "state":
                return v
            else:
                return {self._p_object: v}

    def __nonzero__(self):
        return True

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_object)
        rc.__dict__.update(self.__dict__)
        return rc


class JSValue:
    def __init__(self, code):
        self.code = code

    def _as_javascript(self):
        return self.code


class UnaryOp(Op):
    def __init__(self, remote, operand):
        super(UnaryOp, self).__init__(remote)
        self.__dict__["_p_operand"] = operand
        if isinstance(operand, Op):
            operand._unqueue()

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_operand)
        rc.__dict__.update(self.__dict__)
        return rc


class UnaryPrefixOp(UnaryOp):
    def __init__(self, remote, operand, operator):
        super(UnaryOp, self).__init__(remote)
        self.__dict__["_p_operand"] = operand
        self.__dict__["_p_operator"] = operator

    def _as_javascript(self):
        self._unqueue()
        return self._p_operator + " " + dumps(self._p_operand)

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_operand, self._p_operator)
        rc.__dict__.update(self.__dict__)
        return rc


class BinaryOp(Op):
    def __init__(self, remote, l_operand, r_operand, operator):
        super(BinaryOp, self).__init__(remote)
        self.__dict__["_p_l_operand"] = l_operand
        self.__dict__["_p_r_operand"] = r_operand
        self.__dict__["_p_operator"] = operator
        if isinstance(l_operand, Op):
            l_operand._unqueue()
        if isinstance(r_operand, Op):
            r_operand._unqueue()

    def _as_javascript(self):
        self._unqueue()
        return "(%s %s %s)" % (dumps(self._p_l_operand), self._p_operator, dumps(self._p_r_operand))

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_l_operand, self._p_r_operand, self._p_operator)
        rc.__dict__.update(self.__dict__)
        return rc


class SetOp(BinaryOp):
    def __init__(self, remote, l_operand, r_operand):
        super(SetOp, self).__init__(remote, l_operand, r_operand, "=")

    def _as_update(self):
        return self._p_l_operand._as_update({"$set": self._p_r_operand})

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_l_operand, self._p_r_operand)
        rc.__dict__.update(self.__dict__)
        return rc


class DotOp(BinaryOp):
    def __init__(self, remote, l_operand, r_operand):
        super(DotOp, self).__init__(remote, l_operand, r_operand, ".")

    def _as_javascript(self):
        self._unqueue()
        return dumps(self._p_l_operand) + self._p_operator + self._p_r_operand

    def _as_update(self, v):
        return self._p_l_operand._as_update({self._p_r_operand: v})

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_l_operand, self._p_r_operand)
        rc.__dict__.update(self.__dict__)
        return rc


class CallOp(BinaryOp):
    def __init__(self, remote, l_operand, r_operand):
        super(CallOp, self).__init__(remote, l_operand, r_operand, None)
        self._p_remote._queue(self)
        self.__dict__["_p_queued"] = True

    def _as_javascript(self):
        self._unqueue()
        return "%s(%s)" % (dumps(self._p_l_operand), ",".join([dumps(i) for i in self._p_r_operand]))

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_l_operand, self._p_r_operand)
        rc.__dict__.update(self.__dict__)
        return rc


class IndexOp(BinaryOp):
    def __init__(self, remote, l_operand, r_operand):
        super(IndexOp, self).__init__(remote, l_operand, r_operand, None)

    def _as_javascript(self):
        self._unqueue()
        return "%s[%s]" % (dumps(self._p_l_operand), dumps(self._p_r_operand))

    def _as_update(self, v):
        return self._p_l_operand._as_update({self._p_r_operand: v})

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_l_operand, self._p_r_operand)
        rc.__dict__.update(self.__dict__)
        return rc


class NewOp(Op):
    def __getattr__(self, item):
        return UnaryPrefixOp(self._p_remote, JSValue(item), "new")

    def _as_javascript(self):
        if not hasattr(self, "_p_operand"):
            raise ValueError('js.new used without attribute access: usage is js.new.Date("2025-01-01")')


class _IF_OP_NV(object):
    pass


IF_OP_NV = _IF_OP_NV()


class IfOp(Op):
    def __init__(self, remote, condition, then_=IF_OP_NV, else_=IF_OP_NV):
        super(IfOp, self).__init__(remote)
        self.__dict__["_p_condition"] = condition
        self.__dict__["_p_then"] = then_
        self.__dict__["_p_else"] = else_
        for i in [condition, then_, else_]:
            if isinstance(i, Op):
                i._unqueue()

    def then_(self, v):
        if self.__dict__["_p_then"] is not IF_OP_NV:
            raise ValueError('Attempt to set the "then" element of a js conditional twice')
        self.__dict__["_p_then"] = v
        if isinstance(v, Op):
            v._unqueue()
        return self

    def else_(self, v):
        if self.__dict__["_p_else"] is not IF_OP_NV:
            raise ValueError('Attempt to set the "else" element of a js conditional twice')
        self.__dict__["_p_else"] = v
        if isinstance(v, Op):
            v._unqueue()
        return self

    def __or__(self, operand):
        return self.else_(operand)

    def _as_javascript(self):
        self._unqueue()
        if self._p_then is IF_OP_NV:
            raise ValueError("Cannot have an if without a then using x >> y | z notation")
        if self._p_else is IF_OP_NV:
            raise ValueError("Cannot have an if without an else using x >> y | z notation")

        return "(%s ? %s : %s)" % (dumps(self._p_condition), dumps(self._p_then), dumps(self._p_else))

    def copy(self):
        rc = self.__class__(self._p_remote, self._p_condition, self._p_then, self._p_else)
        rc.__dict__.update(self.__dict__)
        return rc


class JSComponent(object):
    """
    Remote Javascript gateway for a component
    """

    _is_js_this = False

    def __init__(self, comp):
        self.__dict__["_p_comp"] = comp

    def __getattr__(self, k):
        return NoOp(self, self._as_javascript() + "." + k)

    def __getitem__(self, k):
        return IndexOp(self, self, k)

    def __setattr__(self, k, v):
        return SetOp(self, getattr(self, k), v)

    def _queue(self, op):
        pass

    def _unqueue(self, op):
        pass

    def _as_javascript(self):
        return "c[%s]" % dumps(self._p_comp.uid)

    def nextTick(self, op):
        op._unqueue()
        self._queue(NoOp(self, "Vue.nextTick().then(function(){ %s }.bind(this))" % op._as_javascript()))


class JS(object):
    """
    General-purpose remote Javascript gateway
    """

    _is_js_this = False

    def __getattr__(self, k):
        return NoOp(self, k)

    def __getitem__(self, k):
        return getattr(self, k)

    def __setattr__(self, k, v):
        return SetOp(self, getattr(self, k), v)

    def var(self, k):
        return UnaryPrefixOp(self, k, "var")

    def let(self, k):
        return UnaryPrefixOp(self, k, "let")

    def debugger(self):
        pass

    @property
    def new(self):
        return NewOp(self)

    def nextTick(self):
        pass

    def if_(self, condition, then_=None, else_=None):
        return IfOp(self, condition=condition, then_=then_, else_=else_)

    def not_(self, condition):
        return UnaryPrefixOp(self, condition, "!")

    @staticmethod
    def _queue(op):
        pass

    @staticmethod
    def _unqueue(op):
        pass

    def __call__(self, k):
        return NoOp(self, k)

    @staticmethod
    def function(*args):
        return FunctionHeader(args=args)

    @staticmethod
    def arrow(*args):
        return ArrowFunctionHeader(args=args)


class FunctionHeader(object):
    def __init__(self, args):
        self.args = args

    def __call__(self, body):
        return Function(args=self.args, body=body)

    def __lshift__(self, body):
        return Function(args=self.args, body=body)

    def _as_javascript(self):
        raise ValueError("Cannot pass a function with no body into javascript (%r)" % self)

    def __repr__(self):
        return "<javascript.FunctionHeader %r>" % (",".join(self.args))


class ArrowFunctionHeader:
    def __init__(self, args):
        self.args = args

    def __lshift__(self, body):
        self.body = body
        return self

    def _as_javascript(self):
        if not self.body:
            ValueError("Cannot pass a function with no body into javascript (%r)" % self)

        if isinstance(self.body, str):
            s = self.body

        elif hasattr(self.body, "_as_javascript"):
            s = self.body._as_javascript()

        else:
            s = dumps(self.body)
            return "(%s) => (%s)" % (",".join([string_or_js(i) for i in self.args]), s)

        return "(%s) => %s" % (",".join([string_or_js(i) for i in self.args]), s)

    def __repr__(self):
        return "<javascript.ArrowFunctionHeader %r>" % (",".join([string_or_js(i) for i in self.args]))


def string_or_js(s):
    if isinstance(s, str):
        return s
    else:
        return s._as_javascript()


class Function(object):
    def __init__(self, args, body):
        self.args = args
        self.body = body
        if isinstance(body, Op):
            body._unqueue()
        self._bind = None

    def _as_javascript(self):
        if not self.body:
            ValueError("Cannot pass a function with no body into javascript (%r)" % self)
        if isinstance(self.body, str):
            s = self.body
        elif hasattr(self.body, "_as_javascript"):
            s = self.body._as_javascript()
        else:
            s = dumps(self.body)

        s = "function(%s){%s}" % (",".join([string_or_js(i) for i in self.args]), s)
        if self._bind:
            s = "(%s).bind(%s)" % (s, string_or_js(self._bind))
        return s

    def __repr__(self):
        return "<javascript.Function (%r) => {%s}>" % (",".join(self.args), string_or_js(self.body))

    def bind(self, to):
        self._bind = to
        return self


this = None

js = JS()
