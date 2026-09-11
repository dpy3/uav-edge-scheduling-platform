from __future__ import annotations

import numpy as np
import pytest

from problem import generate_instance, makespan_of


def test_instance_generation_is_reproducible():
    first = generate_instance(n_tasks=8, n_nodes=3, seed=11)
    second = generate_instance(n_tasks=8, n_nodes=3, seed=11)

    np.testing.assert_array_equal(first.release, second.release)
    np.testing.assert_array_equal(first.duration, second.duration)
    assert first.node_names == ["UAV-local", "edge-1", "edge-2"]


def test_decoder_respects_release_times_and_assignment():
    inst = generate_instance(n_tasks=5, n_nodes=2, seed=3)
    assignment = np.zeros(inst.n_tasks, dtype=int)
    order = np.arange(inst.n_tasks)

    makespan, start, node = makespan_of(assignment, order, inst)

    assert makespan == int((start + inst.duration[:, 0]).max())
    assert np.all(start >= inst.release)
    assert np.all(node == assignment)
    assert np.all(start[1:] >= start[:-1])


def test_decoder_rejects_invalid_order_values():
    inst = generate_instance(n_tasks=4, n_nodes=2, seed=2)
    with pytest.raises(IndexError):
        makespan_of(np.zeros(4, dtype=int), np.array([0, 1, 2, 4]), inst)
