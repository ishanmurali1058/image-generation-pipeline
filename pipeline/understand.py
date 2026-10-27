import json

from pipeline.llm import call_llm

ROUTES = ["chart", "geometry", "circuit", "ray", "map", "template", "illustration", "layered"]

REQUIRED_FIELDS = ["must_show", "must_not_show", "route", "route_reason", "spec"]

SYSTEM_PROMPT = """You plan images for school assessment questions (Grades 3 to 10).
Read the question and reply with ONLY a JSON object. No other text, no markdown.

Choose exactly one route:
- chart: bar, line or pie charts, histograms, pictographs, number lines, graphs of functions
- geometry: plain geometry figures made only of lines, points and shapes, such as triangles, angles, circles, parallel lines
- circuit: electric circuit diagrams
- ray: ray diagrams for mirrors and lenses
- map: maps with shaded or labelled regions
- template: lab apparatus, measuring instruments, clocks, coins, biology diagrams
- illustration: scenes, characters and objects where nothing the student reads must be exact
- layered: an illustrated or realistic scene (people, buildings, objects, landscapes) with exact measurements, angles or a grid drawn on top

If anything the student reads from the image must be exact, never choose illustration.
If the question or image_notes ask for an illustrated or realistic scene that also needs exact measurements, choose layered, not geometry.

Reply in this format:
{
  "must_show": "what the image must contain",
  "must_not_show": ["things the image must hide, such as the answer"],
  "route": "one route name from the list",
  "route_reason": "one sentence on why this route fits",
  "spec": {}
}

For the chart route, the spec must be:
{
  "chart_type": "bar",
  "title": "chart title",
  "x_label": "x-axis label",
  "y_label": "y-axis label",
  "labels": ["category names in order"],
  "values": [numbers in the same order],
  "y_min": 0,
  "y_max": number,
  "y_step": number
}
For the chart route, also add a top-level field (next to "spec", not inside it):
"answer_check": {"operation": "...", "labels": ["the bar labels the answer uses"]}
operation must be one of:
- value: the answer is one bar's value
- sum: the answer is the total of the listed bars
- difference: the first listed bar minus the second
- average: the mean of the listed bars
- max_label: the answer is the name of the highest bar among those listed (empty list means all bars)
- min_label: the answer is the name of the lowest bar among those listed (empty list means all bars)
- none: the answer cannot be worked out from the chart values

For the geometry route, only triangles are supported. The spec must be:
{
  "shape": "triangle",
  "vertices": ["A", "B", "C"],
  "angles": {"A": 50, "B": 65, "C": null},
  "sides": {"AB": null, "BC": null, "CA": null},
  "units": "cm",
  "unknown": "C"
}
- vertices: the three corner names used in the question, as a list.
- angles: the angle in degrees at each vertex, but only if the student is told it; otherwise null.
- sides: each side's length, but only if the student is told it; otherwise null.
- unknown: the vertex (for an angle) or side (for a length) the student must find. It must be null in angles or sides. Use null if the student finds nothing in the figure.
- Never put the answer in angles or sides.
- A right angle the student is told about is 90 in angles.

For the circuit route, the spec must be:
{
  "source": {"type": "cell", "label": "", "volts": null},
  "series": [{"type": "switch", "label": "S", "state": "closed"}, {"type": "bulb", "label": "B1", "ohms": null}],
  "branches": []
}
- source: type is cell or battery. volts only if the student is told it, otherwise null.
- series: the components on the main wire, in order.
- branches: for parallel parts, a list of branches, each a list of components in order. All branches join the same two points. Use [] for a circuit with no parallel parts.
- component types: bulb, resistor, switch, ammeter, voltmeter. A switch needs "state": "open" or "closed". ohms only if the student is told it, otherwise null.
- Give each component the label used in the question, or "" if it has none.

For the circuit route, also add a top-level "answer_check" (next to "spec", not inside it):
- {"operation": "lit", "target": "B2", "removed": ["B1"], "switches": {"S": "open"}, "expected": false}
  for questions about whether a bulb glows. removed lists fused or removed components, switches lists any switch changes the question describes, and expected is true if the correct answer means the target glows, false if not.
- {"operation": "total_resistance"} or {"operation": "current"} for calculation questions.
- {"operation": "none"} if the answer cannot be worked out from the circuit.

For other routes, describe the image in the spec as clear key-value fields.

Rules:
- If image_notes are given, use their values exactly.
- If they are not given, choose sensible values that fit the question and its answer.
- Never show the answer in the image unless the question requires the student to see it.
"""

def understand(question, feedback = None):
    user_prompt = json.dumps(question, ensure_ascii=False, indent=2)
    if feedback:
        user_prompt += "\n\n" + feedback
    result = call_llm(SYSTEM_PROMPT, user_prompt)

    try:
        plan = parse_plan(result["text"])
    except ValueError as error:
        plan = {
            "must_show": "",
            "must_not_show": [],
            "route": "none",
            "route_reason": "The LLM reply could not be used.",
            "spec": {},
            "error": str(error),
        }

    plan["cost"] = result["cost"]
    return plan

def parse_plan(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Reply contained no JSON object.")

    try:
        plan = json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise ValueError(f"Reply was not valid JSON: {error}")

    missing = [field for field in REQUIRED_FIELDS if field not in plan]
    if missing:
        raise ValueError(f"Reply is missing fields: {missing}")

    if plan["route"] not in ROUTES:
        raise ValueError(f"Reply chose an unknown route: {plan['route']}")

    return plan