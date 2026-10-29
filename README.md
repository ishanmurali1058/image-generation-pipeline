# Image generation pipeline for school assessment questions

A Python pipeline that takes school assessment questions (Math, Science and Social Studies, Grades 3 to 10) and produces an image for each one, checks that the image matches the question, retries or repairs it when a check fails, and flags anything it cannot get right for a person to review.

Each question is planned by an LLM, routed to the drawing method that suits it, drawn, and verified. Exact diagrams (charts, triangles, circuits, maps) are drawn with code, so their values are exact and can be checked with arithmetic. Open-ended scenes are generated with an image model and checked by a vision model acting as a judge. Combination images draw exact measurements on top of a scene.

## How it works

1. **Plan:** one call to Claude Haiku 5.5 reads the question and returns a JSON plan: what the image must show and hide, the route, the reason for that route, and a structured spec.
2. **Check the spec:** route-specific checks run before anything is drawn, such as the values matching the image notes, the figure giving the question's answer, and the answer not being labelled.
3. **Draw:** the chosen route renders the image as PNG (and SVG where the method produces vector output).
4. **Check the image:** readback checks on the drawing, and for generated images, a vision-model judge.
5. **Repair or redraw:** if the plan was wrong, the failed checks are sent back to Claude for a corrected plan. If only the picture was wrong, the same plan is redrawn. After three attempts, or straight away for unfixable problems, the question is flagged with the reason.
6. **Log:** every attempt, check result and cost is written to the question's metadata file.

## Routes

- **`chart`** draws bar, line and pie charts with matplotlib.
- **`geometry`** draws triangles, solving them from the given angles and sides with trigonometry, then drawing them with matplotlib.
- **`circuit`** draws series and parallel circuits with schemdraw, and uses a small circuit simulator for its answer checks.
- **`map`** draws maps of India's states and union territories with geopandas, using DataMeet's boundaries.
- **`illustration`** generates open-ended scenes with no text using FLUX.1 schnell on fal.ai, checked by a Claude judge.
- **`layered`** draws right-triangle measurements or grids on top of a generated scene, with a plain drawn scene as a fallback.

Questions routed to `template` (lab apparatus, instruments, exact counts) and other routes are flagged, because those routes are not built yet.

## Setup

These steps assume Python 3.12 or later (the project was developed on Python 3.14).

1. **Clone the repository**

   git clone https://github.com/ishanmurali1058/image-generation-pipeline.git
   cd image-generation-pipeline

2. **Create and activate a virtual environment**

   python -m venv .venv
   - Windows (PowerShell): `.venv\Scripts\activate`
   - macOS or Linux: `source .venv/bin/activate`

3. **Install the dependencies**

   pip install -r requirements.txt

4. **Add your API keys**

   Copy `.env.example` to a new file called `.env`, and fill in your keys:

   ANTHROPIC_API_KEY=anthropic-key
   FAL_KEY=fal-key

   `.env` is listed in `.gitignore`, so it is never committed. Environment variables with the same names set outside `.env` are used instead, if present.

## Running the pipeline

python run.py --input samples/questions.json --out outputs/

- `--input`: a JSON file containing a list of questions (a `{"questions": [...]}` wrapper is also accepted).
- `--out`: the folder to write outputs into. It is created if it does not exist.

The run prints its progress, and finishes with `Done. N questions processed.` A question that hits any error is flagged with the reason, and the run carries on with the next question.

### Input format

json
{
  "id": "M-01",
  "subject": "Math",
  "grade": 5,
  "question": "The bar graph shows the number of trees planted by four classes. How many trees were planted in total?",
  "options": ["38", "42", "45", "48"],
  "answer": "42",
  "image_notes": "Class 6: 8, Class 7: 12, Class 8: 10, Class 9: 12. Vertical bars, y-axis from 0 to 14 in steps of 2."
}

`answer`, `image_notes` and `options` are optional. Questions without an `id` are given one (`Q-001`, `Q-002`, …), and IDs containing characters that are not allowed in file names are made safe.

### Outputs

For each question, the output folder contains:

- `<id>.png`: the image, or a placeholder if the question was flagged before an image could be drawn.
- `<id>.svg`: a vector copy, for routes that produce vector output.
- `<id>.json`: the route and the reason for it, the spec, every attempt with its verification results and cost, the final status (`accepted` or `flagged`), the flag reason, and the total cost.

The folder also contains `summary.csv`, with each question's status, route, attempt count and cost, followed by the total and average cost.

## External services and models

- **Anthropic API, Claude Haiku 5.5** (`claude-haiku-5-5`): used for planning, the image judge, and locating objects in layered scenes. Costs are tracked at $0.10 per million input tokens and $0.50 per million output tokens.
- **fal.ai, FLUX.1 schnell** (`fal-ai/flux/schnell`): used for illustrations and layered scene backgrounds. Costs are tracked at $0.003 per megapixel.

Prices are set in `config/prices.yaml`. Costs are calculated from the token counts each API reports and the size of each generated image.

## Sample set and results

`samples/questions.json` contains 27 questions across Math, Science and Social Studies, covering all three image types, including 7 combination questions and deliberately hard cases: hidden answers, exact counts, questions between categories, questions with some error and questions with no answer or image notes. Each question records its source.

The outputs from the final run are in `outputs/`. In that run, 22 questions were accepted and 5 flagged, at an average cost of $0.0029 per image.

## Project structure

run.py                      Single command that runs the whole pipeline
pipeline/
    understand.py           Planning: the Claude prompt and plan validation
    stages.py               Generate and verify stages that call the routes
    repair.py               Builds repair feedback from failed checks
    llm.py                  All Claude calls and their costs
    images.py               All FLUX calls and their costs
routes/
    common.py               Checks and helpers shared by every route
    chart.py 
    geometry.py
    circuit.py
    maps.py
    illustration.py
    layered.py
config/prices.yaml          Prices used for cost tracking
data/india_states.geojson   State boundaries for the map route
samples/questions.json      Sample question set
outputs/                    Outputs of the final sample run

### Adding a route

Each route is one file in `routes/` with three functions:

- `check_spec(plan, question)`: checks before drawing, returning a list of check results.
- `render(spec, png_path, svg_path)`: draws the image, returning anything the image checks need (and a `cost`, if it calls a paid service).
- `check_render(plan, files, question=None)`: checks after drawing.

Register it in `routes/__init__.py`, and describe its spec format in the planning prompt in `pipeline/understand.py`.

## Data sources

India state boundaries: [DataMeet India community](http://datameet.org/), from https://github.com/datameet/maps, licensed under CC BY 4.0. The boundaries were simplified for this project.

## License

MIT License. See `LICENSE`.