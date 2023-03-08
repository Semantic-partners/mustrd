from rdflib import Graph


class MustrdRdfLib:
    def __init__(self):
        pass

    # https://github.com/Semantic-partners/mustrd/issues/50
    def execute_select(self, given, when, bindings: dict = None):
        return Graph().parse(data=given).query(when, initBindings=bindings)

    def execute_construct(self, given, when):
        return Graph().parse(data=given).query(when).graph
