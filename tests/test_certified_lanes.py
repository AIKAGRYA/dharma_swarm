"""Tests for dharma_swarm.certified_lanes — certified operator lane registry.

Validates:
- CertifiedLane.matches_profile_id with exact and alias matching
- CertifiedLane.matches_alias across all identity fields
- CertifiedLane.matches_provider_model with default and alias models
- get_certified_lane lookup by profile_id
- match_certified_lane multi-strategy resolution
- CERTIFIED_LANES tuple completeness
- CERTIFIED_LANE_BY_PROFILE_ID dict correctness
"""

from __future__ import annotations

import pytest

from dharma_swarm.certified_lanes import (
    CERTIFIED_LANE_BY_PROFILE_ID,
    CERTIFIED_LANES,
    CertifiedLane,
    get_certified_lane,
    match_certified_lane,
)
from dharma_swarm.models import ProviderType


# ---------------------------------------------------------------------------
# CERTIFIED_LANES data integrity
# ---------------------------------------------------------------------------


class TestCertifiedLanesData:
    def test_lanes_not_empty(self):
        assert len(CERTIFIED_LANES) > 0

    def test_all_lanes_have_unique_profile_ids(self):
        ids = [lane.profile_id for lane in CERTIFIED_LANES]
        assert len(ids) == len(set(ids))

    def test_all_lanes_have_unique_registration_ids(self):
        ids = [lane.registration_id for lane in CERTIFIED_LANES]
        assert len(ids) == len(set(ids))

    def test_by_profile_id_dict_matches_tuple(self):
        assert len(CERTIFIED_LANE_BY_PROFILE_ID) == len(CERTIFIED_LANES)
        for lane in CERTIFIED_LANES:
            assert CERTIFIED_LANE_BY_PROFILE_ID[lane.profile_id] is lane

    def test_all_lanes_have_required_fields(self):
        for lane in CERTIFIED_LANES:
            assert lane.profile_id
            assert lane.label
            assert lane.summary
            assert lane.registration_id
            assert lane.codename
            assert lane.display_name


# ---------------------------------------------------------------------------
# CertifiedLane.matches_profile_id
# ---------------------------------------------------------------------------


class TestMatchesProfileId:
    def test_exact_match(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_profile_id(lane.profile_id) is True

    def test_case_insensitive(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_profile_id(lane.profile_id.upper()) is True

    def test_alias_match(self):
        for lane in CERTIFIED_LANES:
            if lane.aliases:
                assert lane.matches_profile_id(lane.aliases[0]) is True

    def test_none_returns_false(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_profile_id(None) is False

    def test_empty_string_returns_false(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_profile_id("") is False

    def test_no_match(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_profile_id("nonexistent_profile") is False


# ---------------------------------------------------------------------------
# CertifiedLane.matches_alias
# ---------------------------------------------------------------------------


class TestMatchesAlias:
    def test_matches_profile_id(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_alias(lane.profile_id) is True

    def test_matches_codename(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_alias(lane.codename) is True

    def test_matches_display_name(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_alias(lane.display_name) is True

    def test_matches_label(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_alias(lane.label) is True

    def test_matches_alias_entry(self):
        for lane in CERTIFIED_LANES:
            if lane.aliases:
                assert lane.matches_alias(lane.aliases[0]) is True

    def test_case_insensitive(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_alias(lane.codename.upper()) is True

    def test_none_returns_false(self):
        assert CERTIFIED_LANES[0].matches_alias(None) is False

    def test_empty_returns_false(self):
        assert CERTIFIED_LANES[0].matches_alias("") is False

    def test_no_match(self):
        assert CERTIFIED_LANES[0].matches_alias("totally_unknown_alias") is False


# ---------------------------------------------------------------------------
# CertifiedLane.matches_provider_model
# ---------------------------------------------------------------------------


class TestMatchesProviderModel:
    def test_default_model_match(self):
        for lane in CERTIFIED_LANES:
            for provider, model in lane.default_models.items():
                assert lane.matches_provider_model(provider, model) is True

    def test_model_alias_match(self):
        for lane in CERTIFIED_LANES:
            if lane.model_aliases:
                for provider, aliases in lane.model_aliases.items():
                    for alias in aliases:
                        assert lane.matches_provider_model(provider, alias) is True

    def test_wrong_model_no_match(self):
        lane = CERTIFIED_LANES[0]
        provider = list(lane.default_models.keys())[0]
        assert lane.matches_provider_model(provider, "completely-wrong-model") is False

    def test_wrong_provider_no_match(self):
        lane = CERTIFIED_LANES[0]
        model = list(lane.default_models.values())[0]
        assert lane.matches_provider_model("nonexistent_provider", model) is False

    def test_none_provider_returns_false(self):
        lane = CERTIFIED_LANES[0]
        assert lane.matches_provider_model(None, "some-model") is False

    def test_none_model_returns_false(self):
        lane = CERTIFIED_LANES[0]
        provider = list(lane.default_models.keys())[0]
        assert lane.matches_provider_model(provider, None) is False

    def test_provider_as_string(self):
        for lane in CERTIFIED_LANES:
            for provider, model in lane.default_models.items():
                assert lane.matches_provider_model(provider.value, model) is True


# ---------------------------------------------------------------------------
# get_certified_lane
# ---------------------------------------------------------------------------


class TestGetCertifiedLane:
    def test_known_profile_id(self):
        lane = CERTIFIED_LANES[0]
        result = get_certified_lane(lane.profile_id)
        assert result is lane

    def test_alias_profile_id(self):
        for lane in CERTIFIED_LANES:
            if lane.aliases:
                result = get_certified_lane(lane.aliases[0])
                assert result is lane

    def test_none_returns_none(self):
        assert get_certified_lane(None) is None

    def test_empty_returns_none(self):
        assert get_certified_lane("") is None

    def test_unknown_returns_none(self):
        assert get_certified_lane("totally_unknown") is None


# ---------------------------------------------------------------------------
# match_certified_lane
# ---------------------------------------------------------------------------


class TestMatchCertifiedLane:
    def test_by_profile_id(self):
        lane = CERTIFIED_LANES[0]
        result = match_certified_lane(profile_id=lane.profile_id)
        assert result is lane

    def test_by_alias(self):
        lane = CERTIFIED_LANES[0]
        result = match_certified_lane(alias=lane.codename)
        assert result is lane

    def test_by_provider_model(self):
        lane = CERTIFIED_LANES[0]
        provider = list(lane.default_models.keys())[0]
        model = lane.default_models[provider]
        result = match_certified_lane(provider=provider, model=model)
        assert result is lane

    def test_profile_id_takes_priority(self):
        lane = CERTIFIED_LANES[0]
        other = CERTIFIED_LANES[1] if len(CERTIFIED_LANES) > 1 else CERTIFIED_LANES[0]
        result = match_certified_lane(
            profile_id=lane.profile_id,
            alias=other.codename,
        )
        assert result is lane

    def test_no_match_returns_none(self):
        result = match_certified_lane(
            profile_id="unknown",
            alias="unknown",
            provider="unknown",
            model="unknown",
        )
        assert result is None

    def test_all_none_returns_none(self):
        assert match_certified_lane() is None
