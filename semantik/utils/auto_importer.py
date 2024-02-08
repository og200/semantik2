from html.parser import HTMLParser
from .html_and_view_tags import HTML_AND_VUE_TAGS

from ..utils.errors import SKTypeError


class ModifyingTemplateParser(HTMLParser):
    """
    Template parser that finds all components used in the template so we can import them and include them in .components
    """

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.components = set()  #: list of all internal components referenced by the template
        self.refs = dict()  #: dict of ref name => component instance
        self.parent = parent  #: parent component used for error reporting

    def error(self, message):
        raise SKTypeError("Error parsing template for %r: %s" % (self.parent, message))

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        tag = raw[1 : 1 + len(tag)]  # we get the tag directly from raw to retain capitalization

        if tag.lower() in HTML_AND_VUE_TAGS:
            return

        self.components.add(tag)
