import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from advanced import reschedule_after_node_failure, weighted_objective
from baselines import greedy_earliest_finish
from problem import generate_instance


def test_multi_objective_and_failure_reschedule():
    inst = generate_instance(12, 4, seed=3)
    result = greedy_earliest_finish(inst)
    score = weighted_objective(inst, result)
    assert score["makespan"] == result["makespan"]
    repaired = reschedule_after_node_failure(inst, result, failed_node=1)
    assert repaired["failed_node"] == 1
    assert all(node != 1 for node in repaired["node"])
