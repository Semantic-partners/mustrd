"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import json
import os

from multimethods import MultiMethod, Default
from .namespace import MUST, TRIPLESTORE
from rdflib import Graph, URIRef
from .mustrdRdfLib import execute_select as execute_select_rdflib
from .mustrdRdfLib import execute_construct as execute_construct_rdflib
from .mustrdRdfLib import execute_update as execute_update_rdflib
from .mustrdAnzo import get_query_from_step, upload_given as upload_given_anzo
from .mustrdAnzo import execute_update as execute_update_anzo
from .mustrdAnzo import execute_construct as execute_construct_anzo
from .mustrdAnzo import execute_select as execute_select_anzo
from .mustrdGraphDb import upload_given as upload_given_graphdb
from .mustrdGraphDb import execute_update as execute_update_graphdb
from .mustrdGraphDb import execute_construct as execute_construct_graphdb
from .mustrdGraphDb import execute_select as execute_select_graphdb
from .spec_component import AnzoWhenSpec, WhenSpec, SpadeEdnGroupSourceWhenSpec
import logging
from edn_format import loads, Keyword

log = logging.getLogger(__name__)


def dispatch_upload_given(triple_store: dict, given: Graph):
    ts = triple_store['type']
    log.info(f"dispatch_upload_given to {ts}")
    return ts


upload_given = MultiMethod('upload_given', dispatch_upload_given)


@upload_given.method(TRIPLESTORE.RdfLib)
def _upload_given_rdflib(triple_store: dict, given: Graph):
    triple_store["given"] = given


@upload_given.method(TRIPLESTORE.GraphDb)
def _upload_given_graphdb(triple_store: dict, given: Graph):
    upload_given_graphdb(triple_store, given)


@upload_given.method(TRIPLESTORE.Anzo)
def _upload_given_anzo(triple_store: dict, given: Graph):
    upload_given_anzo(triple_store, given)


def dispatch_run_when(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    ts = triple_store['type']
    query_type = when.queryType
    log.info(f"dispatch_run_when: spec_uri={spec_uri}, ({ts},{query_type})")
    return ts, query_type


run_when_impl = MultiMethod('run_when', dispatch_run_when)


@run_when_impl.method((TRIPLESTORE.Anzo, MUST.UpdateSparql))
def _anzo_run_when_update(spec_uri: URIRef, triple_store: dict, when: AnzoWhenSpec):
    log.debug(f"_anzo_run_when_update {spec_uri} {triple_store} {when} {type(when)}")
    if when.value is None:
        # fetch the query from the query step on anzo
        query = get_query_from_step(triple_store=when.spec_component_details.mustrd_triple_store,
                                                    query_step_uri=when.query_step_uri)
    else: 
        # we must already have the query
        query = when.value
    log.debug(f"_anzo_run_when_update.query {query}")
    return execute_update_anzo(triple_store, query, when.bindings)


@run_when_impl.method((TRIPLESTORE.Anzo, MUST.ConstructSparql))
def _anzo_run_when_construct(spec_uri: URIRef, triple_store: dict, when: AnzoWhenSpec):
    return execute_construct_anzo(triple_store, when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.Anzo, MUST.SelectSparql))
def _anzo_run_when_select(spec_uri: URIRef, triple_store: dict, when: AnzoWhenSpec):
    return execute_select_anzo(triple_store, when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.GraphDb, MUST.UpdateSparql))
