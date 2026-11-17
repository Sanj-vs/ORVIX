"""Local Phi-3 reasoning layer for ORVIX's five agents.

Deterministic Python agents remain authoritative for risk scores,
financial calculations, recovery feasibility, ranking and validation.

Phi-3 explains validated backend results only.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List


def to_json_safe(value: Any) -> Any:
    """Convert Python objects into JSON-compatible values."""

    if is_dataclass(value) and not isinstance(value, type):
        return to_json_safe(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): to_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def compact_json(value: Any) -> str:
    """Create compact JSON for Ollama."""

    return json.dumps(
        to_json_safe(value),
        ensure_ascii=False,
        separators=(",", ":"),
    )


class OllamaClient:
    """Communicates with the locally running Ollama service."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "phi3:latest",
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/api/tags",
                timeout=5,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )

            models = [
                item.get("name", "")
                for item in payload.get("models", [])
            ]

            return any(
                name == self.model
                or name.startswith(
                    self.model.split(":")[0] + ":"
                )
                for name in models
            )

        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            TypeError,
        ):
            return False

    def chat(
        self,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> str:

        request_data = {
            "model": self.model,
            "stream": False,
            "keep_alive": "10m",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": compact_json(user_payload),
                },
            ],
            "options": {
                "temperature": 0.1,
                "num_predict": 900,
                "num_ctx": 4500,
            },
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(request_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=self.timeout,
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

        message = result.get("message", {})
        content = message.get("content", "")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama returned an empty response.")

        content = content.strip()

        done_reason = result.get("done_reason", "")

        if done_reason == "length":
            raise ValueError(
                "Phi-3 response was truncated because it reached "
                "the generation token limit."
            )

        if result.get("done") is False:
            raise ValueError("Ollama returned an incomplete response.")

        if len(content) < 50:
            raise ValueError("Phi-3 response is too short to validate.")

        if content[-1] not in ".!?\"')]}":
            raise ValueError("Phi-3 response may be incomplete.")

        return content


class ORVIXLLMAgents:
    """Runs five chained local LLM explanation agents."""

    ROLES = [
        (
            "A · Disruption Sensor",
            """
            Explain the detected disruption events in exactly 3 concise sentences.
            Identify the event, severity, affected shipment or facility, and supplied evidence.
            Distinguish observed, forecast and simulated events, including confidence when available.
            Do not invent disruptions or make recovery decisions.
            """,
        ),
        (
            "B · Predictive Risk",
            """
            Explain the supplied predictive risk assessment in exactly 3 concise sentences.
            Include the exact risk score, tier, risk direction and main contributing factors.
            Explain their operational meaning and mention the supplied preventive action, if available.
            Never calculate or modify risk scores or invent predictions.
            """,
        ),
        (
            "C · Impact Scoring",
           """
Explain the supplied Python business-impact metrics in
exactly 3 concise sentences.

Use this exact sentence structure, filling every value
from the Python business_impact input:

Sentence 1: Affected quantity: [exact value and unit];
expected shipment delay: [exact value and unit];
unmet demand: [exact value and unit].

Sentence 2: Spoilage cost: [exact value and currency];
SLA penalty: [exact value and currency];
additional logistics cost: [exact value and currency].

Sentence 3: Total financial exposure: [exact value and
currency]; data confidence: [exact value and percentage].

Include every metric. Preserve zero values.
Never use values from preceding agent explanations.
Never confuse recovery delay with expected shipment delay.
Do not calculate or modify any value.
"""
        ),
        (
            "D · Scenario Planner",
            """


Explain Python's recovery planning in exactly 3 concise,
complete sentences.

Sentence 1:
The Python-recommended alternative is "[exact alternative name]",
and this alternative is feasible.

Sentence 2 MUST follow this format:
Vehicle capacity: [exact vehicle_capacity_kg] kg;
estimated recovery delay: [exact estimated_delay_minutes] minutes;
additional recovery cost: [exact additional_cost_usd] USD.

Sentence 3:
Briefly explain why Python selected this alternative,
using only supplied facts.

Copy every value directly from recommended_alternative.
Never omit vehicle capacity.
Never invent, calculate, round or modify any value.
Never replace the exact recommendation name with a route
or vehicle description.
"""),
    (
            "E · Orchestrator",
            """
Prepare an operations manager briefing in exactly 3
concise, complete sentences.

Sentence 1:
State the main disruption, exact Python risk score and
risk tier, and the exact Python-recommended alternative
name copied from the recommended_alternative input.

Sentence 2:
Include every business-impact metric using this exact
label-and-value format, separated by semicolons:
Affected quantity: [exact Python affected quantity];
Expected shipment delay: [exact Python expected shipment delay];
Spoilage cost: [exact Python spoilage cost];
SLA penalty: [exact Python SLA penalty];
Additional logistics cost: [exact Python additional logistics cost];
Total financial exposure: [exact Python total financial exposure];
Unmet demand: [exact Python unmet demand];
Data confidence: [exact Python data confidence].

Sentence 3:
Clearly state that human approval is required before action.

IMPORTANT:
- Get all business-impact values from Python's business_impact
  input, not from preceding agent explanations.
- Affected quantity means the business-impact affected quantity.
  Never substitute total shipment cargo quantity.
- Do not confuse affected quantity with the 800 kg shipment cargo.
- Copy the exact recommendation name from Python.
- Preserve every number, zero value, unit and currency exactly.
- Never calculate, estimate or modify Python results.
- Never claim that recovery has been executed or a vehicle dispatched.
- The AI agent cannot approve or authorize operational actions.
"""),
    ]

    COMMON_RULES = """
STRICT RESPONSE RULES:

- Use simple, professional English.
- Write exactly 3 concise, complete sentences.
- Use only authoritative Python facts for all numbers,
  measurements, scores, costs, delays and recommendations.
- Python facts always override preceding agent outputs.
- Preceding agent outputs are context only, never a source
  of numerical or operational facts.
- Never copy a number from a preceding agent unless it
  exactly matches the corresponding Python fact.
- Preserve every supplied numerical value and unit exactly.
- Preserve zero values.
- Never calculate, estimate, round or modify Python results.
- Never invent dates, IDs, locations or measurements.
- Do not output JSON, dictionaries or code.
- Distinguish simulated information from observed facts.
- If information is missing, state that it is unavailable.
- Do not perform operational actions.
- Human approval is required for operational decisions.
- Never produce an incomplete sentence.
"""

    def __init__(
        self,
        client: OllamaClient | None = None,
    ):
        self.client = client or OllamaClient()

    @staticmethod
    def _numeric_value_matches(
        text: str,
        value: Any,
    ) -> bool:
        """Check whether an exact numeric value appears in text."""

        if value is None or isinstance(value, bool):
            return False

        try:
            expected = float(value)
        except (TypeError, ValueError):
            return False

        number_pattern = r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?"

        for match in re.finditer(number_pattern, text):
            try:
                actual = float(match.group().replace(",", ""))
            except ValueError:
                continue

            if abs(actual - expected) < 0.000001:
                return True

        return False

    @staticmethod
    def _metric_value_is_grounded(
        explanation: str,
        aliases: List[str],
        expected_value: Any,
    ) -> bool:
        """Check that a metric's expected value appears in its clause."""

        if expected_value is None:
            return True

        clauses = re.split(
            r"(?<=[.!?;])\s+|\n+|\s+\b(?:and|but|while|whereas|however)\b\s+",
            explanation,
            flags=re.IGNORECASE,
        )

        for clause in clauses:
            for alias in aliases:
                if re.search(
                    re.escape(alias),
                    clause,
                    flags=re.IGNORECASE,
                ):
                    if ORVIXLLMAgents._numeric_value_matches(
                        clause,
                        expected_value,
                    ):
                        return True

        return False

    @staticmethod
    def validate_impact_explanation(
        explanation: str,
        impact: Dict[str, Any] | None,
    ) -> List[str]:
        """Validate Agent C's metric-to-value associations."""

        if not impact:
            return []

        checks = {
            "affected quantity": (
                ["affected quantity", "quantity affected"],
                impact.get("quantity_affected_kg"),
            ),
            "expected shipment delay": (
                ["expected shipment delay", "expected delay"],
                impact.get("expected_delay_minutes"),
            ),
            "spoilage cost": (
                ["spoilage cost", "spoilage loss"],
                impact.get("estimated_spoilage_cost_usd"),
            ),
            "SLA penalty": (
                ["SLA penalty", "contractual penalty"],
                impact.get("estimated_sla_penalty_usd"),
            ),
            "additional logistics cost": (
                ["additional logistics cost", "logistics cost"],
                impact.get("estimated_additional_logistics_usd"),
            ),
            "total financial exposure": (
                ["total financial exposure", "financial exposure"],
                impact.get("total_financial_exposure_usd"),
            ),
            "unmet demand": (
                ["unmet demand"],
                impact.get("unmet_demand_kg"),
            ),
            "data confidence": (
                ["data confidence"],
                impact.get("data_confidence_pct"),
            ),
        }

        errors = []

        for metric_name, (aliases, expected_value) in checks.items():
            if expected_value is None:
                continue

            if not ORVIXLLMAgents._metric_value_is_grounded(
                explanation,
                aliases,
                expected_value,
            ):
                errors.append(
                    f"Incorrect or missing value for {metric_name}."
                )

        return errors

    @staticmethod
    def validate_recovery_explanation(
        explanation: str,
        alternatives: List[Dict[str, Any]],
        recommended: Dict[str, Any] | None,
    ) -> List[str]:
        """Validate Agent D's recommendation against Python's decisions."""

        errors = []
        text = explanation.casefold()

        if recommended:
            recommended_name = str(
                recommended.get("name", "")
            ).strip()

            if not recommended_name:
                errors.append(
                    "Python recommendation has no alternative name."
                )
            elif recommended_name.casefold() not in text:
                errors.append(
                    "Python's recommended alternative is missing."
                )

            if recommended.get("is_feasible") is not True:
                errors.append(
                    "Python's recommended alternative is not feasible."
                )

            if (
                recommended_name
                and recommended_name.casefold() in text
                and "feasible" not in text
            ):
                errors.append(
                    "The recommended alternative's feasibility "
                    "is not explained."
                )

            checks = {
                "vehicle capacity": (
                    ["capacity"],
                    recommended.get("vehicle_capacity_kg"),
                ),
                "recovery delay": (
                    ["estimated delay", "recovery delay"],
                    recommended.get("estimated_delay_minutes"),
                ),
                "additional recovery cost": (
                    ["additional cost", "recovery cost"],
                    recommended.get("additional_cost_usd"),
                ),
            }

            for metric_name, (aliases, expected_value) in checks.items():
                if expected_value is None:
                    continue

                if not ORVIXLLMAgents._metric_value_is_grounded(
                    explanation,
                    aliases,
                    expected_value,
                ):
                    errors.append(
                        f"Incorrect or missing {metric_name}."
                    )

        else:
            if not any(
                phrase in text
                for phrase in (
                    "no feasible",
                    "no alternative",
                    "operational escalation",
                    "escalation required",
                )
            ):
                errors.append(
                    "No feasible recommendation was supplied by Python, "
                    "but escalation was not explained."
                )

        for alternative in alternatives:
            if alternative.get("is_feasible") is not False:
                continue

            alt_name = str(
                alternative.get("name", "")
            ).strip()

            if not alt_name:
                continue

            pattern = (
                r"(?:recommended|recommendation|best option|optimal choice)"
                r".{0,100}"
                + re.escape(alt_name)
                + r"|"
                + re.escape(alt_name)
                + r".{0,100}"
                r"(?:is recommended|is the best option|is the optimal choice)"
            )

            for match in re.finditer(
                pattern,
                explanation,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                context = match.group().casefold()

                if not any(
                    phrase in context
                    for phrase in (
                        "not recommended",
                        "not the best option",
                        "not the optimal choice",
                        "rejected",
                        "infeasible",
                    )
                ):
                    errors.append(
                        "Infeasible alternative presented as recommended: "
                        f"{alt_name}."
                    )
                    break

        return errors

    @staticmethod
    def validate_orchestrator_explanation(
        explanation: str,
        impact: Dict[str, Any] | None,
        risk: Dict[str, Any] | None,
        recommended: Dict[str, Any] | None,
    ) -> List[str]:
        """Validate Agent E's briefing against authoritative Python facts."""

        errors = []
        text = explanation.casefold()

        errors.extend(
            ORVIXLLMAgents.validate_impact_explanation(
                explanation,
                impact,
            )
        )

        if recommended:
            recommended_name = str(
                recommended.get("name", "")
            ).strip()

            if (
                not recommended_name
                or recommended_name.casefold() not in text
            ):
                errors.append(
                    "The Python-recommended alternative is missing "
                    "from the manager briefing."
                )
        elif not any(
            phrase in text
            for phrase in (
                "no feasible",
                "operational escalation",
                "escalation required",
            )
        ):
            errors.append(
                "The briefing does not explain that no feasible "
                "recovery alternative is available."
            )

        approval_phrases = (
            "human approval",
            "operator approval",
            "manager approval",
            "approval is required",
            "requires approval",
        )

        if not any(
            phrase in text for phrase in approval_phrases
        ):
            errors.append(
                "The briefing does not clearly require human approval."
            )

        forbidden_claims = (
            "vehicle has been dispatched",
            "vehicle was dispatched",
            "vehicle is dispatched",
            "shipment has been rerouted",
            "shipment was rerouted",
            "recovery plan has been executed",
            "recovery plan was executed",
            "action has been executed",
            "action was executed",
        )

        if any(
            phrase in text for phrase in forbidden_claims
        ):
            errors.append(
                "The briefing incorrectly claims an operational action "
                "has been executed."
            )

        if risk:
            risk_score = next(
                (
                    risk[key]
                    for key in (
                        "risk_score",
                        "overall_risk_score",
                        "composite_risk_score",
                    )
                    if risk.get(key) is not None
                ),
                None,
            )

            risk_tier = next(
                (
                    risk[key]
                    for key in ("risk_tier", "tier")
                    if risk.get(key) is not None
                ),
                None,
            )

            if (
                risk_score is not None
                and not ORVIXLLMAgents._metric_value_is_grounded(
                    explanation,
                    ["risk score", "risk index"],
                    risk_score,
                )
            ):
                errors.append(
                    "The manager briefing has an incorrect or missing "
                    "risk score."
                )

            if risk_tier is not None:
                if str(risk_tier).casefold() not in text:
                    errors.append(
                        "The manager briefing has an incorrect or missing "
                        "risk tier."
                    )

        return errors

    @staticmethod
    def _build_agent_payload(
        index: int,
        facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a role-specific payload from Python-validated facts."""

        shipment_context = facts.get("shipment_context", {})

        if index == 1:
            return {
                "shipment_context": shipment_context,
                "detected_events": facts.get("events", []),
            }

        if index == 2:
            return {
                "shipment_context": shipment_context,
                "risk_assessment": facts.get("risk"),
                "relevant_events": facts.get("events", []),
            }

        if index == 3:
            return {
                "shipment_context": shipment_context,
                "business_impact": facts.get("impact"),
            }

        if index == 4:
            return {
                "shipment_context": shipment_context,
                "recovery_alternatives": facts.get(
                    "alternatives", []
                ),
                "recommended_alternative": facts.get("recommended"),
            }

        if index == 5:
            return {
                "shipment_context": shipment_context,
                "workflow_stage": facts.get("workflow_stage"),
                "detected_events": facts.get("events", []),
                "risk_assessment": facts.get("risk"),
                "business_impact": facts.get("impact"),
                "recommended_alternative": facts.get("recommended"),
                "human_approval_required": True,
            }

        raise ValueError(f"Invalid ORVIX agent index: {index}")

    def run(
        self,
        pipeline_result: Dict[str, Any],
        shipment_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Run all five chained agents using Python-validated results."""

        pipeline_result = to_json_safe(pipeline_result or {})
        shipment_context = to_json_safe(shipment_context or {})

        raw_facts = {
            "shipment_context": shipment_context,
            "events": pipeline_result.get("detected_events", []),
            "risk": pipeline_result.get("risk_assessment"),
            "impact": pipeline_result.get("business_impact"),
            "alternatives": pipeline_result.get(
                "recovery_alternatives", []
            ),
            "recommended": pipeline_result.get(
                "recommended_alternative"
            ),
            "workflow_stage": pipeline_result.get("workflow_stage"),
        }

        facts = to_json_safe(raw_facts)

        outputs = []
        preceding_agent_outputs = []

        for index, (name, role_prompt) in enumerate(
            self.ROLES,
            start=1,
        ):
            system_prompt = (
                self.COMMON_RULES
                + "\n\nAGENT ROLE:\n"
                + role_prompt
            )

            payload = self._build_agent_payload(index, facts)

            payload["preceding_agent_outputs"] = (
            preceding_agent_outputs[-1:]
)

            try:
                explanation = self.client.chat(
                    system_prompt,
                    payload,
                )


                validation_errors = []

                if index == 3:
                    validation_errors = (
                        self.validate_impact_explanation(
                            explanation,
                            facts["impact"],
                        )
                    )

                elif index == 4:
                    validation_errors = (
                        self.validate_recovery_explanation(
                            explanation,
                            facts["alternatives"] or [],
                            facts["recommended"],
                        )
                    )

                elif index == 5:
                    validation_errors = (
                        self.validate_orchestrator_explanation(
                            explanation,
                            facts["impact"],
                            facts["risk"],
                            facts["recommended"],
                        )
                    )

                if validation_errors:
                    raise ValueError(
                        "LLM explanation failed fact validation: "
                        + " ".join(validation_errors)
                    )

                item = {
                    "agent": name,
                    "status": "LLM_COMPLETED",
                    "model": self.client.model,
                    "explanation": explanation,
                }

            except Exception as exc:
                print(
                    f"[ORVIX] ERROR in {name}: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

                validation_failed = str(exc).startswith(
                    "LLM explanation failed fact validation:"
                )

                item = {
                    "agent": name,
                    "status": (
                        "LLM_VALIDATION_FALLBACK"
                        if validation_failed
                        else "LLM_UNAVAILABLE_FALLBACK"
                    ),
                    "model": getattr(
                        self.client,
                        "model",
                        "unknown",
                    ),
                    "explanation": (
                        "The AI explanation did not match the "
                        "authoritative Python results. The "
                        "deterministic backend result remains "
                        "authoritative."
                        if validation_failed
                        else (
                            "A complete LLM explanation could not be "
                            "validated. The deterministic Python backend "
                            "result remains authoritative."
                        )
                    ),
                    "error": str(exc)[:500],
                }

            outputs.append(item)
            preceding_agent_outputs.append(item)

            print(
                f"[ORVIX] Finished agent {index}/5: "
                f"{name} - {item['status']}",
                flush=True,
            )

        return {
            "provider": "Ollama (local)",
            "model": getattr(
                self.client,
                "model",
                "unknown",
            ),
            "agents": outputs,
            "completed_count": sum(
                item["status"] == "LLM_COMPLETED"
                for item in outputs
            ),
            "total_count": len(outputs),
            "human_approval_required": True,
        }
