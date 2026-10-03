"""Tab Engine (Phase 3): fingering optimizer, Block Mode, playability, แนะนำคีย์/capo"""
from .blocks import coverage, custom_block, generate_blocks
from .engine import PRESETS, TabSettings, alternatives, generate_tab
from .keysuggest import suggest

__all__ = ["PRESETS", "TabSettings", "alternatives", "coverage", "custom_block", "generate_blocks", "generate_tab", "suggest"]
