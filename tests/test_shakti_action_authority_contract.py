from __future__ import annotations


def test_shakti_action_authority_predicate_exists_and_rejects_missing_high_risk_scan():
    from dharma_swarm.ontology import ActionExecution
    from dharma_swarm import policy_compiler

    action = ActionExecution(
        action_name="external_commitment",
        object_id="proposal-1",
        object_type="ActionProposal",
        input_params={
            "is_significant_action": True,
            "risk_level": "high",
            "action_authority_case": {
                "maheshwari_scope": "limited migration repair",
                "mahalakshmi_impact_scan": "operator-visible only",
                "mahasaraswati_execution_plan": "patch and run tests",
            },
        },
    )

    predicate = policy_compiler.shakti_action_authority_predicate
    assert predicate(action) is False


def test_policy_compiler_blocks_autonomous_significant_action_when_authority_case_fails():
    from dharma_swarm.dharma_kernel import DharmaKernel, MetaPrinciple
    from dharma_swarm.policy_compiler import PolicyCompiler

    kernel = DharmaKernel.create_default()
    policy = PolicyCompiler().compile(
        {MetaPrinciple.SHAKTI_QUESTIONS.value: kernel.principles[MetaPrinciple.SHAKTI_QUESTIONS.value]},
        [],
        context="autonomous",
    )

    assert any(
        getattr(rule, "named_evaluator", None) == "valid_action_authority_case"
        for rule in policy.rules
    )
