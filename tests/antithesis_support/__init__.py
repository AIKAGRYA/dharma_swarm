"""Support package for the native Antithesis-style harness (DharmaGraph goal).

Deliberately OUTSIDE tests/oracle_support/: that directory is digest-pinned
by the parity gauntlet custody chain (RELEVANT_SOURCE_ROOTS in
scripts/governance/dharmagraph_parity_gauntlet.py) and additions there
require a builder+judge reseal.
"""
