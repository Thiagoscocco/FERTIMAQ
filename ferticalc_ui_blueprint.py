"""Blueprint de interface para reaproveitar o estilo do FertiCalc.

Este modulo funciona como guia detalhado do layout, cores, tipografia e
componentes utilizados no FertiCalc com customtkinter. Copie-o para qualquer
novo projeto da linha (por exemplo, FertiMaq) e utilize as funcoes auxiliares
para montar rapidamente uma interface com o mesmo visual.

Como usar em um novo projeto:
1. Importe este modulo e chame `init_theme()` antes de criar a janela raiz.
2. Instancie `ctk.CTk()` e aplique `configure_window()` para titulo, tamanho e
   cores padrao.
3. Use `build_tab_shell()` para criar o container principal com Tabview.
4. Estruture cada aba com `create_card()`, `section_title()` e `body_text()`
   seguindo os espacos fornecidos em `SPACING`.
5. Para overlay de boas-vindas ou telas informativas, reutilize
   `build_intro_overlay()` junto do caminho do logo.
6. Sempre que precisar de botoes principais, use `primary_button()` que ja
   aplica as cores oficiais da marca.

Todas as constantes, dataclasses e helpers daqui foram extraidas diretamente da
implementacao do FertiCalc (app/ui). Manter este arquivo atualizado garante
consistencia visual entre os softwares da linha.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple

import customtkinter as ctk
from PIL import Image

# ---------------------------------------------------------------------------
# Tokens de tema (cores e tipografia)
# ---------------------------------------------------------------------------

BACKGROUND_LIGHT = "#f8f9fa"
BACKGROUND_DARK = "#2b2b2b"

PANEL_LIGHT = "#ffffff"
PANEL_DARK = "#3a3a3a"

TEXT_PRIMARY = "#5a7bbf"
TEXT_SECONDARY = "#666666"
TEXT_ON_DARK = "#eef1fb"

PRIMARY_BLUE = "#2196F3"
PRIMARY_HOVER = "#1976D2"
SUCCESS_GREEN = "#4CAF50"
WARNING_ORANGE = "#FF9800"
WARNING_HOVER = "#E65100"

FONT_SIZE_TITLE = 16
FONT_SIZE_HEADING = 14
FONT_SIZE_BODY = 12

PADX_STANDARD = 15
PADX_SMALL = 5
PADY_STANDARD = 15
PADY_SMALL = 5

PALETTE: Dict[str, Tuple[str, str] | str] = {
    "background": (BACKGROUND_LIGHT, BACKGROUND_DARK),
    "panel": (PANEL_LIGHT, PANEL_DARK),
    "accent_primary": (PRIMARY_BLUE, PRIMARY_HOVER),
    "text_primary": TEXT_PRIMARY,
    "text_secondary": TEXT_SECONDARY,
    "text_on_dark": TEXT_ON_DARK,
    "status_success": SUCCESS_GREEN,
    "status_warning": (WARNING_ORANGE, WARNING_HOVER),
}

TYPOGRAPHY = {
    "title": {"size": FONT_SIZE_TITLE, "weight": "bold"},
    "heading": {"size": FONT_SIZE_HEADING, "weight": "bold"},
    "body": {"size": FONT_SIZE_BODY, "weight": "normal"},
    "body_bold": {"size": FONT_SIZE_BODY, "weight": "bold"},
}

SPACING = {
    "outer_padding": {"padx": PADX_STANDARD, "pady": PADY_STANDARD},
    "card_padding": {"padx": PADX_STANDARD, "pady": PADY_STANDARD},
    "compact_padding": {"padx": PADX_STANDARD, "pady": PADY_SMALL},
    "between_cards": {"pady": (0, PADY_STANDARD)},
    "footer": {"pady": (PADY_SMALL, 0)},
    "intro_overlay": {"padx": 60, "pady": 50},
}

# ---------------------------------------------------------------------------
# Dataclasses que documentam o layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowSpec:
    """Especificacoes da janela principal."""

    title: str = "FertiCalc - Calculadora de Calagem e Adubacao"
    width: int = 960
    height: int = 680
    min_width: int = 880
    min_height: int = 620
    center_on_screen: bool = True
    fg_color: Tuple[str, str] = (BACKGROUND_LIGHT, BACKGROUND_DARK)
    grid_weights: Tuple[int, int] = (1, 1)


@dataclass(frozen=True)
class TabsetSpec:
    """Define a organizacao das abas principais."""

    names: Tuple[str, ...] = ("CALAGEM", "ADUBACAO", "RESULTADOS")
    container_fg: Tuple[str, str] = (BACKGROUND_LIGHT, BACKGROUND_DARK)
    segmented_button_fg: Tuple[str, str] = (BACKGROUND_LIGHT, BACKGROUND_DARK)


@dataclass(frozen=True)
class CardSpec:
    """Configuracao padrao de cards (frames) usados nas abas."""

    fg_color: Tuple[str, str] = (PANEL_LIGHT, PANEL_DARK)
    corner_radius: int = 18
    anchor: str = "nsew"


@dataclass(frozen=True)
class IntroOverlaySpec:
    """Layout da camada inicial de boas-vindas."""

    overlay_color: str = "#2d2f36"
    scrollable_color: str = "#343741"
    scrollbar_color: Tuple[str, str] = ("#4f6ecf", "#4059a6")
    logo_width: int = 260
    heading_size: int = 24
    highlight_color: str = TEXT_PRIMARY


@dataclass(frozen=True)
class FooterSpec:
    """Rodape que aparece abaixo das abas."""

    text: str = "DEV Thiagoscocco UFRGS 2025"
    font_size: int = FONT_SIZE_BODY
    text_color: str = TEXT_SECONDARY
    weight: str = "bold"


WINDOW_SPEC = WindowSpec()
TABSET_SPEC = TabsetSpec()
CARD_SPEC = CardSpec()
INTRO_SPEC = IntroOverlaySpec()
FOOTER_SPEC = FooterSpec()


# ---------------------------------------------------------------------------
# Helpers principais para aplicar o blueprint
# ---------------------------------------------------------------------------


def init_theme(dark_mode: bool = True) -> None:
    """Inicializa o tema do customtkinter de forma consistente."""

    ctk.set_appearance_mode("dark" if dark_mode else "light")


def configure_window(app: ctk.CTk, spec: WindowSpec = WINDOW_SPEC) -> None:
    """Aplica titulo, tamanho, centralizacao e grade padrao."""

    app.title(spec.title)
    app.minsize(spec.min_width, spec.min_height)

    geometry = f"{spec.width}x{spec.height}"
    if spec.center_on_screen:
        pos_x = (app.winfo_screenwidth() // 2) - (spec.width // 2)
        pos_y = (app.winfo_screenheight() // 2) - (spec.height // 2)
        geometry = f"{geometry}+{pos_x}+{pos_y}"
    app.geometry(geometry)
    app.configure(fg_color=spec.fg_color)
    app.grid_rowconfigure(0, weight=spec.grid_weights[0])
    app.grid_columnconfigure(0, weight=spec.grid_weights[1])


def build_tab_shell(
    app: ctk.CTk,
    spec: TabsetSpec = TABSET_SPEC,
    *,
    padding: Mapping[str, int | Tuple[int, int]] = SPACING["outer_padding"],
) -> Tuple[ctk.CTkFrame, ctk.CTkTabview]:
    """Cria o frame container e o tabview com as abas especificadas."""

    container = ctk.CTkFrame(app, fg_color=spec.container_fg)
    container.grid(row=0, column=0, sticky="nsew", **padding)
    container.grid_rowconfigure(0, weight=1)
    container.grid_rowconfigure(1, weight=0)
    container.grid_columnconfigure(0, weight=1)

    tabview = ctk.CTkTabview(
        container,
        fg_color=spec.container_fg,
        segmented_button_fg_color=spec.segmented_button_fg,
    )
    tabview.grid(row=0, column=0, sticky="nsew")

    tabs: Dict[str, ctk.CTkFrame] = {}
    for name in spec.names:
        tabs[name] = tabview.add(name)

    return container, tabview


def create_card(
    parent: ctk.CTkBaseClass,
    *,
    spec: CardSpec = CARD_SPEC,
    row: int,
    column: int,
    sticky: str | None = None,
    padding: Mapping[str, int | Tuple[int, int]] | None = None,
) -> ctk.CTkFrame:
    """Gera um frame com a mesma estetica usada nas abas."""

    frame = ctk.CTkFrame(parent, fg_color=spec.fg_color, corner_radius=spec.corner_radius)
    frame.grid(row=row, column=column, sticky=sticky or spec.anchor, **(padding or SPACING["between_cards"]))
    return frame


def section_title(
    parent: ctk.CTkBaseClass,
    text: str,
    *,
    text_color: Tuple[str, str] | str = (TEXT_PRIMARY, "#4a9eff"),
    padx: int = PADX_STANDARD,
    pady: Tuple[int, int] = (PADY_STANDARD, PADY_SMALL),
) -> ctk.CTkLabel:
    """Cria rotulos usados como titulo de secao."""

    font = ctk.CTkFont(size=FONT_SIZE_HEADING, weight="bold")
    label = ctk.CTkLabel(parent, text=text, font=font, text_color=text_color, anchor="w")
    label.grid(row=0, column=0, columnspan=10, sticky="ew", padx=padx, pady=pady)
    return label


def body_text(
    parent: ctk.CTkBaseClass,
    text: str,
    row: int,
    column: int,
    *,
    justify: str = "left",
    wraplength: int | None = None,
    text_color: str | Tuple[str, str] = TEXT_SECONDARY,
    anchor: str = "w",
    padx: int = PADX_STANDARD,
    pady: Tuple[int, int] = (0, PADY_SMALL),
    font_weight: str = "normal",
) -> ctk.CTkLabel:
    """Helper para textos auxiliares dentro dos cards."""

    font = ctk.CTkFont(size=FONT_SIZE_BODY, weight=font_weight)
    label = ctk.CTkLabel(
        parent,
        text=text,
        font=font,
        justify=justify,
        wraplength=wraplength,
        text_color=text_color,
        anchor=anchor,
    )
    label.grid(row=row, column=column, sticky="ew", padx=padx, pady=pady)
    return label


def primary_button(
    parent: ctk.CTkBaseClass,
    text: str,
    command: Callable[[], None],
    *,
    row: int,
    column: int = 0,
    padx: int = PADX_STANDARD,
    pady: Tuple[int, int] = (0, PADY_STANDARD),
) -> ctk.CTkButton:
    """Botao principal com cores e fonte padronizadas."""

    font = ctk.CTkFont(size=FONT_SIZE_HEADING, weight="bold")
    btn = ctk.CTkButton(
        parent,
        text=text,
        font=font,
        fg_color=PRIMARY_BLUE,
        hover_color=PRIMARY_HOVER,
        text_color="#ffffff",
        command=command,
    )
    btn.grid(row=row, column=column, sticky="ew", padx=padx, pady=pady)
    return btn


def footer_label(parent: ctk.CTkFrame, spec: FooterSpec = FOOTER_SPEC) -> ctk.CTkLabel:
    """Cria o rodape institucional localizado abaixo das abas."""

    font = ctk.CTkFont(size=spec.font_size, weight=spec.weight)
    label = ctk.CTkLabel(parent, text=spec.text, font=font, text_color=spec.text_color, anchor="center")
    label.grid(row=1, column=0, sticky="ew", **SPACING["footer"])
    return label


# ---------------------------------------------------------------------------
# Overlay inicial (tela de boas-vindas / onboarding)
# ---------------------------------------------------------------------------


def load_logo_image(path: str | Path, target_width: int = INTRO_SPEC.logo_width) -> ctk.CTkImage | None:
    """Carrega a imagem do logo adaptando o tamanho para o overlay."""

    caminho = Path(path)
    if not caminho.exists():
        return None
    imagem = Image.open(caminho)
    largura, altura = imagem.size
    alvo_altura = int(target_width * altura / max(largura, 1))
    return ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(target_width, alvo_altura))


def build_intro_overlay(
    parent: ctk.CTkFrame,
    *,
    logo_path: str | Path | None = None,
    spec: IntroOverlaySpec = INTRO_SPEC,
    on_close: Callable[[], None] | None = None,
) -> Tuple[ctk.CTkFrame, MutableMapping[str, ctk.CTkLabel | ctk.CTkFrame]]:
    """Monta o overlay de apresentacao usado no FertiCalc."""

    overlay = ctk.CTkFrame(parent, fg_color=spec.overlay_color)
    overlay.place(relx=0.5, rely=0.5, relwidth=1.0, relheight=1.0, anchor="center")

    content = ctk.CTkScrollableFrame(
        overlay,
        fg_color=spec.scrollable_color,
        scrollbar_button_color=spec.scrollbar_color[0],
        scrollbar_button_hover_color=spec.scrollbar_color[1],
    )
    content.pack(expand=True, fill="both", **SPACING["intro_overlay"])
    content.grid_columnconfigure(0, weight=1)

    titulo_font = ctk.CTkFont(size=spec.heading_size, weight="bold")
    corpo_font = ctk.CTkFont(size=FONT_SIZE_BODY + 1)
    destaque_font = ctk.CTkFont(size=FONT_SIZE_BODY + 2, weight="bold")

    elementos: MutableMapping[str, ctk.CTkLabel | ctk.CTkFrame] = {}
    row = 0

    if logo_path:
        imagem = load_logo_image(logo_path, target_width=spec.logo_width)
        if imagem is not None:
            elementos["logo"] = ctk.CTkLabel(content, image=imagem, text="")
            elementos["logo"].grid(row=row, column=0, pady=(0, 24))
            row += 1

    elementos["titulo"] = ctk.CTkLabel(
        content,
        text="BEM-VINDO AO FERTICALC",
        font=titulo_font,
        text_color=spec.highlight_color,
    )
    elementos["titulo"].grid(row=row, column=0, pady=(0, 18), sticky="n")
    row += 1

    elementos["descricao"] = ctk.CTkLabel(
        content,
        text=(
            "Ferramenta integrada para planejamento de calagem e adubacao. "
            "Transforme analises de solo em recomendacoes objetivas e aplique "
            "esta mesma estrutura em novos produtos da linha."
        ),
        font=corpo_font,
        wraplength=720,
        justify="center",
        text_color=TEXT_ON_DARK,
    )
    elementos["descricao"].grid(row=row, column=0, pady=(0, 24), padx=30, sticky="n")
    row += 1

    elementos["bloco_instr"] = ctk.CTkFrame(content, fg_color="#3d414d", corner_radius=18)
    elementos["bloco_instr"].grid(row=row, column=0, pady=(0, 24), padx=30, sticky="ew")
    elementos["bloco_instr"].grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        elementos["bloco_instr"],
        text="INSTRUCOES DE USO DO LAYOUT",
        font=destaque_font,
        text_color=spec.highlight_color,
        anchor="w",
    ).grid(row=0, column=0, sticky="w", pady=(14, 6), padx=20)

    bullets = [
        "Organize entradas em cards com canto arredondado e paddings simetricos.",
        "Utilize rotulos em caixa alta para titulos de seccao com cor primaria.",
        "Priorize textos do corpo em tom neutro (#666666) sobre fundos claros.",
        "Para resultados numericos, mantenha labels justificados a esquerda.",
    ]
    for idx, item in enumerate(bullets, start=1):
        ctk.CTkLabel(
            elementos["bloco_instr"],
            text=f"- {item}",
            font=corpo_font,
            text_color=TEXT_ON_DARK,
            justify="left",
            wraplength=680,
        ).grid(row=idx, column=0, sticky="w", padx=20, pady=2)
    row += 1

    elementos["aviso"] = ctk.CTkLabel(
        content,
        text=(
            "Este overlay pode ser adaptado para apresentar novidades, disclaimers "
            "ou fluxos de onboarding em novos softwares. Basta alterar textos "
            "mantendo cores e proporcoes."
        ),
        font=corpo_font,
        text_color="#b6bdcd",
        wraplength=720,
        justify="center",
    )
    elementos["aviso"].grid(row=row, column=0, pady=(0, 24), padx=40, sticky="n")
    row += 1

    elementos["call_to_action"] = ctk.CTkButton(
        content,
        text="COMECAR",
        font=titulo_font,
        fg_color="#4f6ecf",
        hover_color="#4059a6",
        text_color="#ffffff",
        width=280,
        height=46,
        corner_radius=18,
        command=on_close or overlay.destroy,
    )
    elementos["call_to_action"].grid(row=row, column=0, pady=(0, 12))

    return overlay, elementos


# ---------------------------------------------------------------------------
# Notas descritivas para manter consistencia visual
# ---------------------------------------------------------------------------


LAYOUT_NOTES = """
- Janela base 960x680, com minimo 880x620 e centralizacao na tela.
- Grid raiz: 1 linha / 1 coluna com weight 1 para permitir redimensionamento.
- Container principal usa frame com padding 15 e cores pareadas claro/escuro.
- Tabview recebe nomes em caixa alta. Para novos projetos, ajuste apenas o texto.
- Cada aba utiliza CTkScrollableFrame ou Frame com cards empilhados verticalmente.
- Cards possuem corner_radius 18, paddings simetricos e variacao de tons claro/escuro.
- Fontes: headings em tamanho 14 bold, corpo em tamanho 12 regular.
- Botoes principais ocupam toda a largura do card, com azul #2196F3 e hover #1976D2.
- Rodape institucional alinhado ao centro com fonte corpo bold e cor #666666.
- Overlay de boas-vindas cobre 100% do container e usa scroll para textos longos.
"""


BLUEPRINT_SUMMARY = {
    "window": WINDOW_SPEC,
    "tabset": TABSET_SPEC,
    "card": CARD_SPEC,
    "intro_overlay": INTRO_SPEC,
    "footer": FOOTER_SPEC,
    "palette": PALETTE,
    "typography": TYPOGRAPHY,
    "spacing": SPACING,
    "layout_notes": LAYOUT_NOTES,
}


def describe_blueprint() -> Mapping[str, object]:
    """Retorna um snapshot do blueprint completo para inspecao ou serializacao."""

    return BLUEPRINT_SUMMARY


__all__ = [
    "PALETTE",
    "TYPOGRAPHY",
    "SPACING",
    "WINDOW_SPEC",
    "TABSET_SPEC",
    "CARD_SPEC",
    "INTRO_SPEC",
    "FOOTER_SPEC",
    "init_theme",
    "configure_window",
    "build_tab_shell",
    "create_card",
    "section_title",
    "body_text",
    "primary_button",
    "footer_label",
    "load_logo_image",
    "build_intro_overlay",
    "LAYOUT_NOTES",
    "describe_blueprint",
]
