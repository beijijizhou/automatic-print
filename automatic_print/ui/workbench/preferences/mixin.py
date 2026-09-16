"""Compatibility mixin composed from the separated parameter state flows."""

from .actions import PreferenceActionsMixin
from .load import load_layout_preferences
from .save import save_layout_preferences


class PreferencesMixin(PreferenceActionsMixin):
    def load_layout_preferences(self) -> None:
        load_layout_preferences(self)

    def save_layout_preferences(self, *_args, notify=True) -> None:
        save_layout_preferences(self, notify=notify)
