# SPDX-License-Identifier: GPL-3.0-only
# SPDX-FileCopyrightText: 2026 zkojii
"""SPDX 2.3 document writer.

Converts a list of :class:`~analyzer.models.Component` objects into an
SPDX 2.3 document and writes it to a file.

Supported output formats (auto-detected from file extension):
    .spdx / .tag  → tag-value
    .json         → JSON
    .yaml / .yml  → YAML
    .xml          → XML
    .rdf          → RDF/XML
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from analyzer.models import Component


def write_spdx(
    components: list[Component],
    output_path: Path,
    document_name: str = "Izumi-SBOM",
    validate: bool = True,
    project_name: str = "",
    project_version: str = "",
) -> None:
    """Write *components* as an SPDX 2.3 document to *output_path*.

    Args:
        components: List of components to include.
        output_path: Destination file (format inferred from extension).
        document_name: SPDX document name field.
        validate: Whether to validate the document before writing.
            Auto-disabled for empty component lists.

    Raises:
        ImportError: If spdx-tools is not installed.
        ValueError: If the document fails validation.
    """
    from spdx_tools.spdx.model import (  # type: ignore[import]
        Actor,
        ActorType,
        CreationInfo,
        Document,
        ExternalPackageRef,
        ExternalPackageRefCategory,
        Package,
        Relationship,
        RelationshipType,
    )
    from spdx_tools.spdx.model.spdx_no_assertion import SpdxNoAssertion  # type: ignore[import]
    from spdx_tools.spdx.writer.write_anything import write_file  # type: ignore[import]
    from license_expression import get_spdx_licensing  # type: ignore[import]

    licensing = get_spdx_licensing()

    # Use project_name/version in the document name (metadata only, not a package)
    if project_name:
        doc_name = f"{project_name}-{project_version}" if project_version else project_name
    else:
        doc_name = document_name

    ns_uuid = uuid.uuid4()
    creation_info = CreationInfo(
        spdx_version="SPDX-2.3",
        spdx_id="SPDXRef-DOCUMENT",
        name=doc_name,
        document_namespace=f"https://izumi.example.com/sbom/{ns_uuid}",
        creators=[Actor(ActorType.TOOL, "Izumi")],
        created=datetime.now(timezone.utc),
    )

    packages: list[Package] = []
    relationships: list[Relationship] = []

    for comp in components:
        spdx_id = f"SPDXRef-{_spdx_safe_id(comp.name)}"

        # Parse license expression into a boolean.Expression object
        license_val = _parse_license(comp.license_expression, licensing)

        # Copyright text
        if comp.copyright_texts:
            copyright_val: str | SpdxNoAssertion = "\n".join(comp.copyright_texts)
        else:
            copyright_val = SpdxNoAssertion()

        purl = f"pkg:generic/{comp.name}"
        if comp.version:
            purl += f"@{comp.version}"

        supplier_val = (
            Actor(ActorType.ORGANIZATION, comp.supplier)
            if comp.supplier
            else SpdxNoAssertion()
        )

        pkg = Package(
            spdx_id=spdx_id,
            name=comp.name,
            version=comp.version or None,
            supplier=supplier_val,
            download_location=SpdxNoAssertion(),
            license_concluded=license_val,
            license_declared=license_val,
            copyright_text=copyright_val,
            files_analyzed=False,
            comment=_build_comment(comp),
            external_references=[
                ExternalPackageRef(
                    category=ExternalPackageRefCategory.PACKAGE_MANAGER,
                    reference_type="purl",
                    locator=purl,
                )
            ],
        )
        packages.append(pkg)
        relationships.append(
            Relationship("SPDXRef-DOCUMENT", RelationshipType.DESCRIBES, spdx_id)
        )

    # SPDX validation fails on empty documents; disable it in that case
    should_validate = validate and len(packages) > 0

    document = Document(
        creation_info=creation_info,
        packages=packages,
        files=[],
        snippets=[],
        annotations=[],
        relationships=relationships,
        extracted_licensing_info=[],
    )

    write_file(document, str(output_path), validate=should_validate)


def _parse_license(
    license_expression: str | None,
    licensing: object,
) -> object:
    """Parse *license_expression* into a boolean.Expression, or return SpdxNoAssertion."""
    from spdx_tools.spdx.model.spdx_no_assertion import SpdxNoAssertion  # type: ignore[import]

    if not license_expression or license_expression.upper() == "NOASSERTION":
        return SpdxNoAssertion()
    try:
        return licensing.parse(license_expression, validate=True)
    except Exception:
        return SpdxNoAssertion()


def _spdx_safe_id(name: str) -> str:
    """Convert *name* to a valid SPDX identifier (alphanumeric + hyphen)."""
    safe = re.sub(r"[^a-zA-Z0-9\-]", "-", name)
    if safe and safe[0].isdigit():
        safe = "pkg-" + safe
    return safe or "pkg-unknown"


def _build_comment(comp: Component) -> str:
    parts = [f"Classification: {comp.classification.value}"]
    parts.append(f"Reason: {comp.classification_reason}")
    if comp.oss_hint:
        parts.append(f"LLM hint: {comp.oss_hint}")
    if comp.user_comment:
        parts.append(f"User comment: {comp.user_comment}")
    return " | ".join(parts)
