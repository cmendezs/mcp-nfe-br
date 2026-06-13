"""XSD validation for NF-e/NFC-e (modelo 55/65, schema 4.00) documents.

Validates against a **derivative** of the official PL_010d schema bundled
under ``mcp_nfe_br/schemas/nfe/``: ``nfe_v4.00_unsigned.xsd`` /
``leiauteNFe_v4.00_unsigned.xsd``. The only change from the official
``nfe_v4.00.xsd`` / ``leiauteNFe_v4.00.xsd`` is that ``<ds:Signature>``
(last child of ``<NFe>``) is changed from mandatory to ``minOccurs="0"``.

This is necessary because Phase 1 defers ICP-Brasil XML-DSig signing
(`NFeGenerator` emits unsigned `<NFe><infNFe>…</infNFe></NFe>`), but the
official schema requires `<Signature>` as a structural element of `<NFe>`
regardless of whether signature *verification* is performed — schema
validation and signature verification are independent SEFAZ checks.
`[Inference]`: re-validating a *signed* document (a later phase) should use
the unmodified official `nfe_v4.00.xsd`, not this derivative.
"""

from __future__ import annotations

import importlib.resources

from lxml import etree
from mcp_einvoicing_core import BaseDocumentValidator, DocumentValidationResult
from mcp_einvoicing_core.xml_utils import safe_fromstring, safe_parser

_SCHEMA_VERSION = "NF-e/NFC-e 4.00 (PL_010d / NT 2026.004, unsigned variant)"
_SCHEMA_PACKAGE = "mcp_nfe_br.schemas.nfe"
_SCHEMA_FILE = "nfe_v4.00_unsigned.xsd"


def _load_schema() -> etree.XMLSchema:
    schema_dir = importlib.resources.files(_SCHEMA_PACKAGE)
    schema_path = schema_dir / _SCHEMA_FILE
    with importlib.resources.as_file(schema_path) as path:
        return etree.XMLSchema(etree.parse(str(path), safe_parser(load_dtd=True)))


class NFeXSDValidator(BaseDocumentValidator):
    """Validates NF-e/NFC-e 4.00 XML against the bundled PL_010d XSD (unsigned variant)."""

    def __init__(self) -> None:
        self._schema = _load_schema()

    def get_schema_version(self) -> str:
        return _SCHEMA_VERSION

    def get_schema_path(self) -> str | None:
        schema_dir = importlib.resources.files(_SCHEMA_PACKAGE)
        return str(schema_dir / _SCHEMA_FILE)

    def validate(self, document_content: str | bytes) -> DocumentValidationResult:
        if isinstance(document_content, str):
            document_content = document_content.encode("utf-8")

        try:
            doc = safe_fromstring(document_content)
        except etree.XMLSyntaxError as exc:
            return DocumentValidationResult(
                valid=False,
                errors=[f"XML malformado: {exc}"],
                metadata={"schema_version": _SCHEMA_VERSION},
            )
        except ValueError as exc:
            return DocumentValidationResult(
                valid=False,
                errors=[str(exc)],
                metadata={"schema_version": _SCHEMA_VERSION},
            )

        if self._schema.validate(doc):
            return DocumentValidationResult(
                valid=True,
                metadata={"schema_version": _SCHEMA_VERSION},
            )

        errors = [str(err) for err in self._schema.error_log]
        return DocumentValidationResult(
            valid=False,
            errors=errors,
            metadata={"schema_version": _SCHEMA_VERSION},
        )
