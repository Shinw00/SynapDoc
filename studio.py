from graph import build_graph
from llm import make_model, make_prompt


graph = build_graph(make_model(), make_prompt())
