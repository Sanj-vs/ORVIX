
from backend.llm_agents import ORVIXLLMAgents


class FakeClient:
    model = "phi3:latest"

    def __init__(self):
        self.calls = []

    def chat(self, system_prompt, user_payload):
        self.calls.append((system_prompt, user_payload))

        responses = {
            1: "A disruption event has been detected. The affected shipment requires monitoring. The supplied evidence will guide further assessment.",
            2: "The supplied risk score is 72 and the risk tier is ELEVATED. The shipment requires attention. Preventive action should follow the Python assessment.",
            3: (
                "Affected quantity is 80 kg, expected delay is 0 minutes, "
                "and spoilage cost is $40. "
                "SLA penalty is $20, additional logistics cost is $60, "
                "and total financial exposure is $120. "
                "Unmet demand is 80 kg and data confidence is 90%."
            ),
            4: (
                "Python recommends Inland Bypass & Express Reefer Dispatch "
                "as the feasible recovery alternative. "
                "It has vehicle capacity of 1000 kg, estimated delay of "
                "45 minutes, and additional cost of $300. "
                "Other infeasible options remain rejected."
            ),
            5: (
                "The disruption has an ELEVATED risk score of 72, with "
                "affected quantity 80 kg, expected delay 0 minutes, "
                "spoilage cost $40, SLA penalty $20, additional logistics "
                "cost $60, and total financial exposure $120. "
                "Python recommends Inland Bypass & Express Reefer Dispatch, "
                "with unmet demand of 80 kg and data confidence of 90%. "
                "Human approval is required before any operational action."
            ),
        }

        return responses[len(self.calls)]

def test_five_role_specific_llm_calls_are_chained():
    client = FakeClient()

    result = ORVIXLLMAgents(client).run(
        {
            "workflow_stage": "PENDING_APPROVAL",
            "risk_assessment": {
                "risk_score": 72,
                "risk_tier": "ELEVATED",
            },
            "business_impact": {
                "quantity_affected_kg": 80,
                "expected_delay_minutes": 0,
                "estimated_spoilage_cost_usd": 40,
                "estimated_sla_penalty_usd": 20,
                "estimated_additional_logistics_usd": 60,
                "total_financial_exposure_usd": 120,
                "unmet_demand_kg": 80,
                "data_confidence_pct": 90,
            },
            "recovery_alternatives": [
                {
                    "name": "Inland Bypass & Express Reefer Dispatch",
                    "is_feasible": True,
                    "is_recommended": True,
                    "vehicle_capacity_kg": 1000,
                    "estimated_delay_minutes": 45,
                    "additional_cost_usd": 300,
                },
                {
                    "name": "Emergency Light Courier Van C3 (Rejected)",
                    "is_feasible": False,
                    "is_recommended": False,
                },
            ],
            "recommended_alternative": {
                "name": "Inland Bypass & Express Reefer Dispatch",
                "is_feasible": True,
                "is_recommended": True,
                "vehicle_capacity_kg": 1000,
                "estimated_delay_minutes": 45,
                "additional_cost_usd": 300,
            },
        },
        {"quantity_kg": 800},
    )

    assert len(client.calls) == 5
    assert result["completed_count"] == 5
    assert result["human_approval_required"] is True
    assert "preceding_agent_outputs" in client.calls[1][1]
    assert len(client.calls[1][1]["preceding_agent_outputs"]) == 1
    assert "cannot approve" in client.calls[-1][0].lower()


def test_llm_failure_falls_back_without_stopping_agent_chain():
    class BrokenClient(FakeClient):
        def chat(self, system_prompt, user_payload):
            self.calls.append((system_prompt, user_payload))
            if len(self.calls) == 1:
                raise TimeoutError("Ollama timed out")
            return "Available fallback reasoning"

    result = ORVIXLLMAgents(BrokenClient()).run({})
    assert result["total_count"] == 5
    assert result["agents"][0]["status"] == "LLM_UNAVAILABLE_FALLBACK"
    assert result["agents"][1]["status"] == "LLM_COMPLETED"
def test_rejects_incorrect_financial_exposure():
    impact = {
        "total_financial_exposure_usd": 120,
    }

    explanation = "The total financial exposure is $1,200."

    errors = ORVIXLLMAgents.validate_impact_explanation(
        explanation,
        impact,
    )

    assert errors
    assert any(
        "total financial exposure" in error.lower()
        for error in errors
    )
def test_rejects_infeasible_alternative_as_recommended():
    alternatives = [
        {
            "name": "Inland Bypass & Express Reefer Dispatch",
            "is_feasible": True,
            "is_recommended": True,
            "vehicle_capacity_kg": 1000,
            "estimated_delay_minutes": 45,
            "additional_cost_usd": 300,
        },
        {
            "name": "Emergency Light Courier Van C3",
            "is_feasible": False,
            "is_recommended": False,
        },
    ]

    recommended = alternatives[0]

    explanation = (
        "Python recommends Inland Bypass & Express Reefer Dispatch "
        "as the feasible recovery alternative. "
        "Emergency Light Courier Van C3 is recommended as the best option."
    )

    errors = ORVIXLLMAgents.validate_recovery_explanation(
        explanation,
        alternatives,
        recommended,
    )

    assert errors
    assert any(
        "infeasible alternative" in error.lower()
        for error in errors
    )
def test_rejects_recovery_delay_as_expected_shipment_delay():
    impact = {
        "expected_delay_minutes": 0,
    }

    explanation = (
        "The expected shipment delay is 35 minutes. "
        "The recovery alternative has an estimated delay "
        "of 35 minutes."
    )

    errors = ORVIXLLMAgents.validate_impact_explanation(
        explanation,
        impact,
    )

    assert errors
    assert any(
        "expected shipment delay" in error.lower()
        for error in errors
    )