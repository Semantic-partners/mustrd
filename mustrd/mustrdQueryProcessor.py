
from pyparsing import ParseResults
from rdflib import RDF, Graph, URIRef, Variable, Literal, XSD, util, BNode
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from rdflib.plugins.sparql.algebra import translateQuery, translateUpdate, translateAlgebra
from rdflib.plugins.sparql.sparql import Query
from rdflib.plugins.sparql.parserutils import CompValue, value, Expr
from rdflib.namespace import DefinedNamespace, Namespace
from rdflib.term import Identifier
from typing import Union

from builtins import list, set, tuple, str


namespace = "https://mustrd.com/query/"

class MustrdQueryProcessor:
    original_query : Union [Query, ParseResults] 
    original_query : Query
    query_graph = Graph()
    is_algebra_graph: bool = False

    def __init__(self, query_str: str, is_algebra_graph: bool = False):
        parsetree = parseQuery(query_str)
        self.original_query = (is_algebra_graph and translateQuery(parsetree)) or parsetree
        self.is_algebra_graph = is_algebra_graph
        
        self.query_to_graph((is_algebra_graph and self.original_query.algebra) or parsetree._toklist, BNode())

    def query_to_graph(self, part: CompValue, partBnode):
        if not part or not partBnode:
            return
        self.query_graph.add((partBnode, RDF.type, URIRef(namespace + type(part).__name__)))
        self.query_graph.add((partBnode, QUERY.has_class , Literal(str(part.__class__.__name__))))
        if isinstance(part, CompValue) or isinstance(part, ParseResults):
            self.query_graph.add((partBnode, QUERY.name , Literal(part.name)))
        if isinstance(part, CompValue):
            for key, sub_part in part.items():
                sub_part_bnode = BNode()
                self.query_graph.add((partBnode, URIRef(namespace + str(key)) , sub_part_bnode))
                self.query_to_graph(sub_part, sub_part_bnode)
        elif hasattr(part, '__iter__') and not isinstance(part, Identifier) and not isinstance(part, str):
            for sub_part in part:
                sub_part_bnode = BNode()
                self.query_graph.add((partBnode, QUERY.has_list , sub_part_bnode))
                self.query_to_graph(sub_part, sub_part_bnode)
        elif isinstance(part, Identifier) or isinstance(part, str):
                self.query_graph.add((partBnode, QUERY.has_value, Literal(part)))

    def serialize(self):
        return self.query_graph.serialize(format = "ttl")
    
    def query(self, meta_query: str):
        return self.query_graph.query(meta_query)
    
    def update(self, meta_query: str):
        return self.query_graph.update(meta_query)
    
    def get_query(self):
        roots = self.query_graph.query("SELECT DISTINCT ?sub WHERE {?sub ?prop ?obj FILTER NOT EXISTS {?s ?p ?sub}}")
        if len(roots) != 1:
            raise Exception("query graph has more than one root: invalid")
        
        for root in roots:
            new_query = self.graph_to_query(root.sub)
        if not self.is_algebra_graph:
            new_query = ParseResults(toklist=new_query, name=self.original_query.name)
            new_query = translateQuery(new_query)
        else:
            new_query = Query(algebra=new_query, prologue=self.original_query.prologue)
        return translateAlgebra(new_query)
        
        

    def graph_to_query(self, subject):
        subject_dict = self.get_subject_dict(subject)
        if QUERY.has_class in subject_dict:
            class_name = str(subject_dict[QUERY.has_class])
            subject_dict.pop(QUERY.has_class)
            if class_name in globals():
                clazz = globals()[class_name]
                if clazz in (CompValue, Expr):
                    comp_name = str(subject_dict[QUERY.name])
                    subject_dict.pop(QUERY.name)
                    subject_dict.pop(RDF.type)
                    new_dict = dict(map(lambda kv: [str(kv[0]).replace(str(QUERY._NS), ""),
                                                    self.graph_to_query(kv[1])] ,
                                        subject_dict.items()))
                    return clazz(comp_name, **new_dict)
                elif clazz in (set, list, tuple) and QUERY.has_list in subject_dict:
                    return clazz(map(lambda item: self.graph_to_query(item), subject_dict[QUERY.has_list]))
                elif clazz == ParseResults and QUERY.has_list in subject_dict:
                    return ParseResults(toklist=list(map(lambda item: self.graph_to_query(item), subject_dict[QUERY.has_list])))
                elif clazz in (Literal, Variable, URIRef, str) and QUERY.has_value in subject_dict:
                    return clazz(str(subject_dict[QUERY.has_value]))
                        

    def get_subject_dict(self, subject):
        dict = {}
        for key, value in self.query_graph.predicate_objects(subject):
            # If key already exists: create or add to a list
            if key == QUERY.has_list:
                if key in dict:
                    dict[key].append(value)
                else:
                    dict[key] = [value]
            else:
                dict[key] = value
        return dict
    


class QUERY(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/query/")
    has_class : URIRef
    has_list : URIRef
    name : URIRef
    has_value: URIRef
