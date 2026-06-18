"""XSD validation for NFS-e Nacional (ADN) DPS and NFSe documents, schema v1.01.

Two schemas are bundled under ``mcp_nfe_br/schemas/nfse/``, both from the
official v1.01 package (`nfse-esquemas_xsd-v1-01-20260209.zip`):

- ``DPS_v1.01.xsd`` — for the Declaração de Prestação de Serviços submitted
  by the contributor. ``<ds:Signature>`` is optional (``minOccurs="0"``) in
  TCDPS, so this schema validates both unsigned and signed DPS documents.
- ``NFSe_v1.01.xsd`` — for the NFS-e returned by ADN after processing.
  ``<ds:Signature>`` is mandatory in TCNFSe (added by ADN).

``NFSeXSDValidator.validate`` selects the schema automatically based on the
XML root element local name:
- root = ``DPS`` → ``DPS_v1.01.xsd``
- root = ``NFSe`` → ``NFSe_v1.01.xsd``
- other → error

Namespace: ``http://www.sped.fazenda.gov.br/nfse``
`[Verified locally — NFSe_v1.01.xsd, DPS_v1.01.xsd]`
"""

from __future__ import annotations

import importlib.resources

from lxml import etree
from mcp_einvoicing_core import BaseDocumentValidator, DocumentValidationResult
from mcp_einvoicing_core.xml_utils import safe_fromstring, safe_parser

_SCHEMA_PACKAGE = "mcp_nfe_br.schemas.nfse"
_SCHEMA_FILE_DPS = "DPS_v1.01.xsd"
_SCHEMA_FILE_NFSE = "NFSe_v1.01.xsd"
_SCHEMA_VERSION_DPS = "NFS-e Nacional DPS v1.01 (ADN, 2026-02-09)"
_SCHEMA_VERSION_NFSE = "NFS-e Nacional NFSe v1.01 (ADN, 2026-02-09)"

_NFSE_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_ROOT_TAG_DPS = f"{{{_NFSE_NAMESPACE}}}DPS"
_ROOT_TAG_NFSE = f"{{{_NFSE_NAMESPACE}}}NFSe"


def _load_schema(schema_file: str) -> etree.XMLSchema:
    schema_dir = importlib.resources.files(_SCHEMA_PACKAGE)
    schema_path = schema_dir / schema_file
    with importlib.resources.as_file(schema_path) as path:
        return etree.XMLSchema(etree.parse(str(path), safe_parser(load_dtd=True)))


class NFSeXSDValidator(BaseDocumentValidator):
    """Validates NFS-e Nacional DPS or NFSe XML against bundled v1.01 XSDs.

    Selects the schema automatically from the root element tag:
    - ``DPS`` → ``DPS_v1.01.xsd`` (validates unsigned and signed DPS)
    - ``NFSe`` → ``NFSe_v1.01.xsd`` (validates ADN-signed NFS-e)
    """

    def __init__(self) -> None:
        self._schema_dps = _load_schema(_SCHEMA_FILE_DPS)
        self._schema_nfse = _load_schema(_SCHEMA_FILE_NFSE)

    def get_schema_version(self) -> str:
        return _SCHEMA_VERSION_DPS

    def get_schema_path(self) -> str | None:
        schema_dir = importlib.resources.files(_SCHEMA_PACKAGE)
        return str(schema_dir / _SCHEMA_FILE_DPS)

    def validate(self, document_content: str | bytes) -> DocumentValidationResult:
        if isinstance(document_content, str):
            document_content = document_content.encode("utf-8")

        try:
            doc = safe_fromstring(document_content)
        except etree.XMLSyntaxError as exc:
            return DocumentValidationResult(
                valid=False,
                errors=[f"XML malformado: {exc}"],
                metadata={"schema_version": _SCHEMA_VERSION_DPS},
            )
        except ValueError as exc:
            return DocumentValidationResult(
                valid=False,
                errors=[str(exc)],
                metadata={"schema_version": _SCHEMA_VERSION_DPS},
            )

        root_tag = doc.tag
        if root_tag == _ROOT_TAG_DPS:
            schema = self._schema_dps
            schema_version = _SCHEMA_VERSION_DPS
        elif root_tag == _ROOT_TAG_NFSE:
            schema = self._schema_nfse
            schema_version = _SCHEMA_VERSION_NFSE
        else:
            return DocumentValidationResult(
                valid=False,
                errors=[
                    f"Elemento raiz inesperado: {root_tag!r}. "
                    f"Esperado '{_ROOT_TAG_DPS}' (DPS) ou '{_ROOT_TAG_NFSE}' (NFSe)."
                ],
                metadata={"schema_version": _SCHEMA_VERSION_DPS},
            )

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
