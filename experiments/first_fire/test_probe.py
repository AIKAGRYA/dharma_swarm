"""Narrow tests for the first-fire toy module. Not part of the main suite."""

from experiments.first_fire.probe import spark


def test_spark_is_small_int() -> None:
    value = spark()
    assert isinstance(value, int)
    assert value in (1, 2)
