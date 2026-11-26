"""Running reledmac.xslt in a test the way tex/latex.py runs it.

The stylesheet holds no typography default of its own and requires every typography
parameter, so a test that transforms a document directly needs the same parameters the
driver would compute for it. These helpers compute them, from the settings model's
defaults unless a test supplies settings of its own.
"""

from __future__ import annotations

from lxml import etree

from opensiddur.common.xslt import xslt_transform_string
from opensiddur.exporter.settings import DistributionSettings
from opensiddur.exporter.tex.latex import XSLT_FILE, typography_parameters
from opensiddur.exporter.typography import TypographyConfig

Settings = TypographyConfig | dict | None

#: For a test whose pages are counted: no distribution notice and no back page.
NO_NOTICES = DistributionSettings(notice="none", back_notice="none")


def _config(typography: Settings) -> TypographyConfig:
    if typography is None:
        return TypographyConfig()
    if isinstance(typography, dict):
        return TypographyConfig.model_validate(typography)
    return typography


def stylesheet_parameters(xml: str, typography: Settings = None) -> dict:
    """Every parameter the stylesheet needs for ``xml``, with no metadata appendix.

    ``typography`` is a ``TypographyConfig``, or the ``typography`` section of a
    settings file as a dict; by default, the settings model's defaults.
    """
    root = etree.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    return {
        "additional-preamble": "",
        "additional-postamble": "",
        **typography_parameters(_config(typography), root),
    }


def transform(xml: str, typography: Settings = None, **params) -> str:
    """Transform ``xml`` with reledmac.xslt. ``params`` override the computed parameters.

    ``layout`` is a setting as well as a parameter — the typography preamble depends on
    it too — so with no ``typography`` of its own a ``layout`` is taken as the setting,
    and one that disagrees with the ``typography`` given is refused: the preamble and
    the document would be set for two different layouts.
    """
    if "layout" in params:
        if typography is None:
            typography = {"parallel": {"layout": params["layout"]}}
        elif _config(typography).parallel.layout.value != params["layout"]:
            raise ValueError(
                f"layout={params['layout']!r} disagrees with the settings' "
                f"{_config(typography).parallel.layout.value!r}"
            )
    full = stylesheet_parameters(xml, typography)
    full.update(params)
    return xslt_transform_string(XSLT_FILE, xml, xslt_params=full)
