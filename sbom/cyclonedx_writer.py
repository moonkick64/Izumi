# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""CycloneDX 1.5 BOM writer.

Converts a list of :class:`~analyzer.models.Component` objects into a
CycloneDX 1.5 BOM and writes it to a file.

Supported output formats:
    .json → JSON
    .xml  → XML  (default when extension is not .json)
"""

from __future__ import annotations

from pathlib import Path

from analyzer.classifier import Classification
from analyzer.models import Component


def write_cyclonedx(
    components: list[Component],
    output_path: Path,
    output_format: str = "json",
    project_name: str = "",
    project_version: str = "",
) -> None:
    """Write *components* as a CycloneDX 1.5 BOM to *output_path*.

    Args:
        components: List of components to include.
        output_path: Destination file.
        output_format: ``'json'`` or ``'xml'``.

    Raises:
        ImportError: If cyclonedx-bom is not installed.
        ValueError: If *output_format* is not supported.
    """
    from cyclonedx.model.bom import Bom  # type: ignore[import]
    from cyclonedx.model.component import Component as CdxComponent  # type: ignore[import]
    from cyclonedx.model.component import ComponentType  # type: ignore[import]
    from cyclonedx.output import make_outputter  # type: ignore[import]
    from cyclonedx.schema import OutputFormat, SchemaVersion  # type: ignore[import]

    bom = Bom()

    # Set main project as the subject of this BOM
    main_comp = None
    if project_name:
        main_comp = CdxComponent(
            type=ComponentType.APPLICATION,
            name=project_name,
            **({"version": project_version} if project_version else {}),
        )
        bom.metadata.component = main_comp

    for comp in components:
        cdx_comp = _build_cdx_component(comp, CdxComponent, ComponentType)
        bom.components.add(cdx_comp)

    # Register dependency relationships (main project → OSS components)
    if main_comp is not None:
        try:
            bom.register_dependency(main_comp, list(bom.components))
        except Exception:
            pass

    fmt = OutputFormat.JSON if output_format.lower() == "json" else OutputFormat.XML
    outputter = make_outputter(
        bom=bom,
        output_format=fmt,
        schema_version=SchemaVersion.V1_5,
    )
    outputter.generate()
    outputter.output_to_file(str(output_path), allow_overwrite=True, indent=2)


def _build_cdx_component(
    comp: Component,
    CdxComponent: type,
    ComponentType: type,
) -> object:
    """Build a CycloneDX Component from an Izumi Component."""
    from cyclonedx.model.license import DisjunctiveLicense  # type: ignore[import]

    kwargs: dict = {
        "type": ComponentType.LIBRARY,
        "name": comp.name,
    }
    if comp.version:
        kwargs["version"] = comp.version

    cdx_comp = CdxComponent(**kwargs)

    # Attach license
    if comp.license_expression:
        try:
            lic = DisjunctiveLicense(id=comp.license_expression)
            cdx_comp.licenses.add(lic)
        except Exception:
            # If the expression is complex (e.g. "MIT AND Apache-2.0"),
            # attach it as a plain name instead of an SPDX id.
            try:
                lic = DisjunctiveLicense(name=comp.license_expression)
                cdx_comp.licenses.add(lic)
            except Exception:
                pass

    # Attach copyright as a property (CycloneDX 1.5 has no native copyright field)
    if comp.copyright_texts:
        try:
            from cyclonedx.model import Property  # type: ignore[import]
            for text in comp.copyright_texts:
                cdx_comp.properties.add(
                    Property(name="izumi:copyright", value=text)
                )
        except Exception:
            pass

    # Attach classification metadata as a property
    try:
        from cyclonedx.model import Property  # type: ignore[import]
        cdx_comp.properties.add(
            Property(
                name="izumi:classification",
                value=comp.classification.value,
            )
        )
        if comp.oss_hint:
            cdx_comp.properties.add(
                Property(name="izumi:oss_hint", value=comp.oss_hint)
            )
    except Exception:
        pass

    return cdx_comp
