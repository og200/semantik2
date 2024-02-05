import datetime
from . import encoder

__all__ = ["indent_string", "format_object", "dumps", "js", "JavascriptString"]


class JavascriptString:

    js: str

    def __init__(self, js):
        self.js = js

    def _as_javascript(self):
        return self.js


def indent_string(s, i="  "):
    out = ""
    for line in s.split("\n"):
        out += i + line + "\n"
    if not s.endswith("\n") and out:
        return out[:-1]
    return out


_encoder = None


def dumps(o):
    global _encoder
    if not _encoder:
        _encoder = encoder.JSONEncoder()
    if hasattr(o, "_as_javascript"):
        return o._as_javascript()  # test here for performance
    return _encoder.encode(o)


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


def js(s: str):
    if isinstance(s, str):
        return JavascriptString(s)
    elif hasattr(s, "_as_javascript"):
        return s
    else:
        return JavascriptString(dumps(s))
