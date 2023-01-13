from rdflib import Graph

class MustrdRdfLib:
    def __init__(self):
        pass

    def execute_select(self, given, when):
        listOfDict = []
        for item in Graph().parse(data=given).query(when):
            listOfDict.append(item.asdict())
        return listOfDict

    def execute_construct(self, given, when):
        return Graph().parse(data=given).query(when).graph
