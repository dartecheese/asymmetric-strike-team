"""AI-powered agent wrappers for the Grinding Wheel pipeline.

Each agent fetches its own data via the existing Python code,
then calls the shared LLM for reasoning and decision-making.

The model is managed by ai_agents.engine — a single Ollama instance
that stays loaded across all pipeline stages.
"""

from .engine import OllamaEngine, MLXEngine, auto_select_engine
from .whisperer import AIWhisperer
from .actuary import AIActuary
from .slinger import AISlinger
from .reaper import AIReaper
from .researcher import Researcher, ResearcherVerdict
from .rating import EntryRating, parse_rating
from . import memory
