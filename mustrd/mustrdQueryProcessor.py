
from pyparsing import And, MatchFirst, ParseResults
from rdflib import RDF, Graph, URIRef, Variable, Literal, XSD, util, BNode
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate, Query as query_grammar, UpdateUnit as update_grammar
from rdflib.plugins.sparql.algebra import translateQuery, translateUpdate, translateAlgebra
from rdflib.plugins.sparql.sparql import Query
from rdflib.plugins.sparql.parserutils import CompValue, value, Expr, Param, Comp
from rdflib.namespace import DefinedNamespace, Namespace
from rdflib.term import Identifier
from typing import Union
from datetime import datetime

from builtins import list, set, tuple, str
from pyparsing import Optional, CaselessKeyword as Keyword, Suppress, Forward, Combine, ZeroOrMore, OneOrMore

from .sparqlserializer import serialize_component

namespace = "https://mustrd.com/query/"

# Sparql sistematically process query and update differently but in our case it would just duplicate code for nothing
all_grammar = query_grammar | update_grammar

class MustrdQueryProcessor:
    original_query : Union [Query, ParseResults]
    current_query : Union [Query, ParseResults] 
    graph : Graph
    graph_mode: bool = True

    def __init__(self, query_str: str, graph_mode: bool = True):
        # Can parse all types of query
        t1 = datetime.now()
        self.original_query = all_grammar.parseString(query_str, parseAll=True)
        print(f"Time to parse: {str(datetime.now()-t1)}")
        
        # Init original query to algebra or parsed query
        self.current_query = self.original_query
        self.graph_mode = graph_mode
        self.graph = Graph()
        
        t2 = datetime.now()
        serialized = serialize_component(self.original_query)
        print(f"Time to serialize: {str(datetime.now()-t2)}")
    
        print(serialized)
        
        if graph_mode:
            self.query_to_graph(self.original_query) 
                   
    def get_query(self):
        if self.graph_mode:
            roots = self.graph.query("SELECT DISTINCT ?sub WHERE {?sub ?prop ?obj FILTER NOT EXISTS {?s ?p ?sub}}")
            if len(roots) != 1:
                raise Exception("query graph has more than one root: invalid")
            
            for root in roots:
                new_query = self.graph_to_query(root.sub)
        else:
            new_query = self.current_query
        return serialize_component(new_query)        

    def query_to_graph(self, part: CompValue, partBnode = BNode()):
        if not part or not partBnode:
            return
        self.graph.add((partBnode, RDF.type, URIRef(namespace + type(part).__name__)))
        self.graph.add((partBnode, QUERY.has_class , Literal(str(part.__class__.__name__))))
        if isinstance(part, CompValue) or isinstance(part, ParseResults):
            self.graph.add((partBnode, QUERY.name , Literal(part.name)))
        if isinstance(part, CompValue):
            for key, sub_part in part.items():
                sub_part_bnode = BNode()
                self.graph.add((partBnode, URIRef(namespace + str(key)) , sub_part_bnode))
                self.query_to_graph(sub_part, sub_part_bnode)
        elif hasattr(part, '__iter__') and not isinstance(part, Identifier) and not isinstance(part, str):
            for sub_part in part:
                sub_part_bnode = BNode()
                self.graph.add((partBnode, QUERY.has_list , sub_part_bnode))
                self.query_to_graph(sub_part, sub_part_bnode)
        elif isinstance(part, Identifier) or isinstance(part, str):
                self.graph.add((partBnode, QUERY.has_value, Literal(part)))

    def serialize_graph(self):
        if not self.graph_mode:
            raise Exception("Not able to execute that function if graph mode is not activated: cannot work with two sources of truth")
        return self.graph.serialize(format = "ttl")
    
    def query_graph(self, meta_query: str):
        if not self.graph_mode:
            raise Exception("Not able to execute that function if graph mode is not activated: cannot work with two sources of truth")
        return self.graph.query(meta_query)
    
    def update(self, meta_query: str):
        if not self.graph_mode:
            # Implement update directly on objects: self.current_query
            pass
        return self.graph.update(meta_query)

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
        for key, value in self.graph.predicate_objects(subject):
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
