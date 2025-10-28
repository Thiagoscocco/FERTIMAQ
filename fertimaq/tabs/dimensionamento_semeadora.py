"""Tab responsible for sizing the seeder set based on the existing calculation engine."""

from __future__ import annotations

import math
from dataclasses import replace

import customtkinter as ctk

from ferticalc_ui_blueprint import create_card, primary_button, section_title
from logica_calc import Inputs, calcular

from .base import FertiMaqTab, tab_registry


@tab_registry.register
class DimensionamentoSemeadoraTab(FertiMaqTab):
    tab_id = "dimensionamento_semeadora"
    title = "DIMENSIONAMENTO DA SEMEADORA"

    def __init__(self, app: "FertiMaqApp") -> None:
        super().__init__(app)
        # Conjunto vars
        self._linhas_var = ctk.StringVar(value="7")
        self._sulcador_var = ctk.StringVar(value="Discos/Botinha")
        self._cv_trator_var = ctk.StringVar(value="80.0")
        self._velocidade_var = ctk.StringVar(value="5.6")

        # Area vars
        self._preparo_var = ctk.StringVar(value="Plantio Direto")
        self._solo_var = ctk.StringVar(value="Medio")
        self._aclive_display_var = ctk.StringVar(value="Aclive selecionado: --")

        # Result vars
        self._status_var = ctk.StringVar(value="Informe os dados e calcule o dimensionamento.")
        self._peso_semeadora_var = ctk.StringVar(value="--")
        self._peso_trator_var = ctk.StringVar(value="--")
        self._peso_conjunto_var = ctk.StringVar(value="--")
        self._cv_com_aclive_var = ctk.StringVar(value="--")
        self._cv_plano_var = ctk.StringVar(value="--")
        self._status_label_ref: ctk.CTkLabel | None = None
        self._limite_aclive_var = ctk.StringVar(value="")

    # ------------------------------------------------------------------ #
    # UI assembly
    # ------------------------------------------------------------------ #

    def build(self, frame: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        cards_row = ctk.CTkFrame(scroll, fg_color="transparent")
        cards_row.grid(row=0, column=0, sticky="nsew", padx=20, pady=(0, 20))
        cards_row.grid_columnconfigure((0, 1), weight=1, uniform="cards")

        # Left card: conjunto
        conjunto_card = create_card(
            cards_row,
            row=0,
            column=0,
            sticky="nsew",
            padding={"padx": (0, 10), "pady": (0, 0)},
        )
        conjunto_card.grid_columnconfigure(0, weight=1)
        section_title(conjunto_card, "DIMENSIONAMENTO DO CONJUNTO")

        conjunto_body = ctk.CTkFrame(conjunto_card, fg_color="transparent")
        conjunto_body.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 12))
        conjunto_body.grid_columnconfigure(1, weight=1)

        # Sulcador
        ctk.CTkLabel(conjunto_body, text="Tipo de sulcador", anchor="w").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        self._sulcador_menu = ctk.CTkOptionMenu(
            conjunto_body,
            values=list(self.app.sulcador_options.keys()),
            variable=self._sulcador_var,
            anchor="w",
        )
        self._sulcador_menu.grid(row=0, column=1, sticky="ew", pady=(0, 10), padx=(12, 0))

        # Linhas
        ctk.CTkLabel(conjunto_body, text="Numero de linhas", anchor="w").grid(row=1, column=0, sticky="w", pady=6)
        ctk.CTkEntry(conjunto_body, textvariable=self._linhas_var, width=140).grid(
            row=1, column=1, sticky="ew", padx=(12, 0), pady=6
        )

        # CV disponivel
        ctk.CTkLabel(conjunto_body, text="CV do trator disponivel", anchor="w").grid(row=2, column=0, sticky="w", pady=6)
        ctk.CTkEntry(conjunto_body, textvariable=self._cv_trator_var, width=140).grid(
            row=2, column=1, sticky="ew", padx=(12, 0), pady=6
        )

        # Velocidade
        ctk.CTkLabel(conjunto_body, text="Velocidade desejada (km/h)", anchor="w").grid(
            row=3, column=0, sticky="w", pady=6
        )
        ctk.CTkEntry(conjunto_body, textvariable=self._velocidade_var, width=140).grid(
            row=3, column=1, sticky="ew", padx=(12, 0), pady=6
        )

        primary_button(
            conjunto_card,
            text="Calcular dimensionamento",
            command=self._executar_calculo,
            row=2,
        )

        # Right card: area
        area_card = create_card(
            cards_row,
            row=0,
            column=1,
            sticky="nsew",
            padding={"padx": (10, 0), "pady": (0, 0)},
        )
        area_card.grid_columnconfigure(0, weight=1)
        section_title(area_card, "CARACTERISTICAS DA AREA")

        area_body = ctk.CTkFrame(area_card, fg_color="transparent")
        area_body.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 12))
        area_body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(area_body, text="Preparo do solo", anchor="w").grid(row=0, column=0, sticky="w", pady=6)
        self._preparo_menu = ctk.CTkOptionMenu(
            area_body,
            values=list(self.app.preparo_options.keys()),
            variable=self._preparo_var,
            anchor="w",
        )
        self._preparo_menu.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=6)

        ctk.CTkLabel(area_body, text="Textura do solo", anchor="w").grid(row=1, column=0, sticky="w", pady=6)
        self._solo_menu = ctk.CTkOptionMenu(
            area_body,
            values=list(self.app.solo_options.keys()),
            variable=self._solo_var,
            anchor="w",
        )
        self._solo_menu.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=6)

        ctk.CTkLabel(
            area_body,
            textvariable=self._aclive_display_var,
            anchor="w",
            text_color="#eef1fb",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))

        # Results + recommendations row
        bottom_row = ctk.CTkFrame(scroll, fg_color="transparent")
        bottom_row.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        bottom_row.grid_columnconfigure((0, 1), weight=1, uniform="bottom_cards")

        resultado_card = create_card(
            bottom_row,
            row=0,
            column=0,
            sticky="nsew",
            padding={"padx": (0, 10), "pady": (0, 0)},
        )
        resultado_card.grid_columnconfigure(0, weight=1)
        section_title(resultado_card, "RESULTADOS DO DIMENSIONAMENTO")

        self._status_label_ref = ctk.CTkLabel(
            resultado_card,
            textvariable=self._status_var,
            anchor="w",
            wraplength=320,
            text_color="#666666",
        )
        self._status_label_ref.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 16))
        self._status_var_color("#666666")

        results_frame = ctk.CTkFrame(resultado_card, fg_color="transparent")
        results_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        results_frame.grid_columnconfigure(1, weight=1)

        self._add_result_row(results_frame, 0, "Peso da semeadora (t)", self._peso_semeadora_var)
        self._add_result_row(results_frame, 1, "Peso do trator (t)", self._peso_trator_var)
        self._add_result_row(results_frame, 2, "Peso do conjunto (t)", self._peso_conjunto_var)
        self._add_result_row(results_frame, 3, "CV necessario (com aclive)", self._cv_com_aclive_var)
        self._add_result_row(results_frame, 4, "CV necessario (terreno plano)", self._cv_plano_var)

        recomendacao_card = create_card(
            bottom_row,
            row=0,
            column=1,
            sticky="nsew",
            padding={"padx": (10, 0), "pady": (0, 0)},
        )
        recomendacao_card.grid_columnconfigure(0, weight=1)
        section_title(recomendacao_card, "RECOMENDACOES")

        self._recomendacao_var = ctk.StringVar(value="Calcule o dimensionamento para receber recomendacoes.")
        ctk.CTkLabel(
            recomendacao_card,
            textvariable=self._recomendacao_var,
            anchor="w",
            wraplength=320,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 6))

        ctk.CTkLabel(
            recomendacao_card,
            textvariable=self._limite_aclive_var,
            anchor="w",
            wraplength=320,
            justify="left",
            text_color="#e0c060",
        ).grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))

        # React to slope changes
        self.app.field_vars["slope_selected_deg"].trace_add("write", lambda *_: self._refresh_aclive_label())
        self._refresh_aclive_label()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _add_result_row(self, parent: ctk.CTkFrame, row: int, label: str, var: ctk.StringVar) -> None:
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=row, column=0, sticky="ew", pady=4)
        ctk.CTkLabel(parent, textvariable=var, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=1, sticky="ew", pady=4
        )

    def _refresh_aclive_label(self) -> None:
        text = self.app.field_vars["slope_selected_deg"].get()
        if text:
            self._aclive_display_var.set(f"Aclive selecionado: {text} graus")
        else:
            self._aclive_display_var.set("Aclive selecionado: --")

    def _executar_calculo(self) -> None:
        try:
            linhas = int(self._linhas_var.get())
            cv_disponivel = float(self._cv_trator_var.get().replace(",", "."))
            velocidade = float(self._velocidade_var.get().replace(",", "."))
        except ValueError:
            self._status_var.set("Revise os valores numericos informados.")
            self._status_var_callback(error=True)
            return

        try:
            preparo = self.app.preparo_options[self._preparo_var.get()]
            solo = self.app.solo_options[self._solo_var.get()]
            sulcador = self.app.sulcador_options[self._sulcador_var.get()]
        except KeyError:
            self._status_var.set("Selecione preparo, solo e sulcador validos.")
            self._status_var_callback(error=True)
            return

        slope_deg_text = self.app.field_vars["slope_selected_deg"].get()
        slope_deg = float(slope_deg_text.replace(",", ".")) if slope_deg_text else 0.0
        aclive_percent = math.tan(math.radians(slope_deg)) * 100.0

        base_inputs = Inputs(
            preparo=preparo,
            solo=solo,
            aclive_percent=aclive_percent,
            sulcador=sulcador,
            linhas=linhas,
            cv_trator_disponivel=cv_disponivel,
            velocidade_kmh=velocidade,
        )

        try:
            resultado = calcular(base_inputs)
            plano_inputs = replace(base_inputs, aclive_percent=0.0)
            plano = calcular(plano_inputs)
        except Exception as exc:
            self._status_var.set(f"Falha ao calcular: {exc}")
            self._status_var_callback(error=True)
            return

        self._status_var.set("Dimensionamento calculado com sucesso.")
        self._status_var_callback(error=False)

        peso_conjunto = resultado.peso_semeadora_t + resultado.peso_trator_t
        self._peso_semeadora_var.set(f"{resultado.peso_semeadora_t:,.2f}".replace(",", "."))
        self._peso_trator_var.set(f"{resultado.peso_trator_t:,.2f}".replace(",", "."))
        self._peso_conjunto_var.set(f"{peso_conjunto:,.2f}".replace(",", "."))
        self._cv_com_aclive_var.set(f"{resultado.cv_requerido:,.2f}".replace(",", "."))
        self._cv_plano_var.set(f"{plano.cv_requerido:,.2f}".replace(",", "."))

        recomendacao, limite_info = self._gerar_recomendacao(
            resultado,
            plano,
            cv_disponivel,
            linhas,
            velocidade,
            aclive_percent,
        )
        self._recomendacao_var.set(recomendacao)
        self._limite_aclive_var.set(limite_info)

    def _gerar_recomendacao(
        self,
        resultado: "Results",
        plano: "Results",
        cv_disponivel: float,
        linhas: int,
        velocidade_kmh: float,
        aclive_percent: float,
    ) -> tuple[str, str]:
        deficit = resultado.cv_requerido - cv_disponivel
        if deficit <= 0:
            return "O conjunto consegue atender a velocidade necessaria para a operacao.", ""

        if deficit > 25:
            limite_msg = self._slope_limite_mensagem(plano.cv_requerido, resultado.cv_requerido, cv_disponivel, aclive_percent)
            return (
                "O trator atual nao atende. Considere reduzir o numero de linhas da semeadora "
                "ou utilizar um trator mais potente.",
                limite_msg,
            )

        # deficit <= 25: sugerir reduzir velocidade.
        # cv requerido proporcional a velocidade (kW cresce proporcionalmente). Ajuste multiplicativo:
        velocidade_sugerida = max(1.0, velocidade_kmh * (cv_disponivel / resultado.cv_requerido))
        velocidade_sugerida = round(velocidade_sugerida, 2)
        limite_msg = self._slope_limite_mensagem(plano.cv_requerido, resultado.cv_requerido, cv_disponivel, aclive_percent)
        return (
            "O trator atende se a velocidade for reduzida. "
            f"Sugestao: operar a aproximadamente {velocidade_sugerida} km/h.",
            limite_msg,
        )

    def _slope_limite_mensagem(
        self,
        cv_plano: float,
        cv_total: float,
        cv_disponivel: float,
        aclive_percent: float,
    ) -> str:
        extra_atual = max(cv_total - cv_plano, 0.0)
        extra_disponivel = max(cv_disponivel - cv_plano, 0.0)
        if extra_atual <= 1e-6 or extra_disponivel <= 0.0 or aclive_percent <= 0.0:
            return ""

        proporcao = max(0.0, min(extra_disponivel / extra_atual, 1.0))
        limite_pct = aclive_percent * proporcao
        if limite_pct <= 0.0:
            return ""

        limite_deg = math.degrees(math.atan(limite_pct / 100.0))
        return f"Esse conjunto responderia bem em aclives de ate {limite_deg:.1f} graus nessa velocidade."

    def _status_var_callback(self, *, error: bool) -> None:
        if error:
            self._status_var_color("#b00020")
        else:
            self._status_var_color("#3f7e2d")

    def _status_var_color(self, color: str) -> None:
        if self._status_label_ref is not None:
            self._status_label_ref.configure(text_color=color)

    def on_show(self) -> None:
        self._refresh_aclive_label()
        if self._status_label_ref is not None and self._status_var.get() == "Informe os dados e calcule o dimensionamento.":
            self._status_label_ref.configure(text_color="#666666")

