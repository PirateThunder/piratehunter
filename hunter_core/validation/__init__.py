"""Валидационный контур hunter_core (PRD §9)."""

from validation.agents import SyntheticAgent
from validation.harness import build_bank, run_session, run_validation
from validation.matching_eval import run_matching_eval

__all__ = ["SyntheticAgent", "build_bank", "run_matching_eval", "run_session", "run_validation"]
