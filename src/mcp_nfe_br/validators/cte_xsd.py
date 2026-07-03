"""XSD validation for CT-e (modelo 57, schema 4.00) documents.

Two schema variants are bundled under ``mcp_nfe_br/schemas/cte/``, both
derived from the official `PL_CTe_400` package, same pattern as
`nfe_xsd.py`:

- ``cte_v4.00_unsigned.xsd`` / ``cteTiposBasico_v4.00_unsigned.xsd`` — a
  derivative where ``<ds:Signature>`` (last child of ``<CTe>``) is changed
  from mandatory to ``minOccurs="0"``. Used for documents produced by
  `CTeGenerator`, which emits unsigned `<CTe><infCte>…</infCte></CTe>`.
- ``cte_v4.00.xsd`` / ``cteTiposBasico_v4.00.xsd`` — the unmodified
  official schema, where `<ds:Signature>` is mandatory. Used once
  `mcp_nfe_br.standards.cte_signer` has applied an ICP-Brasil XML-DSig
  signature.

`CTeXSDValidator` selects between the two automatically: if the document's
`<CTe>` root contains a `<ds:Signature>` child, it is validated against the
official (signed) schema; otherwise against the unsigned derivative.
"""

from __future__ import annotations

import importlib.resources

from lxml import etree
from mcp_einvoicing_core import BaseDocumentValidator, DocumentValidationResult
from mcp_einvoicing_core.xml_utils import safe_fromstring, safe_parser

_SCHEMA_PACKAGE = "mcp_nfe_br.schemas.cte"
_SCHEMA_FILE_UNSIGNED = "cte_v4.00_unsigned.xsd"
_SCHEMA_FILE_SIGNED = "cte_v4.00.xsd"
_SCHEMA_VERSION_UNSIGNED = "CT-e 4.00 (PL_CTe_400, unsigned variant)"
_SCHEMA_VERSION_SIGNED = "CT-e 4.00 (PL_CTe_400, official signed schema)"

_DS_SIGNATURE = "{http://www.w3.org/2000/09/xmldsig#}Signature"


def _load_schema(schema_file: str) -> etree.XMLSchema:
    schema_dir = importlib.resources.files(_SCHEMA_PACKAGE)
    schema_path = schema_dir / schema_file
    with importlib.resources.as_file(schema_path) as path:
        return etree.XMLSchema(etree.parse(str(path), safe_parser(load_dtd=True)))


class CTeXSDValidator(BaseDocumentValidator):
    """Validates CT-e 4.00 XML against the bundled PL_CTe_400 XSD.

    Automatically selects the unsigned derivative or the official
    (signature-required) schema based on whether `<ds:Signature>` is present.
    """

    def __init__(self) -> None:
        self._schema_unsigned = _load_schema(_SCHEMA_FILE_UNSIGNED)
        self._schema_signed = _load_schema(_SCHEMA_FILE_SIGNED)

    def get_schema_version(self) -> str:
        return _SCHEMA_VERSION_UNSIGNED

    def get_schema_path(self) -> str | None:
        schema_dir = importlib.resources.files(_SCHEMA_PACKAGE)
        return str(schema_dir / _SCHEMA_FILE_UNSIGNED)

    def validate(self, document_content: str | bytes) -> DocumentValidationResult:
        if isinstance(document_content, str):
            document_content = document_content.encode("utf-8")

        try:
            doc = safe_fromstring(document_content)
        except etree.XMLSyntaxError as exc:
            return DocumentValidationResult(
                valid=False,
                errors=[f"XML malformado: {exc}"],
                metadata={"schema_version": _SCHEMA_VERSION_UNSIGNED},
            )
        except ValueError as exc:
            return DocumentValidationResult(
                valid=False,
                errors=[str(exc)],
                metadata={"schema_version": _SCHEMA_VERSION_UNSIGNED},
            )

        is_signed = doc.find(_DS_SIGNATURE) is not None
        schema = self._schema_signed if is_signed else self._schema_unsigned
        schema_version = _SCHEMA_VERSION_SIGNED if is_signed else _SCHEMA_VERSION_UNSIGNED

        if schema.validate(doc):
            return DocumentValidationResult(
                valid=True,
                metadata={"schema_version": schema_version},
            )

        errors = [str(err) for err in schema.error_log]
        return DocumentValidationResult(
            valid=False,
            errors=errors,
            metadata={"schema_version": schema_version},
        )
