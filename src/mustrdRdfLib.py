import logging
from rdflib import Graph

class MustrdRdfLib:
    def __init__(self):
        pass

    def executeWhenAgainstGiven(self,given, when):
        return Graph().parse(data=given.value).query(when.value)