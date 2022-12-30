from rdflib.compare import graph_diff


def graph_comparison_message(expected_graph, actual_graph) -> str:
    diff = graph_diff(expected_graph, actual_graph)
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual).serialize(format='ttl')
    in_actual_not_in_expected = (in_actual - in_expected).serialize(format='ttl')
    in_both = diff[0].serialize(format='ttl')
    message = f"\nin_expected_not_in_actual\n{in_expected_not_in_actual}\nin_actual_not_in_expected\n{in_actual_not_in_expected}\nin_both\n{in_both}"
    return message
