"""Property-based tests for FitnessScore.

Tests that fitness calculations are always valid, bounded, and consistent.
"""

import pytest
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis not installed")
from hypothesis import given, strategies as st

try:
    from dharma_swarm.archive import FITNESS_DIMENSIONS, FitnessScore
    ARCHIVE_AVAILABLE = True
except ImportError:
    ARCHIVE_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="archive module not available")


def fitness_score_strategy():
    """Generate random but valid FitnessScore instances.

    Dimensions are derived from FITNESS_DIMENSIONS (the canonical weight keys)
    so the strategy cannot silently drift out of sync with the model when a
    new fitness dimension is added.
    """
    unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    return st.builds(
        FitnessScore,
        **{dim: unit for dim in FITNESS_DIMENSIONS},
    )


if ARCHIVE_AVAILABLE:
    @given(fitness_score_strategy())
    def test_fitness_all_dimensions_bounded(fitness):
        """Property: All fitness dimensions must be in [0, 1]."""
        values = fitness.model_dump(include=set(FITNESS_DIMENSIONS))
        for dim, value in values.items():
            assert 0.0 <= value <= 1.0, f"{dim}={value} out of bounds [0, 1]"


    @given(fitness_score_strategy())
    def test_fitness_weighted_bounded(fitness):
        """Property: Weighted fitness score must be in [0, 1]."""
        weighted = fitness.weighted()
        assert 0.0 <= weighted <= 1.0, \
            f"Weighted fitness {weighted} out of bounds [0, 1]"


    @given(fitness_score_strategy())
    def test_fitness_weighted_not_nan(fitness):
        """Property: Weighted fitness should never be NaN."""
        import math
        weighted = fitness.weighted()
        assert not math.isnan(weighted), "Weighted fitness is NaN"


    @given(fitness_score_strategy(), st.dictionaries(
        st.sampled_from(FITNESS_DIMENSIONS),
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=1
    ))
    def test_fitness_custom_weights_sum_not_required(fitness, weights):
        """Property: Custom weights don't need to sum to 1.0 (just positive)."""
        # Should not raise even if weights don't sum to 1
        try:
            weighted = fitness.weighted(weights)
            # Should still be a valid number
            import math
            assert not math.isnan(weighted)
            assert not math.isinf(weighted)
        except Exception as e:
            pytest.fail(f"Custom weights raised exception: {e}")


    @given(fitness_score_strategy())
    def test_fitness_json_roundtrip(fitness):
        """Property: FitnessScore serialization preserves values."""
        json_str = fitness.model_dump_json()
        restored = FitnessScore.model_validate_json(json_str)

        assert restored.model_dump(include=set(FITNESS_DIMENSIONS)) == fitness.model_dump(
            include=set(FITNESS_DIMENSIONS)
        )


    @given(fitness_score_strategy())
    def test_fitness_perfect_score_is_one(fitness):
        """Property: If all dimensions are 1.0, weighted should be 1.0."""
        perfect = FitnessScore(**{dim: 1.0 for dim in FITNESS_DIMENSIONS})
        assert abs(perfect.weighted() - 1.0) < 0.001, \
            f"Perfect score weighted to {perfect.weighted()}, expected 1.0"


    @given(fitness_score_strategy())
    def test_fitness_zero_score_is_zero(fitness):
        """Property: If all dimensions are 0.0, weighted should be 0.0."""
        zero = FitnessScore(**{dim: 0.0 for dim in FITNESS_DIMENSIONS})
        assert abs(zero.weighted() - 0.0) < 0.001, \
            f"Zero score weighted to {zero.weighted()}, expected 0.0"
