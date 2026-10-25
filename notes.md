# Process Notes

# Project Setup:
# Created the GitHub repo, venv and the structure of folders and files.

# Pipeline Skeleton:
# Built run.py with 3 fake stages (understand, generate and verify), which will eventually write all required outputs. Six starter questions are being used, which cover math, science and social studies, as well as all 3 types of questions (technical diagrams, illustrations and combinations). The images generated for the questions will be blank placeholders with text showing the question id only for now.

# Real understand stage:
# Replaced the fake understand stage in run.py with an actual stage that calls Claude Haiku 5.5 (cheapest Claude model) to return route, route reason and json spec, which is then validated using code. Costs are also calculated using the token count. 
# After initial run, M-03 was routed to geometry instead of layered, so SYSTEM_PROMPT was modified to give the model more clarity over when to use layered and when to use geometry.