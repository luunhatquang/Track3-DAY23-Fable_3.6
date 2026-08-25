from langgraph_agent_lab.graph import build_graph

EXPECTED = {"intake", "classify", "tool", "evaluate", "answer", "clarify",
            "risky_action", "approval", "retry", "dead_letter", "finalize"}


def test_graph_registers_all_nodes():
    graph = build_graph().get_graph()
    assert set(graph.nodes) - {"__start__", "__end__"} == EXPECTED


def test_all_nodes_can_reach_finalize():
    graph = build_graph().get_graph()
    adjacency = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
    for start in EXPECTED:
        pending, visited = [start], set()
        while pending and "finalize" not in visited:
            node = pending.pop()
            visited.add(node)
            pending.extend(adjacency.get(node, set()) - visited)
        assert "finalize" in visited
