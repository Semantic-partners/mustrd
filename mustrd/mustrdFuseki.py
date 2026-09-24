"""Apache Jena Fuseki, over the SPARQL 1.1 protocols.

Endpoints sit under the dataset name: ``{url}:{port}/{dataset}/sparql``,
``/update`` and ``/data``.

CONSTRUCT asks for TriG because ARQ extends the CONSTRUCT grammar to allow GRAPH
in the template (https://jena.apache.org/documentation/query/construct-quad.html),
so a construct here can return quads and Turtle would discard the graph names.

Everything else is in mustrdSparqlHttp, shared with every other store that
implements the specs.
"""
from .mustrdSparqlHttp import SparqlHttpBackend

BACKEND = SparqlHttpBackend(
    label="Fuseki",
    paths={
        "query": lambda ts: f"/{ts['dataset']}/sparql",
        "update": lambda ts: f"/{ts['dataset']}/update",
        "graph_store": lambda ts: f"/{ts['dataset']}/data",
    },
    construct_accept="application/trig",
)
