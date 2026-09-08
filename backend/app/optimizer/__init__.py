"""The optimizer.

Four pieces, in the order they run:

  problem.py   turns the API's network into flat arrays the search can hammer
  encoding.py  turns a vector of numbers into a set of delivery routes
  fitness.py   turns a set of routes into one number: how bad it is
  qpso.py      searches the space of vectors for the one with the lowest number

Nothing here imports FastAPI and nothing here needs a server running. That is
deliberate: the algorithm has to be testable and demonstrable on its own, from
the command line, before any of it is wired to a browser.
"""

from .encoding import decode, encode
from .fitness import Solution, Weights, evaluate
from .problem import Problem
from .qpso import OptimizeResult, QPSOParams, optimize

__all__ = [
    "Problem",
    "decode",
    "encode",
    "Weights",
    "Solution",
    "evaluate",
    "QPSOParams",
    "OptimizeResult",
    "optimize",
]
