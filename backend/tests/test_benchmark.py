"""The benchmark harness: statistics, pairing, and export."""

from app.optimizer.benchmark import (
    CSV_COLUMNS, AlgorithmStats, RunRecord, compare, to_csv_rows, to_dict,
)
from app.optimizer.problem import Problem
from tests.fixtures import square_graph


def _problem() -> Problem:
    return Problem(square_graph())


def _stats(costs):
    return AlgorithmStats("test", [
        RunRecord("test", i, c, c + 10, 1.0, 2, True, 1.0, 1.0, 1.0, 100, 0.01, 0,
                  curve=[c + 10, c])
        for i, c in enumerate(costs)
    ])


def test_stats_report_the_right_summary_values():
    s = _stats([10.0, 20.0, 30.0])
    assert s.mean == 20.0
    assert s.best == 10.0
    assert s.worst == 30.0
    assert s.median == 20.0
    assert abs(s.stdev - 10.0) < 1e-9


def test_stdev_of_a_single_run_is_zero_not_an_error():
    """One run has no spread. statistics.stdev would raise; we return 0.0."""
    assert _stats([42.0]).stdev == 0.0


def test_mean_curve_averages_across_runs():
    s = _stats([10.0, 20.0])
    assert s.mean_curve() == [25.0, 15.0]


def test_comparison_runs_both_algorithms_once_per_seed():
    c = compare(_problem(), seeds=[1, 2, 3], particles=6, iterations=10)
    assert len(c.qpso.runs) == 3
    assert len(c.pso.runs) == 3
    assert [r.seed for r in c.qpso.runs] == [1, 2, 3]


def test_head_to_head_counts_add_up_to_the_number_of_seeds():
    c = compare(_problem(), seeds=[1, 2, 3, 4], particles=6, iterations=10)
    w = c.wins
    assert w["qpso"] + w["pso"] + w["tie"] == 4


def test_both_algorithms_get_the_same_budget_in_a_comparison():
    c = compare(_problem(), seeds=[1, 2], particles=7, iterations=12)
    q = {r.evaluations for r in c.qpso.runs}
    p = {r.evaluations for r in c.pso.runs}
    assert q == p == {7 * 13}


def test_verdict_names_whichever_algorithm_actually_won():
    c = compare(_problem(), seeds=[1, 2, 3], particles=6, iterations=10)
    v = c.verdict()
    leader = "QPSO" if c.mean_gap_pct > 0 else "PSO"
    assert leader in v or "No separation" in v


def test_csv_has_a_header_and_one_row_per_run():
    c = compare(_problem(), seeds=[1, 2], particles=6, iterations=8)
    rows = to_csv_rows(c)
    assert rows[0] == CSV_COLUMNS
    assert len(rows) == 1 + 4          # header + 2 seeds x 2 algorithms
    assert len(set(len(r) for r in rows)) == 1


def test_export_dict_is_json_safe_and_complete():
    import json
    c = compare(_problem(), seeds=[1, 2], particles=6, iterations=8)
    d = to_dict(c)
    json.dumps(d)                       # must not raise
    assert d["setup"]["runs"] == 2
    assert d["setup"]["evaluationsPerRun"] == 6 * 9
    assert "meanCurve" in d["qpso"] and "meanCurve" in d["pso"]
    assert d["headToHead"]["qpso"] + d["headToHead"]["pso"] + d["headToHead"]["tie"] == 2


def test_empty_seed_list_is_rejected():
    try:
        compare(_problem(), seeds=[], particles=5, iterations=5)
    except ValueError:
        return
    raise AssertionError("A benchmark with no seeds should be rejected.")


def test_gap_to_exact_is_none_when_no_optimum_was_computed():
    c = compare(_problem(), seeds=[1], particles=5, iterations=5)
    assert c.gap_to_exact(c.qpso) is None


def test_gap_to_exact_is_a_percentage_above_the_floor():
    c = compare(_problem(), seeds=[1], particles=5, iterations=5)
    c.exact_cost = c.qpso.mean / 2.0
    assert abs(c.gap_to_exact(c.qpso) - 100.0) < 1e-6


def test_unequal_evaluation_budgets_are_refused():
    """The whole comparison rests on both algorithms spending the same number of
    evaluations. Shapes may differ - QPSO 20x1999 against PSO 80x499 - but the
    product must not.

    This check caught a real error: the variant sweep computed iterations as
    `budget // particles - 1`, which handed QPSO 40,040 evaluations against PSO's
    40,000. Small, and it moved the headline figure by 0.26 percentage points in
    our favour.
    """
    try:
        compare(_problem(), seeds=[1], qpso_shape=(20, 100), pso_shape=(40, 100))
    except ValueError as exc:
        assert "budget" in str(exc).lower()
        return
    raise AssertionError("Unequal evaluation budgets should be refused.")


def test_equal_budgets_with_different_shapes_are_allowed():
    """Different swarm shapes at the same budget is the whole point: each
    algorithm is reported at its own best configuration."""
    c = compare(_problem(), seeds=[1, 2], qpso_shape=(10, 39), pso_shape=(20, 19))
    q = {r.evaluations for r in c.qpso.runs}
    p = {r.evaluations for r in c.pso.runs}
    assert q == p == {400}
