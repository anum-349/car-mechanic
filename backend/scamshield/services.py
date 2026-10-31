"""Backward-compatible import for consumers moving to the logic module."""
from .logic import evaluate

__all__ = ["evaluate"]