def _graphdb_run_when_update(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    return execute_update_graphdb(triple_store, when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.GraphDb, MUST.ConstructSparql))
def _graphdb_run_when_construct(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    return execute_construct_graphdb(triple_store, when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.GraphDb, MUST.SelectSparql))
def _graphdb_run_when_select(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    return execute_select_graphdb(triple_store, when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.RdfLib, MUST.UpdateSparql))
def _rdflib_run_when_update(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    return execute_update_rdflib(triple_store, triple_store["given"], when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.RdfLib, MUST.ConstructSparql))
def _rdflib_run_when_construct(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    return execute_construct_rdflib(triple_store, triple_store["given"], when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.RdfLib, MUST.SelectSparql))
def _rdflib_run_when_select(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    return execute_select_rdflib(triple_store, triple_store["given"], when.value, when.bindings)


@run_when_impl.method((TRIPLESTORE.Anzo, MUST.AnzoQueryDrivenUpdateSparql))
def _multi_run_when_anzo_query_driven_update(spec_uri: URIRef, triple_store: dict, when: AnzoWhenSpec):
    # run the parameters query to obtain the values for the template step and put them into a dictionary
    query_parameters = json.loads(execute_select_anzo(triple_store, when.paramQuery, None))
    if len(query_parameters['results']['bindings']) > 0:
        # replace the anzo query placeholders with the input and output graphs
        when_template = when.queryTemplate.replace(
            "${usingSources}",
            f"USING <{triple_store['input_graph']}> \nUSING <{triple_store['output_graph']}>").replace(
            "${targetGraph}", f"<{triple_store['output_graph']}>")

        # for each set of parameters insert their values into the template an run it
        for params in query_parameters['results']['bindings']:
            when_query = when_template
            for param in params:
                if params[param].get('datatype'):
                    value = params[param]['value']
                else:
                    if params[param]['type'] == 'uri':
                        value = '<' + params[param]['value'] + '>'
                    else:
                        value = '"' + params[param]['value'] + '"'
                when_query = when_query.replace("${" + param + "}", value)
            result = execute_update_anzo(triple_store, when_query, None)
        return result


@run_when_impl.method((TRIPLESTORE.Anzo, MUST.SpadeEdnGroupSource))
def _spade_edn_group_source(spec_uri: URIRef, triple_store: dict, when: SpadeEdnGroupSourceWhenSpec):
    log.info(f"Running SpadeEdnGroupSource for {spec_uri} using {triple_store}")

    merged_result = None
    # Iterate over the list of WhenSpec objects in `when.value`
    for step_when_spec in when.value:
        try:
            log.info(f"Dispatching run_when for step: {step_when_spec}")
            query_result = run_when_impl(spec_uri, triple_store, step_when_spec)
            log.info(f"Executed SPARQL query: {query_result}")
            # Merge results if possible (e.g., for Graphs), else just keep last non-None
            if merged_result is None:
                merged_result = query_result
            else:
                try:
                    merged_result += query_result  # For graph-like objects
                except Exception:
                    # If not mergeable, just keep the last result
                    merged_result = query_result
        except Exception as e:
            log.error(f"Failed to execute SPARQL query: {e}")

    log.debug(f"Final merged result: {merged_result}")
    return merged_result


@run_when_impl.method((TRIPLESTORE.RdfLib, MUST.SpadeEdnGroupSource))
def _spade_edn_group_source(spec_uri: URIRef, triple_store: dict, when: SpadeEdnGroupSourceWhenSpec):
    log.info(f"Running SpadeEdnGroupSource for {spec_uri} using {triple_store}")

    edn_file_dir = os.path.dirname(when.file)  # Get the directory of the EDN file
    merged_graph = Graph()

    # Iterate over the list of WhenSpec objects in `when.value`
    for step_when_spec in when.value:
        try:
            if step_when_spec.queryType == MUST.UpdateSparql:
                # Resolve file paths relative to the EDN file
                if hasattr(step_when_spec, 'filepath'):
                    step_when_spec.filepath = os.path.join(edn_file_dir, step_when_spec.filepath)

                log.info(f"Dispatching run_when for UpdateSparql step: {step_when_spec}")
                query_result = run_when_impl(spec_uri, triple_store, step_when_spec)
                log.info(f"Executed SPARQL query: {query_result}")
                merged_graph += query_result  # Merge the resulting graph
            else:
                log.warning(f"Unsupported queryType: {step_when_spec.queryType}")
        except Exception as e:
            log.error(f"Failed to execute SPARQL query: {e}")

    log.debug(f"Final merged graph has {len(merged_graph)} triples.")
    return merged_graph


@run_when_impl.method(Default)
def _multi_run_when_default(spec_uri: URIRef, triple_store: dict, when: WhenSpec):
    log.error(f"run_when not implemented for {spec_uri} {triple_store} {when}")
    if when.queryType == MUST.AskSparql:
        log.warning(f"Skipping {spec_uri}, SPARQL ASK not implemented.")
        msg = "SPARQL ASK not implemented."
    elif when.queryType == MUST.DescribeSparql:
        log.warning(f"Skipping {spec_uri}, SPARQL DESCRIBE not implemented.")
        msg = "SPARQL DESCRIBE not implemented."
    elif triple_store['type'] not in [TRIPLESTORE.Anzo, TRIPLESTORE.GraphDb, TRIPLESTORE.RdfLib]:
        msg = f"{when.queryType} not implemented for {triple_store['type']}"
    else:
        log.warning(f"Skipping {spec_uri},  {when.queryType} is not a valid SPARQL query type.")
        msg = f"{when.queryType} is not a valid SPARQL query type."
    raise NotImplementedError(msg)

log.debug(f"run_when registry: {run_when_impl} {dir(run_when_impl)}")

