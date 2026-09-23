"""
jev_cot.controller.actions
==========================
Defines the canonical action space for the Adaptive CoT controller.
"""

from enum import StrEnum


class Action(StrEnum):
    """
    The 6 valid routing actions the controller can take.
    Reference: PRD §6.1
    """

    CONTINUE = "CONTINUE"
    RETRIEVE = "RETRIEVE"
    COMPUTE = "COMPUTE"
    BRANCH = "BRANCH"
    STOP = "STOP"
    ESCALATE = "ESCALATE"
