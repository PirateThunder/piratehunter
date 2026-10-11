"""Константы core-api."""

API_TITLE = "hunter_core core-api"
API_VERSION = "0.2.0"
INTERNAL_PREFIX = "/internal"

MODE_FULL = "full"
MODE_EXPRESS = "express"
MODES = (MODE_FULL, MODE_EXPRESS)

SESSION_ACTIVE = "active"
SESSION_FINISHED = "finished"

# нейтральная константа stack-фактора в режиме категории (PRD §7.5.4)
NEUTRAL_STACK_VALUE = 0.5
