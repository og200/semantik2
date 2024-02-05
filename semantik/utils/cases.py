import re

__all__ = ["pascal_to_kebab", "kebab_to_pascal", "kebab_to_camel"]

PAT_C2K_1 = re.compile("(.)([A-Z][a-z]+)")  #: pascalToKebab pattern
PAT_C2K_2 = re.compile("([a-z0-9])([A-Z])")  #: pascalToKebab pattern


def pascal_to_kebab(name):
    """Convert from PascalCase or camelCase to kebab-case"""
    name = PAT_C2K_1.sub(r"\1-\2", name)
    return PAT_C2K_2.sub(r"\1-\2", name).lower()


def kebab_to_pascal(name):
    """Convert from kebab-case to PascalCase"""
    return "".join(word.title() for word in name.split("-"))


def kebab_to_camel(name):
    """Convert from kebab-case to PascalCase"""
    s = kebab_to_pascal(name)
    return s[0].lower() + s[1:]
