"""
This type stub file was generated by pyright.
"""

xpath_tokenizer_re = ...

def xpath_tokenizer(
    pattern, namespaces=..., with_prefixes=...
):  # -> Generator[tuple[Any, LiteralString] | Any, Any, None]:
    ...
def prepare_child(next, token):  # -> Callable[..., Generator[Any, Any, None]]:
    ...
def prepare_star(next, token):  # -> Callable[..., Generator[Any, Any, None]]:
    ...
def prepare_self(next, token):  # -> Callable[..., Any]:
    ...
def prepare_descendant(next, token):  # -> Callable[..., Generator[Any, Any, None]]:
    ...
def prepare_parent(next, token):  # -> Callable[..., Generator[Any, Any, None]]:
    ...
def prepare_predicate(next, token):  # -> Callable[..., Generator[Any, Any, None]]:
    ...

ops = ...
_cache = ...

def iterfind(elem, path, namespaces=..., with_prefixes=...):  # -> Iterator[Any]:
    ...
def find(elem, path, namespaces=..., with_prefixes=...):  # -> None:
    ...
def findall(elem, path, namespaces=..., with_prefixes=...):  # -> list[Any]:
    ...
def findtext(
    elem, path, default=..., namespaces=..., with_prefixes=...
):  # -> Literal[''] | None:
    ...
