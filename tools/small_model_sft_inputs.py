"""Shared complete-answer encoding; also available to the isolated standalone worker."""
from tools.small_model_worker import causal_example, full_completion_example

__all__ = ["causal_example", "full_completion_example"]
