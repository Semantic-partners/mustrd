import logging
from rdflib import Graph

class MustrdRdfLib:
    def __init__(self):
        pass

    def executeWhenAgainstGiven(self,given, when, queryType):
        return Graph().parse(data=given).query(when)