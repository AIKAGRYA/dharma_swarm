from scripts.governance import check_nats_substrate_contract


def test_nats_substrate_contract_checker_passes() -> None:
    assert check_nats_substrate_contract.main() == 0
