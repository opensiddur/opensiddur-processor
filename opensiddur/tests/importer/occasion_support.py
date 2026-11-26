"""Deciding a running order's occasion gates against what the calendar derives for a date."""

from lxml import etree

from opensiddur.exporter.compiler import CompilerProcessor
from opensiddur.exporter.condition_eval import (
    TriState,
    evaluate_condition,
    parse_condition_element,
)
from opensiddur.exporter.conditional_settings import yaml_to_declaration_entries
from opensiddur.exporter.linear import get_linear_data, reset_linear_data

JERUSALEM = {"latitude": 31.78, "longitude": 35.22}
NEW_YORK = {"latitude": 40.71, "longitude": -74.01}


class CalendarDay:
    """The settings a date, place and time derive, as the compiler would hold them."""

    def __init__(self, *, date, place=JERUSALEM, time=None):
        reset_linear_data()
        declarations = {
            "opensiddur:gregorian-date": dict(zip(("year", "month", "day"), date)),
            "opensiddur:location": place,
        }
        if time is not None:
            declarations["opensiddur:time"] = dict(zip(("hour", "minute"), time))
        linear_data = get_linear_data()
        CompilerProcessor.load_init_settings(linear_data, yaml_to_declaration_entries(declarations))
        self.processor = CompilerProcessor.__new__(CompilerProcessor)
        self.processor.linear_data = linear_data

    def decide(self, conditional: etree.ElementBase) -> TriState:
        """How a `j:conditional`'s condition resolves on this day."""
        return evaluate_condition(parse_condition_element(conditional), self.processor)
