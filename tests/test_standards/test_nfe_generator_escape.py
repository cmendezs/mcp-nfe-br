"""XML-escape parity tests for free-text fields (BR-SH-3).

Mirrors IT-SH-1 v0.2.3 fixtures. For each of the six audit-named fields,
verifies that special characters are properly escaped in the generated XML.
"""

from __future__ import annotations

import re

from lxml import etree

from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from tests.conftest import make_emitente, make_endereco, make_line, make_nfe

_SPECIAL = '& < > " \''
_ENCODED = ("&amp;", "&lt;", "&gt;")

# Pattern that catches a bare & not followed by amp;/lt;/gt;/quot;/apos;
_BARE_AMP_RE = re.compile(r"&(?!(amp|lt|gt|quot|apos);)")


def _assert_escaped(xml: str) -> None:
    assert not _BARE_AMP_RE.search(xml), "bare & found in output"
    etree.fromstring(xml.encode())  # must parse without error


# ---------------------------------------------------------------------------
# xNome (emit block)
# ---------------------------------------------------------------------------


def test_xnome_escapes_special_chars() -> None:
    emit = make_emitente(x_nome=f"Empresa {_SPECIAL} LTDA")
    xml = NFeGenerator().generate(make_nfe(emitente=emit))
    _assert_escaped(xml)
    assert "&amp;" in xml


# ---------------------------------------------------------------------------
# xLgr (logradouro in enderEmit)
# ---------------------------------------------------------------------------


def test_xlgr_escapes_special_chars() -> None:
    end = make_endereco(x_lgr=f"Rua {_SPECIAL}")
    emit = make_emitente(ender_emit=end)
    xml = NFeGenerator().generate(make_nfe(emitente=emit))
    _assert_escaped(xml)


# ---------------------------------------------------------------------------
# xMun (município in enderEmit)
# ---------------------------------------------------------------------------


def test_xmun_escapes_special_chars() -> None:
    end = make_endereco(x_mun=f"Cidade {_SPECIAL}")
    emit = make_emitente(ender_emit=end)
    xml = NFeGenerator().generate(make_nfe(emitente=emit))
    _assert_escaped(xml)


# ---------------------------------------------------------------------------
# xProd (product description on line)
# ---------------------------------------------------------------------------


def test_xprod_escapes_special_chars() -> None:
    line = make_line(description=f"Produto {_SPECIAL}")
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    _assert_escaped(xml)


# ---------------------------------------------------------------------------
# natOp (natureza da operação)
# ---------------------------------------------------------------------------


def test_natop_escapes_special_chars() -> None:
    xml = NFeGenerator().generate(make_nfe(natureza_operacao=f"Venda {_SPECIAL}"))
    _assert_escaped(xml)


# ---------------------------------------------------------------------------
# xPag (descrição do meio de pagamento)
# ---------------------------------------------------------------------------


def test_xpag_escapes_special_chars() -> None:
    from mcp_nfe_br.models.invoice import BRPagamento

    pag = BRPagamento(t_pag="90", v_pag="100.00", x_pag=f"Outro {_SPECIAL}")
    xml = NFeGenerator().generate(make_nfe(pagamentos=[pag]))
    _assert_escaped(xml)
