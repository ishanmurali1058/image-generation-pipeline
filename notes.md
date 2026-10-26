# Process Notes

# Project Setup:
# Created the GitHub repo, venv and the structure of folders and files.

# Pipeline Skeleton:
# Built run.py with 3 fake stages (understand, generate and verify), which will eventually write all required outputs. Six starter questions are being used, which cover math, science and social studies, as well as all 3 types of questions (technical diagrams, illustrations and combinations). The images generated for the questions will be blank placeholders with text showing the question id only for now.

# Real understand stage:
# Replaced the fake understand stage in run.py with an actual stage that calls Claude Haiku 5.5 (cheapest Claude model) to return route, route reason and json spec, which is then validated using code. Costs are also calculated using the token count. 
# After initial run, M-03 was routed to geometry instead of layered, so SYSTEM_PROMPT was modified to give the model more clarity over when to use layered and when to use geometry.

# Chart route:
# Added a route to draw actual bar, line and pie charts in png and svg from the spec information using matplotlib. The remaining routes which haven't been created yet still have placeholder images, and are now flagged. 

# Chart verification:
# Added 7 different checks (6 spec checks and 1 render check) for charts, they are label and value counts, axis range, values and labels against the image notes, answer consistency, answer leaks, and a readback of the drawn values. Changed the answer to M-01 from 42 to 40 to check whether answer consistency would flag the question, and it did. Running it revealed that the svg was still getting created even when the question was flagged, so modified the code to delete svg when question is flagged.

# Repair and smarter retries:
# Failed checks are now sent back to Claude with previous plan, and unfixable failures like routes which haven't been built yet are flagged after one attempt itself along with the reason. Verified its working by changing the answer to M-01 from 42 to 40, Claude kept the notes' values on each attempt instead of modifying them to match the given answer (40).