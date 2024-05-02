from rdflib.plugins.sparql.parserutils import CompValue
from rdflib.term import Identifier

from builtins import list
    
def serialize_component(component):
    
    if component == None:
        return ""
    
    if isinstance(component, Identifier):
        return f" {component.n3()} "
    elif isinstance(component, str):
        return component
    elif hasattr(component, '__iter__') and not isinstance(component, CompValue):
        serialized = ""        
        for subComponent in component:
            serialized += serialize_component(subComponent)      
        return serialized
    
    match component.name:
        case "SelectQuery":
            return f"""
SELECT {component.modifier or ''} {serialize_component(component.projection) or '*'} 
{serialize_component(component.datasetClause)}
WHERE {{ 
    {serialize_component(component.where)}  
}} 
{serialize_component(component.groupby)} 
{serialize_component(component.orderby)}
{serialize_component(component.having)}
{serialize_component(component.limitoffset)}
"""
        case "ConstructQuery":
            return f"""
CONSTRUCT {{
    {serialize_triples(component.template)} 
}} WHERE {{
    {serialize_component(component.where)} 
}}
"""
        
        case "Modify":
            return f"""
{serialize_component(component.delete)}
{serialize_component(component.insert)}
{serialize_component(component.using)}
WHERE {{
        {serialize_component(component.where)}
}}
"""
        case "SubSelect":
            return f"""
SELECT {component.modifier or ''} {serialize_component(component.projection) or '*'} 
WHERE {{ 
    {serialize_component(component.where)}  
}} {serialize_component(component.groupby)} {serialize_component(component.orderby)}
"""
        case "DeleteClause":
            return f"DELETE {{ {serialize_component(component.quads)} }}"
        case "InsertClause":
            return f"INSERT {{ {serialize_component(component.quads)} }}"
        # When Quads are not containing quads but triples
        case "Quads":
            if hasattr(component, "triples") and component.triples:
                return serialize_triples(component.triples)
        case "QuadsNotTriples":
            return f"GRAPH {component.term} {{ {serialize_triples(component.triples)} }}"
        case "PrefixDecl":
            return f"PREFIX {component.prefix}: {serialize_component(component.iri)}"
        case "DatasetClause":
            if hasattr(component, "default") and component.default:
                return f"FROM {serialize_component(component.default)}"
            elif hasattr(component, "named") and component.named:
                return f"FROM NAMED {serialize_component(component.named)}"
        case "UsingClause":
            if hasattr(component, "default") and component.default:
                return f"USING {serialize_component(component.default)}"
            elif hasattr(component, "named") and component.named:
                return f"USING NAMED {serialize_component(component.named)}"
            
        case "GroupClause":
            return f"GROUP BY {serialize_component(component.condition)}"
        case "OrderClause":
            return f"ORDER BY {serialize_component(component.condition)}"
        case "OrderCondition":
            return f"{component.order}({serialize_component(component.expr)})"
        case "LimitOffsetClauses":
            slice = ""
            if component.limit:
                slice += f"LIMIT {component.limit}"
            if component.offset:
                slice += f"OFFSET {component.offset}"
            return slice
        
        case "Aggregate_GroupConcat":
            sep = ""
            if hasattr(component, "separator") and component.separator:
                sep = f"; separator = {serialize_component(component.separator)}"
            distinct = (len(component.distinct) > 0 and component.distinct) or ""
            return f"GROUP_CONCAT({distinct} {serialize_component(component.vars)} {sep})"
        
        case "HavingClause":
            return f"HAVING({serialize_component(component.condition)})"
            
        
        case "TriplesBlock":
            return serialize_triples(component.triples)
        case "GraphGraphPattern":
            return f"GRAPH {serialize_component(component.term)} {{ {serialize_component(component.graph)} }}"
        
        case "Bind":
            return f"BIND({serialize_component(component.expr)} AS {serialize_component(component.var)})"
        # VALUES
        case "InlineData":
            return f"VALUES ({join_serialization(component.var, ' ')}) {{( {join_serialization(component.value, ') (')} )}}"
        
        case "Filter":
            return f"FILTER( {serialize_component(component.expr)} )"
        
        # Builtin function that cannot be managed in a generic way
        case "Builtin_NOTEXISTS":
            return f"NOT EXISTS {{ {serialize_component(component.graph)} }}"
        case "Builtin_EXISTS":
            return f"EXISTS {{ {serialize_component(component.graph)} }}"
        # Cannot be managed in generic way because all argument are in a list in arg. Probably because number of argument is undefined
        case "Builtin_COALESCE":
            return f"COALESCE({join_serialization(component.arg, ',')})"
        case "Builtin_CONCAT":
            return f"CONCAT({join_serialization(component.arg, ',')})"
        
        case "GroupOrUnionGraphPattern":
            return f" {{ {join_serialization(component.graph, '} UNION {')} }}"
        case "OptionalGraphPattern":
            return f"OPTIONAL {{ {serialize_component(component.graph)} }}"
        case "MinusGraphPattern":
            return f"MINUS {{ {serialize_component(component.graph)} }}"
        
        case "vars":
            if hasattr(component, "evar") and component.evar:
                return f"({serialize_component(component.expr)} AS {serialize_component(component.evar)})"
        
        # Uri written with prefix
        case "pname":
            return f" {component.prefix}:{component.localname} "
        # Translate property paths
        case "PathSequence" :
            return join_serialization(component.part, "/")
        case "PathAlternative" :
            return join_serialization(component.part, "|")
        case "PathEltOrInverse":
            return f"^{serialize_component(component.part)}"
        case "PathNegatedPropertySet":
            return f"!({join_serialization(component.part, '|')})"
        
        case "ConditionalOrExpression":
            if component.other:
                return f"({serialize_component(component.expr)} || {join_serialization(component.other, '||')})"
        case "ConditionalAndExpression":
            if component.other:
                return f"({serialize_component(component.expr)} && {join_serialization(component.other, '&&')})"
            
    if "RelationalExpression" and component.op in ("IN", "NOT IN"):
            return f"{serialize_component(component.expr)} {component.op} ({join_serialization(component.other, ',')})"
    
    # If for one reason, you cannot manage builtin like this, then define serialization before
    if "Builtin_" in component.name:
        function = component.name.split("Builtin_")[1].upper()
        return f"{function}({join_serialization(component.values(), ',')})"     
    
    # Default way to handle aggragate, if an aggragate function cannot be serialized that way, then define serialization before
    if "Aggregate_" in component.name:
        function = component.name.split("Aggregate_")[1].upper()
        return serialize_aggregate(function, component)    

    # If none of the above, there is probably no semantic at that level; we simply forward
    if isinstance(component, CompValue):
        serialized = ""        
        for subComponent in component.values():
            serialized += serialize_component(subComponent)      
        return serialized

    print("case not implemented yet")
    return ""


def serialize_aggregate(keyword: str, component):
    distinct = (len(component.distinct) > 0 and "DISTINCT") or ""
    return f"{keyword}({distinct} {serialize_component(component.vars)})"

def join_serialization(arg: list, separator: str = ""):
    if not arg:
        return ""
    return separator.join(list(map(serialize_component,arg)))

# For same subject and same subject same predicate, triples are in the same  list, that's why we use modulo to split the triples
def serialize_triples(triplegroup) : 
    serialized = ""      
    for group in triplegroup:
        for index, item in enumerate(group):
            serialized += serialize_component(item)
            # Add point and line break after triple
            if index % 3 == 2:
                serialized +=" . "
    return serialized
    