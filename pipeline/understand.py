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

For the map route, only maps of India's states and union territories are supported. The spec must be:
{
  "shaded": ["Assam"],
  "labelled": [],
  "title": "",
  "unknown": "Assam"
}
- shaded: the states or union territories to colour in, using their full names.
- labelled: the states or union territories to write names on. Never label the state the student must identify.
- title: a title for the map, or "". Never put the answer in the title.
- unknown: the shaded state the student must identify, or null if the student identifies nothing.

For the illustration route, the spec must be:
{
  "prompt": "A detailed description of the scene for an image model",
  "style": "flat, colourful children's book illustration",
  "must_contain": ["a person shaping clay on a potter's wheel", "a village house"],
  "answer_from_image": true
}
- prompt: describe the scene, people, objects, setting and composition in detail. Never ask for any words, letters, numbers, labels or signs, and never put text in quotation marks.
- style: a simple, clear style suitable for a school paper.
- must_contain: 1 to 5 short things that must be clearly visible in the picture.
- answer_from_image: true if the student needs the picture to choose the answer, false if the picture only decorates the question.

For the layered route, the spec has these fields for every figure:
- overlay: right_triangle (a ladder, line of sight or string forming a right triangle with something vertical and the ground) or grid (squares marked over an area).
- scene: a description of the background scene for an image model. Never include the ladder, slide, ramp, string, rope, measurement lines, grid, words or numbers: the code draws the slanted line itself.
- style: a simple style suitable for a school paper, such as "flat, colourful children's book illustration".
- background: "generated" to draw the scene with an image model, or "drawn" for a plain drawn scene. Use "generated" unless told otherwise.
- units: the unit of length, such as "m".
- unknown: what the student must find.

For a right_triangle overlay, also include:
{"vertical_object": "brick wall", "target": "the top of the wall", "dashed": false, "base": null, "height": null, "slant": 10, "angle": 60}
- vertical_object: the upright thing, such as a brick wall, tower or tree.
- target: where the slanted line ends, such as "the top of the tower" or "the window".
- slant_style: ladder, sight_line (for an angle of elevation) or string (for a kite).
- base: the distance along the ground; height: the height up the vertical object; slant: the length of the slanted line; angle: the angle in degrees between the ground and the slanted line. Give only the values the student is told; set the rest to null.
- unknown: base, height, slant, angle or null. It must be null above.

For a grid overlay, also include:
{"columns": 6, "rows": 4, "square_size": 1}
- columns and rows: whole numbers of squares across and down; square_size: the side of one square.
- unknown: area, perimeter or null.

For other routes, describe the image in the spec as clear key-value fields.

Rules:
- If image_notes are given, use their values exactly.
- If they are not given, choose sensible values that fit the question and its answer.
- Never show the answer in the image unless the question requires the student to see it.
- If the student must count objects in a picture, choose the template route, since no other route can draw an exact number of objects.
- If the question already gives every number the student needs and the picture only sets the scene, choose illustration, set answer_from_image to false, and do not show any numbers in the picture.
"""

def understand(question, feedback = None):
    user_prompt = json.dumps(question, ensure_ascii=False, indent=2)
    if feedback:
        user_prompt += "\n\n" + feedback
    try:
      result = call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception as error:
      return {"must_show": "", "must_not_show": [], "route": "none", "route_reason": "The planning call failed.",
              "spec": {}, "error": f"planning call failed: {error}", "cost": 0.0}

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