# -*- coding: utf-8 -*-
"""Tab responsible for plantability calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass

import customtkinter as ctk

from ferticalc_ui_blueprint import create_card, primary_button, section_title
from fertimaq.plantabilidade_calcs import capacidade_campo, consumo_diesel_total, insumos_por_m_linear, sementes_por_ha

from .base import FertiMaqTab, tab_registry


@dataclass
class PlantabilidadeResultados:
    sementes_por_ha: float = 0.0
    sementes_por_m: float = 0.0
    fertilizante_g_por_m: float = 0.0
    espacamento_cm: float = 0.0


@tab_registry.register
class PlantabilidadeTab(FertiMaqTab):
    tab_id = "plantabilidade"
    title = "PLANTABILIDADE"

    def __init__(self, app: "FertiMaqApp") -> None:
        super().__init__(app)

        self._font_label = ctk.CTkFont(size=14)
        self._font_label_bold = ctk.CTkFont(size=15, weight="bold")
        self._font_value = ctk.CTkFont(size=16, weight="bold")
        self._font_status = ctk.CTkFont(size=13, slant="italic")

        self._populacao_var = ctk.StringVar(value="280000")
        self._fertilizante_var = ctk.StringVar(value="200")
        self._espacamento_var = ctk.StringVar(value="45")
        self._germinacao_var = ctk.StringVar(value="98")
        self._sementes_puras_var = ctk.StringVar(value="98")
        self._qualidade_var = ctk.StringVar(value="9")

        # Rendimento operacional agora é compartilhado via app.input_vars
        self._rendimento_operacional_var = self.app.input_vars.get("rendimento_operacional", ctk.StringVar(value="65"))

        self._status_insumos_var = ctk.StringVar(value="Informe os dados e calcule a regulagem.")
        self._sementes_m_var = ctk.StringVar(value="--")
        self._fertilizante_m_var = ctk.StringVar(value="--")
        self._espacamento_cm_var = ctk.StringVar(value="--")
        self._mais_info_vars = {
            "sementes_totais": ctk.StringVar(value="--"),
            "sementes_sacas": ctk.StringVar(value="--"),
            "sementes_m2": ctk.StringVar(value="--"),
            "plantas_m2": ctk.StringVar(value="--"),
            "fertilizante_m2": ctk.StringVar(value="--"),
        }

        self._status_capacidade_var = ctk.StringVar(value="Informe o rendimento operacional e calcule.")
        self._largura_util_var = ctk.StringVar(value="--")
        self._velocidade_var = ctk.StringVar(value="--")
        self._area_total_var = ctk.StringVar(value="--")
        self._potencia_var = ctk.StringVar(value="--")
        self._cce_var = ctk.StringVar(value="--")
        self._tempo_operacao_var = ctk.StringVar(value="--")
        self._consumo_h_var = ctk.StringVar(value="--")
        self._consumo_total_var = ctk.StringVar(value="--")

        self._status_insumos_label: ctk.CTkLabel | None = None
        self._status_capacidade_label: ctk.CTkLabel | None = None
        self._mais_info_frame: ctk.CTkFrame | None = None
        self._mais_info_visible = False
        self._mais_info_toggle_var = ctk.StringVar(value="Mais informacoes [+]")

        self._insumos_resultados = PlantabilidadeResultados()

    def build(self, frame: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        top_row = ctk.CTkFrame(scroll, fg_color="transparent")
        top_row.grid(row=0, column=0, sticky="nsew", padx=20, pady=(0, 20))
        top_row.grid_columnconfigure((0, 1), weight=1, uniform="plantabilidade_top")

        insumos_card = create_card(
            top_row,
            row=0,
            column=0,
            sticky="nsew",
            padding={"padx": (0, 10), "pady": (0, 0)},
        )
        insumos_card.grid_columnconfigure(0, weight=1)
        section_title(insumos_card, "REGULAGEM DE INSUMOS")
        self._build_insumos_inputs(insumos_card)

        resultados_card = create_card(
            top_row,
            row=0,
            column=1,
            sticky="nsew",
            padding={"padx": (10, 0), "pady": (0, 0)},
        )
        resultados_card.grid_columnconfigure(0, weight=1)
        section_title(resultados_card, "RESULTADOS")
        self._build_insumos_resultados(resultados_card)

        bottom_row = ctk.CTkFrame(scroll, fg_color="transparent")
        bottom_row.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        bottom_row.grid_columnconfigure((0, 1), weight=1, uniform="plantabilidade_bottom")

        capacidade_card = create_card(
            bottom_row,
            row=0,
            column=0,
            sticky="nsew",
            padding={"padx": (0, 10), "pady": (0, 0)},
        )
        capacidade_card.grid_columnconfigure(0, weight=1)
        section_title(capacidade_card, "CAPACIDADE DE OPERACAO")
        self._build_capacidade_inputs(capacidade_card)

        capacidade_resultados_card = create_card(
            bottom_row,
            row=0,
            column=1,
            sticky="nsew",
            padding={"padx": (10, 0), "pady": (0, 0)},
        )
        capacidade_resultados_card.grid_columnconfigure(0, weight=1)
        section_title(capacidade_resultados_card, "RESULTADOS")
        self._build_capacidade_resultados(capacidade_resultados_card)

        self._refresh_capacidade_contexto()

    def _build_insumos_inputs(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 12))
        body.grid_columnconfigure(1, weight=1)

        for row, (label, var) in enumerate(
            (
                ("Populacao alvo (plantas/ha)", self._populacao_var),
                ("Fertilizante (kg/ha)", self._fertilizante_var),
                ("Espacamento entre linhas (cm)", self._espacamento_var),
            )
        ):
            ctk.CTkLabel(body, text=label, anchor="w", font=self._font_label_bold).grid(
                row=row, column=0, sticky="w", pady=6
            )
            ctk.CTkEntry(body, textvariable=var, width=140).grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=6)

        row += 1
        ctk.CTkLabel(
            body,
            text="Caracteristicas da semente",
            anchor="w",
            text_color="#d4dcff",
            font=self._font_label_bold,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(18, 8))

        for offset, (label, var) in enumerate(
            (
                ("Potencial germinativo (%)", self._germinacao_var),
                ("Sementes puras (%)", self._sementes_puras_var),
                ("Qualidade de plantio (0-10)", self._qualidade_var),
            ),
            start=row + 1,
        ):
            ctk.CTkLabel(body, text=label, anchor="w", font=self._font_label).grid(
                row=offset, column=0, sticky="w", pady=6
            )
            ctk.CTkEntry(body, textvariable=var, width=140).grid(row=offset, column=1, sticky="ew", padx=(10, 0), pady=6)

        legenda = (
            "Qualidade de plantio: atribua nota de 0 a 10 considerando clima,\n"
            "condicoes do solo e performance da semeadora."
        )
        ctk.CTkLabel(
            body,
            text=legenda,
            anchor="w",
            justify="left",
            text_color="#9cabd8",
            wraplength=320,
            font=ctk.CTkFont(size=12),
        ).grid(row=offset + 1, column=0, columnspan=2, sticky="ew", pady=(6, 12))

        primary_button(
            parent,
            text="Calcular regulagem",
            command=self._executar_insumos,
            row=2,
            pady=(0, 18),
        )

    def _build_insumos_resultados(self, parent: ctk.CTkFrame) -> None:
        self._status_insumos_label = ctk.CTkLabel(
            parent,
            textvariable=self._status_insumos_var,
            anchor="w",
            wraplength=320,
            text_color="#9ca8cc",
            font=self._font_status,
        )
        self._status_insumos_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 12))

        results_frame = ctk.CTkFrame(parent, fg_color="transparent")
        results_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 14))
        results_frame.grid_columnconfigure(1, weight=1)

        self._add_result_row(results_frame, 0, "Sementes (m linear)", self._sementes_m_var)
        self._add_result_row(results_frame, 1, "Fertilizante (g/m)", self._fertilizante_m_var)
        self._add_result_row(results_frame, 2, "Espacamento entre sementes (cm)", self._espacamento_cm_var)

        toggle_frame = ctk.CTkFrame(parent, fg_color="transparent")
        toggle_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))
        toggle_frame.grid_columnconfigure(0, weight=1)
        toggle_frame.configure(cursor="hand2")

        toggle_label = ctk.CTkLabel(
            toggle_frame,
            textvariable=self._mais_info_toggle_var,
            anchor="w",
            text_color="#eef1fb",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        toggle_label.grid(row=0, column=0, sticky="ew", padx=12, pady=6)
        toggle_frame.bind("<Button-1>", self._toggle_mais_info)
        toggle_label.bind("<Button-1>", self._toggle_mais_info)

        self._mais_info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._mais_info_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        self._mais_info_frame.grid_columnconfigure(1, weight=1)

        self._add_result_row(self._mais_info_frame, 0, "Sementes totais (ha)", self._mais_info_vars["sementes_totais"])
        self._add_result_row(
            self._mais_info_frame,
            1,
            "Equivalente em sacas (60 mil sementes)",
            self._mais_info_vars["sementes_sacas"],
        )
        self._add_result_row(self._mais_info_frame, 2, "Sementes por m\u00b2", self._mais_info_vars["sementes_m2"])
        self._add_result_row(self._mais_info_frame, 3, "Plantas esperadas por m\u00b2", self._mais_info_vars["plantas_m2"])
        self._add_result_row(self._mais_info_frame, 4, "Fertilizante (g/m\u00b2)", self._mais_info_vars["fertilizante_m2"])

        self._set_mais_info_visible(False)

    def _build_capacidade_inputs(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 12))
        body.grid_columnconfigure(1, weight=1)

        # Rendimento operacional movido para a aba Dimensionamento; continua sendo usado daqui via var compartilhada.

        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        info_frame.grid_columnconfigure(1, weight=1)

        self._add_result_row(info_frame, 0, "Largura util (m)", self._largura_util_var)
        self._add_result_row(info_frame, 1, "Velocidade (km/h)", self._velocidade_var)
        self._add_result_row(info_frame, 2, "Area total (ha)", self._area_total_var)
        self._add_result_row(info_frame, 3, "CV do trator", self._potencia_var)

        primary_button(
            parent,
            text="Calcular capacidade",
            command=self._executar_capacidade,
            row=3,
            pady=(0, 18),
        )

    def _build_capacidade_resultados(self, parent: ctk.CTkFrame) -> None:
        self._status_capacidade_label = ctk.CTkLabel(
            parent,
            textvariable=self._status_capacidade_var,
            anchor="w",
            wraplength=320,
            text_color="#9ca8cc",
            font=self._font_status,
        )
        self._status_capacidade_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 12))

        results_frame = ctk.CTkFrame(parent, fg_color="transparent")
        results_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        results_frame.grid_columnconfigure(1, weight=1)

        self._add_result_row(results_frame, 0, "CCE (ha/h)", self._cce_var)
        self._add_result_row(results_frame, 1, "Tempo de operacao (h)", self._tempo_operacao_var)
        self._add_result_row(results_frame, 2, "Consumo diesel (L/h)", self._consumo_h_var)
        self._add_result_row(results_frame, 3, "Consumo diesel total (L)", self._consumo_total_var)

    def _add_result_row(self, parent: ctk.CTkFrame, row: int, label: str, var: ctk.StringVar) -> None:
        ctk.CTkLabel(
            parent,
            text=label,
            anchor="w",
            text_color="#a9b7d9",
            font=self._font_label,
        ).grid(row=row, column=0, sticky="w", pady=4, padx=(12, 8))
        ctk.CTkLabel(
            parent,
            textvariable=var,
            anchor="w",
            text_color="#f2f4ff",
            font=self._font_value,
        ).grid(row=row, column=1, sticky="w", pady=4, padx=(0, 12))

    def _set_status_color(self, label: ctk.CTkLabel | None, color: str) -> None:
        if label is not None:
            label.configure(text_color=color)

    def _toggle_mais_info(self, _event=None) -> None:
        self._set_mais_info_visible(not self._mais_info_visible)

    def _set_mais_info_visible(self, visible: bool) -> None:
        self._mais_info_visible = visible
        symbol = "[-]" if visible else "[+]"
        self._mais_info_toggle_var.set(f"Mais informacoes {symbol}")
        if self._mais_info_frame is None:
            return
        if visible:
            self._mais_info_frame.grid()
        else:
            self._mais_info_frame.grid_remove()

    def _refresh_capacidade_contexto(self) -> None:
        linhas_text = self.app.input_vars["linhas"].get()
        velocidade_text = self.app.input_vars["velocidade_kmh"].get()
        area_text = self.app.field_vars["area_hectares"].get()
        potencia_text = self.app.input_vars["cv_trator_disponivel"].get()

        self._velocidade_var.set(velocidade_text or "--")
        self._area_total_var.set(area_text or "--")
        self._potencia_var.set(potencia_text or "--")

        try:
            linhas = int(linhas_text)
            espacamento_m = self._parse_espacamento_m()
            largura = linhas * espacamento_m
            self._largura_util_var.set(self._format(largura, 2))
        except (ValueError, TypeError):
            self._largura_util_var.set("--")

    def _format(self, value: float, decimals: int) -> str:
        if math.isnan(value) or math.isinf(value):
            return "--"
        return f"{value:,.{decimals}f}".replace(",", ".")

    def _parse_espacamento_m(self) -> float:
        texto = self._espacamento_var.get().replace(",", ".")
        valor_cm = float(texto)
        if valor_cm <= 0:
            raise ValueError("espacamento invalido")
        return valor_cm / 100.0

    def _executar_insumos(self) -> None:
        try:
            populacao = float(self._populacao_var.get().replace(",", "."))
            fertilizante = float(self._fertilizante_var.get().replace(",", "."))
            germinacao_pct = float(self._germinacao_var.get().replace(",", "."))
            sementes_puras_pct = float(self._sementes_puras_var.get().replace(",", "."))
            qualidade = float(self._qualidade_var.get().replace(",", "."))
            espacamento_m = self._parse_espacamento_m()
        except ValueError:
            self._status_insumos_var.set("Revise os valores informados.")
            self._set_status_color(self._status_insumos_label, "#b00020")
            return

        if qualidade < 0 or qualidade > 10:
            self._status_insumos_var.set("Qualidade de plantio deve estar entre 0 e 10.")
            self._set_status_color(self._status_insumos_label, "#b00020")
            return

        germinacao = germinacao_pct / 100.0
        sementes_puras = sementes_puras_pct / 100.0
        if germinacao <= 0 or sementes_puras <= 0:
            self._status_insumos_var.set("Percentuais de germinacao e sementes puras devem ser positivos.")
            self._set_status_color(self._status_insumos_label, "#b00020")
            return

        try:
            sementes_ha = sementes_por_ha(populacao, germinacao, sementes_puras, qualidade)
            sementes_m, fertilizante_g_m, espacamento_cm = insumos_por_m_linear(
                sementes_ha, fertilizante, espacamento_m
            )
        except Exception as exc:
            self._status_insumos_var.set(f"Falha ao calcular: {exc}")
            self._set_status_color(self._status_insumos_label, "#b00020")
            return

        self._insumos_resultados = PlantabilidadeResultados(
            sementes_por_ha=sementes_ha,
            sementes_por_m=sementes_m,
            fertilizante_g_por_m=fertilizante_g_m,
            espacamento_cm=espacamento_cm,
        )

        self._sementes_m_var.set(self._format(sementes_m, 2))
        self._fertilizante_m_var.set(self._format(fertilizante_g_m, 2))
        self._espacamento_cm_var.set(self._format(espacamento_cm, 2))

        sementes_totais_ha = sementes_ha
        sacas_equivalentes = sementes_ha / 60000.0
        sementes_m2 = sementes_m / espacamento_m if espacamento_m else float("inf")
        plantas_m2 = populacao / 10000.0
        fertilizante_g_m2 = fertilizante * 0.1

        self._mais_info_vars["sementes_totais"].set(self._format(sementes_totais_ha, 0))
        self._mais_info_vars["sementes_sacas"].set(self._format(sacas_equivalentes, 2))
        self._mais_info_vars["sementes_m2"].set(self._format(sementes_m2, 3))
        self._mais_info_vars["plantas_m2"].set(self._format(plantas_m2, 3))
        self._mais_info_vars["fertilizante_m2"].set(self._format(fertilizante_g_m2, 2))

        self._status_insumos_var.set("Regulagem calculada com sucesso.")
        self._set_status_color(self._status_insumos_label, "#3f7e2d")
        self._refresh_capacidade_contexto()

    def _executar_capacidade(self) -> None:
        try:
            rendimento_pct = float(self._rendimento_operacional_var.get().replace(",", "."))
        except ValueError:
            self._status_capacidade_var.set("Informe um rendimento operacional valido.")
            self._set_status_color(self._status_capacidade_label, "#b00020")
            return

        rendimento = rendimento_pct / 100.0
        if rendimento <= 0 or rendimento > 1:
            self._status_capacidade_var.set("Rendimento operacional deve ficar entre 0 e 100%.")
            self._set_status_color(self._status_capacidade_label, "#b00020")
            return

        try:
            linhas = int(self.app.input_vars["linhas"].get())
            velocidade = float(self.app.input_vars["velocidade_kmh"].get().replace(",", "."))
            potencia = float(self.app.input_vars["cv_trator_disponivel"].get().replace(",", "."))
        except (ValueError, KeyError):
            self._status_capacidade_var.set("Verifique linhas, velocidade e CV do trator.")
            self._set_status_color(self._status_capacidade_label, "#b00020")
            return

        area_text = self.app.field_vars["area_hectares"].get()
        try:
            area_ha = float(area_text.replace(",", ".")) if area_text else 0.0
        except ValueError:
            area_ha = 0.0

        try:
            espacamento_m = self._parse_espacamento_m()
        except ValueError:
            self._status_capacidade_var.set("Informe um espacamento valido para calcular a largura util.")
            self._set_status_color(self._status_capacidade_label, "#b00020")
            return

        try:
            largura, cce, tempo = capacidade_campo(linhas, espacamento_m, velocidade, rendimento, area_ha)
            consumo_total = consumo_diesel_total(potencia, tempo)
        except Exception as exc:
            self._status_capacidade_var.set(f"Falha ao calcular capacidade: {exc}")
            self._set_status_color(self._status_capacidade_label, "#b00020")
            return

        consumo_h = consumo_total / tempo if tempo and math.isfinite(tempo) else consumo_total

        self._largura_util_var.set(self._format(largura, 2))
        self._velocidade_var.set(self._format(velocidade, 2))
        self._area_total_var.set(self._format(area_ha, 2))
        self._potencia_var.set(self._format(potencia, 2))
        self._cce_var.set(self._format(cce, 1))
        self._tempo_operacao_var.set(self._format(tempo, 1))
        self._consumo_total_var.set(self._format(consumo_total, 1))
        self._consumo_h_var.set(self._format(consumo_h, 1))

        self._status_capacidade_var.set("Capacidade de operacao calculada com sucesso.")
        self._set_status_color(self._status_capacidade_label, "#3f7e2d")

    def on_show(self) -> None:
        self._refresh_capacidade_contexto()
