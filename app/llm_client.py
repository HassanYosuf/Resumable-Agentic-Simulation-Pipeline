import os
from typing import Dict, List

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def decompose_instruction(instruction: str) -> Dict:
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY)
            prompt = (
                "Decompose the following simulation request into a small directed acyclic graph of concrete steps. "
                "Return a JSON object with a `tasks` list. Each task needs `id`, `name`, `description`, and `depends_on` list. "
                "Do not return any extra text.\n\n"
                f"Instruction: {instruction}"
            )
            response = client.responses.create(model="gpt-4.1-mini", input=prompt)
            text = response.output_text if hasattr(response, "output_text") else str(response)
            import json

            return json.loads(text)
        except Exception:
            return _local_decompose_stub(instruction)
    return _local_decompose_stub(instruction)


def _local_decompose_stub(instruction: str) -> Dict:
    normalized = instruction.strip().lower()
    tasks = [
        {
            "id": "setup",
            "name": "prepare-environment",
            "description": "Prepare the simulation environment and configure input parameters.",
            "depends_on": [],
        },
        {
            "id": "run-simulation",
            "name": "execute-simulation",
            "description": "Run the long-running simulation and stream periodic progress updates.",
            "depends_on": ["setup"],
        },
        {
            "id": "collect-results",
            "name": "collect-results",
            "description": "Aggregate simulation outputs, verify integrity, and store results.",
            "depends_on": ["run-simulation"],
        },
    ]
    if "validation" in normalized or "verify" in normalized:
        tasks.append(
            {
                "id": "validate",
                "name": "validate-results",
                "description": "Validate the output against expected invariants and quality checks.",
                "depends_on": ["collect-results"],
            }
        )
    return {"tasks": tasks}
