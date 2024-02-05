"""
Equivalent of @property at the class level
"""

__all__ = ["classproperty"]


class classproperty(object):
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)
