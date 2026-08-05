"""Coloration syntaxique des extraits, rendue en HTML pour Qt.

Qt ne comprend qu'un sous-ensemble de CSS : on demande donc à Pygments des
styles en ligne (`noclasses`) plutôt qu'une feuille de style, et on assemble
soi-même le bloc `<pre>` pour maîtriser la police et l'interligne.
"""

from __future__ import annotations

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

COULEUR_FOND_CODE = "#1a1b1e"
COULEUR_TEXTE_CODE = "#c8ccd4"

# SF Mono d'abord : `apparence.enregistrer_police_du_code` la déclare à Qt au
# démarrage. Les deux noms parce que les deux fichiers du système ne s'annoncent
# pas pareil. Menlo suit et reprend la main sans bruit si rien n'a pu être
# enregistré — c'est le cas hors macOS, et le rendu reste correct.
POLICE_CODE = "SF Mono, '.SF NS Mono', Menlo, Monaco, Consolas, monospace"

# Ordre de préférence : le premier style installé gagne. Les versions de
# Pygments n'embarquent pas toutes les mêmes thèmes.
_STYLES_PREFERES = ("one-dark", "dracula", "nord-darker", "monokai")

# Ce que l'application appelle un langage, traduit en lexer Pygments.
_LEXERS = {
    "python": "python",
    "typescript": "typescript",
    "ts": "typescript",
    "tsx": "tsx",
    "javascript": "javascript",
}


def _premier_style_disponible() -> str:
    from pygments.styles import get_all_styles

    disponibles = set(get_all_styles())
    for style in _STYLES_PREFERES:
        if style in disponibles:
            return style
    return "default"


_STYLE = _premier_style_disponible()


def colorer(code: str, langage: str) -> str:
    """Rend le code en HTML coloré, prêt pour un `QTextEdit`.

    Un langage inconnu n'est pas une erreur bloquante : mieux vaut afficher le
    code sans couleur que refuser la question.
    """
    nom_lexer = _LEXERS.get(langage.lower(), langage.lower())
    try:
        lexer = get_lexer_by_name(nom_lexer, stripnl=False)
    except ClassNotFound:
        lexer = get_lexer_by_name("text", stripnl=False)

    formateur = HtmlFormatter(noclasses=True, nowrap=True, style=_STYLE)
    corps = highlight(code, lexer, formateur)

    return (
        f'<pre style="font-family:{POLICE_CODE}; font-size:12px;'
        f' line-height:150%; color:{COULEUR_TEXTE_CODE};'
        f' white-space:pre; margin:0;">{corps}</pre>'
    )
