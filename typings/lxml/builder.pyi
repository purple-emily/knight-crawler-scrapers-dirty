"""
This type stub file was generated by pyright.
"""

"""
The ``E`` Element factory for generating XML documents.
"""
_QName = ...

class ElementMaker:
    """Element generator factory.

    Unlike the ordinary Element factory, the E factory allows you to pass in
    more than just a tag and some optional attributes; you can also pass in
    text and other elements.  The text is added as either text or tail
    attributes, and elements are inserted at the right spot.  Some small
    examples::

        >>> from lxml import etree as ET
        >>> from lxml.builder import E

        >>> ET.tostring(E("tag"))
        '<tag/>'
        >>> ET.tostring(E("tag", "text"))
        '<tag>text</tag>'
        >>> ET.tostring(E("tag", "text", key="value"))
        '<tag key="value">text</tag>'
        >>> ET.tostring(E("tag", E("subtag", "text"), "tail"))
        '<tag><subtag>text</subtag>tail</tag>'

    For simple tags, the factory also allows you to write ``E.tag(...)`` instead
    of ``E('tag', ...)``::

        >>> ET.tostring(E.tag())
        '<tag/>'
        >>> ET.tostring(E.tag("text"))
        '<tag>text</tag>'
        >>> ET.tostring(E.tag(E.subtag("text"), "tail"))
        '<tag><subtag>text</subtag>tail</tag>'

    Here's a somewhat larger example; this shows how to generate HTML
    documents, using a mix of prepared factory functions for inline elements,
    nested ``E.tag`` calls, and embedded XHTML fragments::

        # some common inline elements
        A = E.a
        I = E.i
        B = E.b

        def CLASS(v):
            # helper function, 'class' is a reserved word
            return {'class': v}

        page = (
            E.html(
                E.head(
                    E.title("This is a sample document")
                ),
                E.body(
                    E.h1("Hello!", CLASS("title")),
                    E.p("This is a paragraph with ", B("bold"), " text in it!"),
                    E.p("This is another paragraph, with a ",
                        A("link", href="http://www.python.org"), "."),
                    E.p("Here are some reserved characters: <spam&egg>."),
                    ET.XML("<p>And finally, here is an embedded XHTML fragment.</p>"),
                )
            )
        )

        print ET.tostring(page)

    Here's a prettyprinted version of the output from the above script::

        <html>
          <head>
            <title>This is a sample document</title>
          </head>
          <body>
            <h1 class="title">Hello!</h1>
            <p>This is a paragraph with <b>bold</b> text in it!</p>
            <p>This is another paragraph, with <a href="http://www.python.org">link</a>.</p>
            <p>Here are some reserved characters: &lt;spam&amp;egg&gt;.</p>
            <p>And finally, here is an embedded XHTML fragment.</p>
          </body>
        </html>

    For namespace support, you can pass a namespace map (``nsmap``)
    and/or a specific target ``namespace`` to the ElementMaker class::

        >>> E = ElementMaker(namespace="http://my.ns/")
        >>> print(ET.tostring( E.test ))
        <test xmlns="http://my.ns/"/>

        >>> E = ElementMaker(namespace="http://my.ns/", nsmap={'p':'http://my.ns/'})
        >>> print(ET.tostring( E.test ))
        <p:test xmlns:p="http://my.ns/"/>
    """
    def __init__(
        self, typemap=..., namespace=..., nsmap=..., makeelement=...
    ) -> None: ...
    def __call__(self, tag, *children, **attrib): ...
    def __getattr__(self, tag):  # -> partial[Any]:
        ...

E = ...