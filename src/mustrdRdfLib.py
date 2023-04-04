from rdflib import Graph


class MustrdRdfLib:
    def __init__(self):
        pass

    def execute_select(self, given: Graph, when: str, bindings: dict = None) -> str:
        return given.query(when, initBindings=bindings).serialize(format="json").decode("utf-8")

    def execute_construct(self, given: Graph, when: str, bindings: dict = None) -> Graph:
        return given.query(when, initBindings=bindings).graph

    def execute_update(self, given: Graph, when: str, bindings: dict = None) -> Graph:
        result = given
        result.update(when, initBindings=bindings)
        return result
