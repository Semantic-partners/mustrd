from rdflib import Graph

class MustrdRdfLib:
    def __init__(self):
        pass
    

    def execute_select(self, given, when):
        return Graph().parse(data=given).query(when).serialize(format="json").decode("utf-8")


    def execute_construct(self, given, when):
        return Graph().parse(data=given).query(when).graph
