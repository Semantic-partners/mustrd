from rdflib import Graph


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    if given is  None :
        return '{"results": {"bindings": []}, "head": {"vars": ["s", "p", "o"]}}'
    else:
        return given.query(when, initBindings=bindings).serialize(format="json").decode("utf-8")




def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return given.query(when, initBindings=bindings).graph


def execute_update(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    result = given
    result.update(when, initBindings=bindings)
    return result
