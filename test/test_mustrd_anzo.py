import pytest
from mustrd import mustrdAnzo
# Those tests depend on a anzo instance and the data it contains.
# We don't parse triple store file nor secrets because we test only mustrdAnzo

# If you want to activate those tests, please configure your anzo configuration here:
anzo_config = {}
anzo_config['url'] = ""
anzo_config['username'] = ""
anzo_config['password'] = ""
anzo_config['gqe_uri'] = ""
anzo_config['input_graph'] = ""
anzo_config['output_graph'] = ""

graphmart = ""

folder_name = ""
query_name = ""

query_step = ""

query_driven_template_step = ""


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_execute_select():
    response = mustrdAnzo.execute_select(triple_store=anzo_config,
                                         when="SELECT * ${fromSources} WHERE {?s ?p ?o} LIMIT 10")
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_execute_update():
    response = mustrdAnzo.execute_update(triple_store=anzo_config,
                                         when="INSERT {GRAPH ${targetGraph} {?s ?p ?o}} ${usingSources} WHERE {?s ?p ?o}")
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_execute_construct():
    response = mustrdAnzo.execute_construct(triple_store=anzo_config,
                                            when="CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}")
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_get_spec_component_from_graphmart():
    response = mustrdAnzo.get_spec_component_from_graphmart(triple_store=anzo_config,
                                                            graphmart=graphmart, layer=anzo_config['input_graph'])
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_get_query_from_querybuilder():
    response = mustrdAnzo.get_query_from_querybuilder(triple_store=anzo_config, folder_name=folder_name, query_name=query_name)
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_get_query_from_step():
    response = mustrdAnzo.get_query_from_step(triple_store=anzo_config, query_step_uri=query_step)
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_get_queries_from_templated_step():
    response = mustrdAnzo.get_queries_from_templated_step(triple_store=anzo_config, query_step_uri=query_driven_template_step)
    print(f"Response: {response}")


@pytest.mark.skip(reason="We are not sure an anzo is configured")
def test_get_queries_for_layer():
    response = mustrdAnzo.get_queries_for_layer(triple_store=anzo_config, graphmart_layer_uri=anzo_config['input_graph'])
    print(f"Response: {response}")
