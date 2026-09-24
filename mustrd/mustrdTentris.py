"""Tentris, over the SPARQL 1.1 protocols.

Endpoints sit at the root: ``{url}:{port}/sparql``, ``/update`` and
``/graph-store``. There is no dataset name in the path — a server serves one
datastore, chosen with ``tentris -s <path> serve``.

CONSTRUCT asks for Turtle. Tentris implements the SPARQL 1.1 grammar, in which a
CONSTRUCT template is triple patterns only, so a construct cannot name graphs and
there are no quads to lose.

Everything else is in mustrdSparqlHttp, shared with every other store that
implements the specs.
"""
from .mustrdSparqlHttp import SparqlHttpBackend

BACKEND = SparqlHttpBackend(
    label="Tentris",
    paths={
        "query": lambda ts: "/sparql",
        "update": lambda ts: "/update",
        "graph_store": lambda ts: "/graph-store",
    },
    construct_accept="text/turtle",
)
