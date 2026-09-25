import pytest

from app.tasks.graph import InvalidPlanError, topological_order
from app.tasks.schemas import PlannedTask
from app.tasks.service import validate_plan


def test_order_respects_dependencies() -> None:
    order = topological_order({"T3": ["T2"], "T1": [], "T2": ["T1"], "T4": ["T1"]})
    assert order.index("T1") < order.index("T2") < order.index("T3")
    assert order.index("T1") < order.index("T4")


@pytest.mark.parametrize(
    ("graph", "message"),
    [
        ({"A": ["B"], "B": ["A"]}, "circulares"),
        ({"A": ["B"], "B": ["C"], "C": ["A"]}, "circulares"),
        ({"A": ["A"]}, "si própria"),
        ({"A": ["Z"]}, "não existe"),
    ],
)
def test_invalid_graphs(graph, message) -> None:
    with pytest.raises(InvalidPlanError, match=message):
        topological_order(graph)


def test_plan_limits() -> None:
    task = lambda k: PlannedTask(key=k, title=k, description=k)  # noqa: E731
    with pytest.raises(InvalidPlanError, match="máximo"):
        validate_plan([task(f"T{i}") for i in range(11)])
    with pytest.raises(InvalidPlanError, match="mesma chave"):
        validate_plan([task("T1"), task("T1")])
    with pytest.raises(InvalidPlanError):
        validate_plan([])
