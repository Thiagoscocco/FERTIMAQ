# -*- coding: utf-8 -*-
"""Tab responsible for machine hour costs calculations."""

from __future__ import annotations

import math
from typing import Optional

import customtkinter as ctk

from ferticalc_ui_blueprint import create_card, primary_button, section_title
from fertimaq.custos_hora_maq_calcs import (
    FixosInputs,
    VariaveisInputs,
    calc_fixos,
    calc_variaveis,
    calcular_tudo_custos,
    estimar_parametros,
    EstimativasInputs,
)

from .base import FertiMaqTab, tab_registry


@tab_registry.register
class CustosHoraMaqTab(FertiMaqTab):
    tab_id = "custos_hora_maq"
    title = "CUSTOS HORA/MÁQUINA"

    def __init__(self, app: "FertiMaqApp") -> None:
        super().__init__(app)

        self._font_label = ctk.CTkFont(size=14)
        self._font_label_bold = ctk.CTkFont(size=15, weight="bold")
        self._font_value = ctk.CTkFont(size=16, weight="bold")
        self._font_status = ctk.CTkFont(size=13, slant="italic")

        # Fixos - TRATOR
        self._trator_area_ano_var = ctk.StringVar(value="")
        self._trator_valor_aq_var = ctk.StringVar(value="")
        self._trator_valor_suc_var = ctk.StringVar(value="")
        self._trator_anos_var = ctk.StringVar(value="10")
        self._trator_horas_ano_var = ctk.StringVar(value="")
        self._trator_juros_var = ctk.StringVar(value="6")
        self._trator_seguro_var = ctk.StringVar(value="2")
        self._trator_abrigo_var = ctk.StringVar(value="1")
        self._salario_min_var = ctk.StringVar(value="3000")

        # Fixos - SEMEADORA
        self._semeadora_area_ano_var = ctk.StringVar(value="")
        self._semeadora_valor_aq_var = ctk.StringVar(value="")
        self._semeadora_valor_suc_var = ctk.StringVar(value="")
        self._semeadora_anos_var = ctk.StringVar(value="10")
        self._semeadora_horas_ano_var = ctk.StringVar(value="")
        self._semeadora_juros_var = ctk.StringVar(value="6")
        self._semeadora_seguro_var = ctk.StringVar(value="2")
        self._semeadora_abrigo_var = ctk.StringVar(value="1")

        # Variáveis - TRATOR
        self._trator_consumo_h_var = ctk.StringVar(value="")
        self._trator_preco_litro_var = ctk.StringVar(value="6.0")
        self._trator_reparo_total_var = ctk.StringVar(value="")
        self._trator_lfa_total_var = ctk.StringVar(value="")
        self._trator_pneus_total_var = ctk.StringVar(value="")

        # Variáveis - SEMEADORA
        self._semeadora_consumo_h_var = ctk.StringVar(value="0")
        self._semeadora_preco_litro_var = ctk.StringVar(value="6.0")
        self._semeadora_reparo_total_var = ctk.StringVar(value="")
        self._semeadora_lfa_total_var = ctk.StringVar(value="")
        self._semeadora_pneus_total_var = ctk.StringVar(value="")

        # Status e resultados
        self._status_fixos_var = ctk.StringVar(value="Informe os dados e calcule.")
        self._status_variaveis_var = ctk.StringVar(value="Informe os dados e calcule.")
        self._status_resultados_var = ctk.StringVar(value="Preencha os custos fixos e variáveis para calcular.")

        self._trator_hora_maq_var = ctk.StringVar(value="--")
        self._semeadora_hora_maq_var = ctk.StringVar(value="--")
        self._conjunto_hora_maq_var = ctk.StringVar(value="--")

        self._fixos_visible = True
        self._variaveis_visible = True

        # Frames de conteúdo colapsáveis
        self._fixos_content_frame: Optional[ctk.CTkFrame] = None
        self._variaveis_content_frame: Optional[ctk.CTkFrame] = None
        self._fixos_toggle_label: Optional[ctk.CTkLabel] = None
        self._variaveis_toggle_label: Optional[ctk.CTkLabel] = None

        # Track estimation states
        self._estimation_flags = {
            "trator_area": False, "trator_valor_aq": False, "trator_valor_suc": False,
            "trator_horas": False, "trator_juros": False, "trator_seguro": False, "trator_abrigo": False,
            "semeadora_area": False, "semeadora_valor_aq": False, "semeadora_valor_suc": False,
            "semeadora_horas": False, "semeadora_juros": False, "semeadora_seguro": False, "semeadora_abrigo": False,
            "salario": False, "trator_consumo": False, "trator_preco": False, "trator_reparo": False,
            "trator_lfa": False, "trator_pneus": False, "semeadora_reparo": False,
            "semeadora_lfa": False, "semeadora_pneus": False,
        }

    def _bind_money_format(self, entry: ctk.CTkEntry, var: ctk.StringVar) -> None:
        """Formata valor monetário ao sair do campo, sem apagar o valor em caso de falha.

        A rotina tenta converter textos com separadores (pontos de milhar/virgulas) para float.
        Se a conversão falhar, preserva o texto original.
        """
        def _on_blur(_event=None) -> None:
            text = (var.get() or "").strip()
            if not text:
                return
            # Normaliza: remove pontos de milhar e troca vírgula por ponto
            norm = text.replace(" ", "").replace(".", "").replace(",", ".")
            try:
                value = float(norm)
            except ValueError:
                return  # mantém o texto como está
            var.set(self._format(value, 2))

        entry.bind("<FocusOut>", _on_blur)

    def build(self, frame: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        # CUSTOS FIXOS
        self._build_fixos_section(scroll)

        # CUSTOS VARIÁVEIS
        self._build_variaveis_section(scroll)

        # RESULTADOS
        self._build_resultados_section(scroll)

    def _build_fixos_section(self, parent: ctk.CTkFrame) -> None:
        """Constrói a seção de custos fixos."""
        card = create_card(
            parent,
            row=0,
            column=0,
            sticky="nsew",
            padding={"padx": 20, "pady": (20, 10)},
        )
        card.grid_columnconfigure(0, weight=1)

        # Título com toggle
        title_frame = ctk.CTkFrame(card, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 0))
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="CUSTOS FIXOS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#5a7bbf",
        )
        title_label.grid(row=0, column=0, sticky="w")

        self._fixos_toggle_label = ctk.CTkLabel(
            title_frame,
            text="ocultar ▲",
            font=ctk.CTkFont(size=12),
            text_color="#ff4444",
            cursor="hand2",
        )
        self._fixos_toggle_label.grid(row=0, column=1, sticky="e")
        self._fixos_toggle_label.bind("<Button-1>", lambda e: self._toggle_fixos())

        # Conteúdo fixos
        self._fixos_content_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._fixos_content_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 18))
        self._fixos_content_frame.grid_columnconfigure((0, 1), weight=1, uniform="fixos_cols")

        self._build_fixos_trator(self._fixos_content_frame)
        self._build_fixos_semeadora(self._fixos_content_frame)

    def _build_fixos_trator(self, parent: ctk.CTkFrame) -> None:
        """Constrói os inputs de custos fixos do trator."""
        trator_frame = ctk.CTkFrame(parent, fg_color="#3a3a3a")
        trator_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        trator_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            trator_frame,
            text="TRATOR",
            font=self._font_label_bold,
            text_color="#5a7bbf",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(12, 8))

        row = 1
        self._add_input_row(trator_frame, row, "Área trabalhada ao ano (ha)", self._trator_area_ano_var, "trator_area")
        row += 1
        self._add_input_row(trator_frame, row, "Valor aquisição (R$)", self._trator_valor_aq_var, "trator_valor_aq")
        row += 1
        self._add_input_row(trator_frame, row, "Valor sucata (R$)", self._trator_valor_suc_var, "trator_valor_suc")
        row += 1
        self._add_input_row(trator_frame, row, "Anos de uso", self._trator_anos_var)
        row += 1
        self._add_input_row(trator_frame, row, "Horas/ano", self._trator_horas_ano_var, "trator_horas")
        row += 1
        self._add_input_row(trator_frame, row, "Taxa juros", self._trator_juros_var, "trator_juros")
        row += 1
        self._add_input_row(trator_frame, row, "Taxa seguro", self._trator_seguro_var, "trator_seguro")
        row += 1
        self._add_input_row(trator_frame, row, "Taxa abrigo", self._trator_abrigo_var, "trator_abrigo")
        row += 1
        self._add_input_row(trator_frame, row, "Salário mínimo (R$)", self._salario_min_var, "salario")

    def _build_fixos_semeadora(self, parent: ctk.CTkFrame) -> None:
        """Constrói os inputs de custos fixos da semeadora."""
        semeadora_frame = ctk.CTkFrame(parent, fg_color="#3a3a3a")
        semeadora_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        semeadora_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            semeadora_frame,
            text="SEMEADORA",
            font=self._font_label_bold,
            text_color="#5a7bbf",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(12, 8))

        row = 1
        self._add_input_row(semeadora_frame, row, "Área trabalhada ao ano (ha)", self._semeadora_area_ano_var, "semeadora_area")
        row += 1
        self._add_input_row(semeadora_frame, row, "Valor aquisição (R$)", self._semeadora_valor_aq_var, "semeadora_valor_aq")
        row += 1
        self._add_input_row(semeadora_frame, row, "Valor sucata (R$)", self._semeadora_valor_suc_var, "semeadora_valor_suc")
        row += 1
        self._add_input_row(semeadora_frame, row, "Anos de uso", self._semeadora_anos_var)
        row += 1
        self._add_input_row(semeadora_frame, row, "Horas/ano", self._semeadora_horas_ano_var, "semeadora_horas")
        row += 1
        self._add_input_row(semeadora_frame, row, "Taxa juros", self._semeadora_juros_var, "semeadora_juros")
        row += 1
        self._add_input_row(semeadora_frame, row, "Taxa seguro", self._semeadora_seguro_var, "semeadora_seguro")
        row += 1
        self._add_input_row(semeadora_frame, row, "Taxa abrigo", self._semeadora_abrigo_var, "semeadora_abrigo")

    def _build_variaveis_section(self, parent: ctk.CTkFrame) -> None:
        """Constrói a seção de custos variáveis."""
        card = create_card(
            parent,
            row=1,
            column=0,
            sticky="nsew",
            padding={"padx": 20, "pady": (10, 10)},
        )
        card.grid_columnconfigure(0, weight=1)

        # Título com toggle
        title_frame = ctk.CTkFrame(card, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 0))
        title_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text="CUSTOS VARIÁVEIS",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#5a7bbf",
        )
        title_label.grid(row=0, column=0, sticky="w")

        self._variaveis_toggle_label = ctk.CTkLabel(
            title_frame,
            text="ocultar ▲",
            font=ctk.CTkFont(size=12),
            text_color="#ff4444",
            cursor="hand2",
        )
        self._variaveis_toggle_label.grid(row=0, column=1, sticky="e")
        self._variaveis_toggle_label.bind("<Button-1>", lambda e: self._toggle_variaveis())

        # Conteúdo variáveis
        self._variaveis_content_frame = ctk.CTkFrame(card, fg_color="transparent")
        self._variaveis_content_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 18))
        self._variaveis_content_frame.grid_columnconfigure((0, 1), weight=1, uniform="variaveis_cols")

        self._build_variaveis_trator(self._variaveis_content_frame)
        self._build_variaveis_semeadora(self._variaveis_content_frame)

    def _build_variaveis_trator(self, parent: ctk.CTkFrame) -> None:
        """Constrói os inputs de custos variáveis do trator."""
        trator_frame = ctk.CTkFrame(parent, fg_color="#3a3a3a")
        trator_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        trator_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            trator_frame,
            text="TRATOR",
            font=self._font_label_bold,
            text_color="#5a7bbf",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(12, 8))

        row = 1
        self._add_input_row(trator_frame, row, "Consumo (L/h)", self._trator_consumo_h_var, "trator_consumo")
        row += 1
        self._add_input_row(trator_frame, row, "Preço litro (R$/L)", self._trator_preco_litro_var, "trator_preco")
        row += 1
        self._add_input_row(trator_frame, row, "Custo reparo total (R$)", self._trator_reparo_total_var, "trator_reparo")
        row += 1
        self._add_input_row(trator_frame, row, "Lub./Adt./Filt. total (R$)", self._trator_lfa_total_var, "trator_lfa")
        row += 1
        self._add_input_row(trator_frame, row, "Pneus e câmaras total (R$)", self._trator_pneus_total_var, "trator_pneus")

    def _build_variaveis_semeadora(self, parent: ctk.CTkFrame) -> None:
        """Constrói os inputs de custos variáveis da semeadora."""
        semeadora_frame = ctk.CTkFrame(parent, fg_color="#3a3a3a")
        semeadora_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        semeadora_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            semeadora_frame,
            text="SEMEADORA",
            font=self._font_label_bold,
            text_color="#5a7bbf",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=15, pady=(12, 8))

        row = 1
        self._add_input_row(semeadora_frame, row, "Custo reparo total (R$)", self._semeadora_reparo_total_var, "semeadora_reparo")
        row += 1
        self._add_input_row(semeadora_frame, row, "Lub./Aditivos total (R$)", self._semeadora_lfa_total_var, "semeadora_lfa")
        row += 1
        self._add_input_row(semeadora_frame, row, "Pneus e câmaras total (R$)", self._semeadora_pneus_total_var, "semeadora_pneus")

    def _build_resultados_section(self, parent: ctk.CTkFrame) -> None:
        """Constrói a seção de resultados."""
        card = create_card(
            parent,
            row=2,
            column=0,
            sticky="nsew",
            padding={"padx": 20, "pady": (10, 20)},
        )
        card.grid_columnconfigure(0, weight=1)

        section_title(card, "RESULTADOS")
        
        status_label = ctk.CTkLabel(
            card,
            textvariable=self._status_resultados_var,
            anchor="w",
            wraplength=600,
            text_color="#9ca8cc",
            font=self._font_status,
        )
        status_label.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 12))

        results_frame = ctk.CTkFrame(card, fg_color="transparent")
        results_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
        results_frame.grid_columnconfigure(1, weight=1)

        self._add_result_row(results_frame, 0, "Hora/Máquina - TRATOR (R$/h)", self._trator_hora_maq_var)
        self._add_result_row(results_frame, 1, "Hora/Máquina - SEMEADORA (R$/h)", self._semeadora_hora_maq_var)
        self._add_result_row(results_frame, 2, "Hora/Máquina - CONJUNTO (R$/h)", self._conjunto_hora_maq_var)

        primary_button(
            card,
            text="Calcular custos hora/máquina",
            command=self._executar_calculo,
            row=3,
            pady=(0, 18),
        )

    def _add_input_row(self, parent: ctk.CTkFrame, row: int, label: str, var: ctk.StringVar, estimate_key: Optional[str] = None) -> None:
        """Adiciona uma linha de input com label, entry e botão estimar (se necessário)."""
        ctk.CTkLabel(
            parent,
            text=label,
            anchor="w",
            font=self._font_label,
            text_color="#a9b7d9",
        ).grid(row=row, column=0, sticky="w", padx=15, pady=6)

        entry = ctk.CTkEntry(parent, textvariable=var, width=140)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=6)

        # Formatação automática para campos monetários (rótulos com R$ ou Preço)
        label_lower = label.lower()
        if "r$" in label_lower or "preço" in label_lower:
            self._bind_money_format(entry, var)

        if estimate_key:
            btn = ctk.CTkButton(
                parent,
                text="estimar",
                font=ctk.CTkFont(size=11),
                fg_color="#2196F3",
                hover_color="#1976D2",
                width=60,
                height=24,
                command=lambda: self._estimiar_campo(estimate_key, var),
            )
            btn.grid(row=row, column=2, padx=(5, 15), pady=6)

    def _add_result_row(self, parent: ctk.CTkFrame, row: int, label: str, var: ctk.StringVar) -> None:
        """Adiciona uma linha de resultado."""
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

    def _toggle_fixos(self) -> None:
        """Alterna visibilidade da seção de custos fixos."""
        self._fixos_visible = not self._fixos_visible
        if self._fixos_content_frame:
            if self._fixos_visible:
                self._fixos_content_frame.grid()
                if self._fixos_toggle_label:
                    self._fixos_toggle_label.configure(text="ocultar ▲")
            else:
                self._fixos_content_frame.grid_remove()
                if self._fixos_toggle_label:
                    self._fixos_toggle_label.configure(text="mostrar ▼")

    def _toggle_variaveis(self) -> None:
        """Alterna visibilidade da seção de custos variáveis."""
        self._variaveis_visible = not self._variaveis_visible
        if self._variaveis_content_frame:
            if self._variaveis_visible:
                self._variaveis_content_frame.grid()
                if self._variaveis_toggle_label:
                    self._variaveis_toggle_label.configure(text="ocultar ▲")
            else:
                self._variaveis_content_frame.grid_remove()
                if self._variaveis_toggle_label:
                    self._variaveis_toggle_label.configure(text="mostrar ▼")

    def _parse_float(self, var: ctk.StringVar, default: float = 0.0) -> float:
        """Parse float from string var."""
        raw = (var.get() or "").strip().replace(" ", "")
        if not raw:
            return default
        # Normaliza vírgula para ponto (decimal)
        text = raw.replace(",", ".")
        # Se houver mais de um ponto, os anteriores são separadores de milhar: remove-os
        if text.count(".") > 1:
            head, tail = text.rsplit(".", 1)
            head = head.replace(".", "")
            text = head + "." + tail
        try:
            return float(text)
        except Exception:
            return default

    def _format(self, value: float, decimals: int = 2) -> str:
        """Format float value."""
        if math.isnan(value) or math.isinf(value):
            return "--"
        return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _get_area_ha(self) -> float:
        """Obtém área do talhão se disponível."""
        try:
            area_text = self.app.field_vars["area_hectares"].get()
            return float(area_text.replace(",", ".")) if area_text else 0.0
        except (ValueError, KeyError):
            return 0.0

    def _get_trator_cv(self) -> float:
        """Obtém CV do trator se disponível."""
        try:
            cv_text = self.app.input_vars["cv_trator_disponivel"].get()
            return float(cv_text.replace(",", ".")) if cv_text else 0.0
        except (ValueError, KeyError):
            return 0.0

    def _get_semeadora_linhas(self) -> float:
        """Obtém número de linhas se disponível."""
        try:
            linhas_text = self.app.input_vars["linhas"].get()
            return float(linhas_text) if linhas_text else 0.0
        except (ValueError, KeyError):
            return 0.0

    def _get_cce(self) -> float:
        """Obtém CCE se disponível da aba plantabilidade."""
        # Prioriza CCE salvo no estado global
        try:
            cce_text = self.app.input_vars.get("cce_ha_h")
            if cce_text is not None:
                raw = cce_text.get()
                if raw:
                    return float(raw.replace(".", "").replace(",", "."))
        except Exception:
            pass
        # Try to get from plantabilidade tab if calculated
        try:
            plantabilidade_tab = self.app._tabs.get("plantabilidade")
            if plantabilidade_tab and hasattr(plantabilidade_tab, "_cce_var"):
                cce_text = plantabilidade_tab._cce_var.get()
                if cce_text and cce_text != "--":
                    return float(cce_text.replace(",", "."))
        except (ValueError, AttributeError, KeyError):
            pass
        return 0.0

    def _get_consumo_h(self) -> float:
        """Obtém consumo/h se disponível da aba plantabilidade."""
        try:
            plantabilidade_tab = self.app._tabs.get("plantabilidade")
            if plantabilidade_tab and hasattr(plantabilidade_tab, "_consumo_h_var"):
                consumo_text = plantabilidade_tab._consumo_h_var.get()
                if consumo_text and consumo_text != "--":
                    return float(consumo_text.replace(",", "."))
        except (ValueError, AttributeError, KeyError):
            pass
        return 8.0  # default

    def _estimiar_campo(self, key: str, var: ctk.StringVar) -> None:
        """Estima valor para um campo específico."""
        self._estimation_flags[key] = True
        area_ha = self._get_area_ha()
        trator_cv = self._get_trator_cv()
        semeadora_linhas = self._get_semeadora_linhas()
        cce = self._get_cce()

        if key == "trator_area" or key == "semeadora_area":
            var.set(self._format(area_ha, 2) if area_ha else "")
        elif key == "trator_valor_aq":
            valor = trator_cv * 3000.0 if trator_cv else 0.0
            var.set(self._format(valor, 2))
        elif key == "semeadora_valor_aq":
            valor = semeadora_linhas * 20000.0 if semeadora_linhas else 0.0
            var.set(self._format(valor, 2))
        elif key == "trator_valor_suc":
            # Se o usuário digitou valor de aquisição, priorizar esse; senão, usar estimado
            valor_digitado = self._parse_float(self._trator_valor_aq_var)
            base = valor_digitado if valor_digitado else (trator_cv * 3000.0 if trator_cv else 0.0)
            var.set(self._format(base * 0.30, 2))
        elif key == "semeadora_valor_suc":
            valor_digitado = self._parse_float(self._semeadora_valor_aq_var)
            base = valor_digitado if valor_digitado else (semeadora_linhas * 20000.0 if semeadora_linhas else 0.0)
            var.set(self._format(base * 0.40, 2))
        elif key == "trator_horas":
            var.set(self._format(area_ha * 10.0, 1) if area_ha else "")
        elif key == "semeadora_horas":
            # horas/ano estimadas = area_trabalhada_ano / CCE (se CCE > 0)
            try:
                area_sem_text = self._semeadora_area_ano_var.get()
                area_sem = float(area_sem_text.replace(".", "").replace(",", ".")) if area_sem_text else area_ha
            except Exception:
                area_sem = area_ha
            horas = (area_sem / cce) if (cce and area_sem) else (area_sem * 10.0 if area_sem else 0.0)
            var.set(self._format(horas, 1) if horas else "")
        elif key == "trator_juros":
            var.set("6")
        elif key == "semeadora_juros":
            var.set("6")
        elif key == "trator_seguro":
            var.set("2")
        elif key == "semeadora_seguro":
            var.set("2")
        elif key == "trator_abrigo":
            var.set("1")
        elif key == "semeadora_abrigo":
            var.set("1")
        elif key == "salario":
            var.set("3000")
        elif key == "trator_consumo":
            # Estima consumo pelo CV (0.11 L/h por cv)
            consumo = 0.11 * self._get_trator_cv()
            var.set(self._format(consumo, 1))
        elif key == "trator_preco":
            var.set("6.0")
        elif key == "trator_reparo":
            valor_aq = self._parse_float(self._trator_valor_aq_var)
            if not valor_aq:
                valor_aq = trator_cv * 3000.0 if trator_cv else 0.0
            # Custo reparo total = 40% do valor de aquisição
            var.set(self._format(valor_aq * 0.40, 2))
        elif key == "semeadora_reparo":
            valor_aq = self._parse_float(self._semeadora_valor_aq_var)
            if not valor_aq:
                valor_aq = semeadora_linhas * 20000.0 if semeadora_linhas else 0.0
            # Custo reparo total = 40% do valor de aquisição
            var.set(self._format(valor_aq * 0.40, 2))
        elif key == "trator_lfa":
            # 10% do custo total de combustível DO TRATOR ao longo da vida útil
            consumo_h = self._parse_float(self._trator_consumo_h_var, 0.0) or self._get_consumo_h()
            preco_litro = self._parse_float(self._trator_preco_litro_var, 6.0)
            trator_horas_ano = self._parse_float(self._trator_horas_ano_var)
            if not trator_horas_ano:
                trator_horas_ano = area_ha * 10.0 if area_ha else 0.0
            trator_anos = self._parse_float(self._trator_anos_var, 10.0)
            vida_horas = trator_horas_ano * trator_anos
            if vida_horas:
                custo_diesel_total = consumo_h * vida_horas * preco_litro
                estimativa_total = 0.10 * custo_diesel_total
                var.set(self._format(estimativa_total, 2))
            else:
                var.set("")
        elif key == "semeadora_lfa":
            # Mesmo total do TRATOR: 10% do combustível total do trator ao longo da vida
            consumo_h_tr = self._parse_float(self._trator_consumo_h_var, 0.0) or self._get_consumo_h()
            preco_litro_tr = self._parse_float(self._trator_preco_litro_var, 6.0)
            tr_horas_ano = self._parse_float(self._trator_horas_ano_var) or (area_ha * 10.0 if area_ha else 0.0)
            tr_anos = self._parse_float(self._trator_anos_var, 10.0)
            vida_tr = tr_horas_ano * tr_anos
            if vida_tr:
                custo_diesel_total_tr = consumo_h_tr * vida_tr * preco_litro_tr
                estimativa_total = 0.10 * custo_diesel_total_tr
                var.set(self._format(estimativa_total, 2))
            else:
                var.set("")
        elif key == "trator_pneus":
            valor_aq = self._parse_float(self._trator_valor_aq_var)
            if not valor_aq:
                valor_aq = trator_cv * 3000.0 if trator_cv else 0.0
            var.set(self._format(valor_aq * 0.07, 2))
        elif key == "semeadora_pneus":
            valor_aq = self._parse_float(self._semeadora_valor_aq_var)
            if not valor_aq:
                valor_aq = semeadora_linhas * 20000.0 if semeadora_linhas else 0.0
            var.set(self._format(valor_aq * 0.01, 2))

    def _executar_calculo(self) -> None:
        """Executa o cálculo completo de custos hora/máquina."""
        try:
            # Coletar inputs fixos
            trator_valor_aq = self._parse_float(self._trator_valor_aq_var)
            trator_valor_suc = self._parse_float(self._trator_valor_suc_var)
            trator_anos = self._parse_float(self._trator_anos_var, 10.0)
            trator_horas_ano = self._parse_float(self._trator_horas_ano_var)
            trator_juros_pct = self._parse_float(self._trator_juros_var, 6.0)
            trator_seguro_pct = self._parse_float(self._trator_seguro_var, 2.0)
            trator_abrigo_pct = self._parse_float(self._trator_abrigo_var, 1.0)
            trator_juros = trator_juros_pct / 100.0
            trator_seguro = trator_seguro_pct / 100.0
            trator_abrigo = trator_abrigo_pct / 100.0
            
            semeadora_valor_aq = self._parse_float(self._semeadora_valor_aq_var)
            semeadora_valor_suc = self._parse_float(self._semeadora_valor_suc_var)
            semeadora_anos = self._parse_float(self._semeadora_anos_var, 10.0)
            semeadora_horas_ano = self._parse_float(self._semeadora_horas_ano_var)
            semeadora_juros_pct = self._parse_float(self._semeadora_juros_var, 6.0)
            semeadora_seguro_pct = self._parse_float(self._semeadora_seguro_var, 2.0)
            semeadora_abrigo_pct = self._parse_float(self._semeadora_abrigo_var, 1.0)
            semeadora_juros = semeadora_juros_pct / 100.0
            semeadora_seguro = semeadora_seguro_pct / 100.0
            semeadora_abrigo = semeadora_abrigo_pct / 100.0
            
            salario_min = self._parse_float(self._salario_min_var, 3000.0)
            mao_obra_h = (salario_min * 2.8) / 240.0

            # Coletar inputs variáveis
            trator_consumo_h = self._parse_float(self._trator_consumo_h_var)
            if not trator_consumo_h:
                trator_consumo_h = self._get_consumo_h()
            trator_preco_litro = self._parse_float(self._trator_preco_litro_var, 6.0)
            
            semeadora_consumo_h = 0.0
            semeadora_preco_litro = 0.0

            trator_reparo_total = self._parse_float(self._trator_reparo_total_var)
            trator_lfa_total = self._parse_float(self._trator_lfa_total_var)
            trator_pneus_total = self._parse_float(self._trator_pneus_total_var)

            semeadora_reparo_total = self._parse_float(self._semeadora_reparo_total_var)
            semeadora_lfa_total = self._parse_float(self._semeadora_lfa_total_var)
            semeadora_pneus_total = self._parse_float(self._semeadora_pneus_total_var)

            # Validar inputs críticos e relatar o que falta
            faltando: list[str] = []
            if not trator_valor_aq:
                faltando.append("Valor de aquisição do trator")
            if not trator_horas_ano:
                faltando.append("Horas/ano do trator")
            if not semeadora_valor_aq:
                faltando.append("Valor de aquisição da semeadora")
            if not semeadora_horas_ano:
                faltando.append("Horas/ano da semeadora")
            if faltando:
                self._status_resultados_var.set("Faltam dados: " + "; ".join(faltando) + ".")
                return

            # Criar inputs para cálculos
            fixos_inputs = FixosInputs(
                trator_valor_aquisicao=trator_valor_aq,
                trator_valor_sucata=trator_valor_suc,
                trator_anos_uso=trator_anos,
                trator_horas_ano=trator_horas_ano,
                trator_taxa_juros=trator_juros,
                trator_seguro_taxa=trator_seguro,
                trator_abrigo_taxa=trator_abrigo,
                semeadora_valor_aquisicao=semeadora_valor_aq,
                semeadora_valor_sucata=semeadora_valor_suc,
                semeadora_anos_uso=semeadora_anos,
                semeadora_horas_ano=semeadora_horas_ano,
                semeadora_taxa_juros=semeadora_juros,
                semeadora_seguro_taxa=semeadora_seguro,
                semeadora_abrigo_taxa=semeadora_abrigo,
                mao_obra_hora=mao_obra_h,
            )

            # Preparar inputs variáveis
            # Para reparos, usar os valores totais fornecidos ou calcular usando fórmulas padrão
            trator_valor_aq_rep = trator_valor_aq
            if not trator_reparo_total:
                trator_reparo_total = trator_valor_aq * 0.40  # Fator padrão trator
            
            sem_valor_aq_rep = semeadora_valor_aq
            if not semeadora_reparo_total:
                semeadora_reparo_total = semeadora_valor_aq * 0.40  # Fator padrão semeadora

            # Para LFA, dividir pelo tempo de vida útil
            trator_horas_ano_lfa = trator_horas_ano
            trator_anos_lfa = trator_anos
            # Usaremos o total informado e dividiremos pela vida útil após o cálculo
            trator_valor_filtros_ano = 0.0

            sem_horas_ano_lfa = semeadora_horas_ano
            sem_anos_lfa = semeadora_anos
            sem_valor_filtros_ano = 0.0

            # Para pneus, dividir pela vida útil também
            trator_horas_ano_pneu = trator_horas_ano
            trator_anos_pneu = trator_anos
            if not trator_pneus_total:
                trator_pneus_total = trator_valor_aq * 0.07  # Estimativa

            sem_horas_ano_pneu = semeadora_horas_ano
            sem_anos_pneu = semeadora_anos
            if not semeadora_pneus_total:
                semeadora_pneus_total = semeadora_valor_aq * 0.01  # Estimativa

            variaveis_inputs = VariaveisInputs(
                trator_consumo_h=trator_consumo_h,
                trator_preco_litro=trator_preco_litro,
                semeadora_consumo_h=semeadora_consumo_h,
                semeadora_preco_litro=semeadora_preco_litro,
                trator_valor_aquisicao_rep=trator_valor_aq_rep,
                trator_horas_ano_rep=trator_horas_ano,
                trator_anos_uso_rep=trator_anos,
                sem_valor_aquisicao_rep=sem_valor_aq_rep,
                sem_horas_ano_rep=semeadora_horas_ano,
                sem_anos_uso_rep=semeadora_anos,
                trator_valor_aquisicao_lfa=trator_valor_aq,
                trator_valor_filtros_ano=trator_valor_filtros_ano,
                trator_horas_ano_lfa=trator_horas_ano_lfa,
                trator_anos_uso_lfa=trator_anos_lfa,
                sem_valor_aquisicao_lfa=semeadora_valor_aq,
                sem_valor_filtros_ano=sem_valor_filtros_ano,
                sem_horas_ano_lfa=sem_horas_ano_lfa,
                sem_anos_uso_lfa=sem_anos_lfa,
                trator_valor_aquisicao_pneu=trator_valor_aq,
                trator_horas_ano_pneu=trator_horas_ano_pneu,
                trator_anos_uso_pneu=trator_anos_pneu,
                sem_valor_aquisicao_pneu=semeadora_valor_aq,
                sem_horas_ano_pneu=sem_horas_ano_pneu,
                sem_anos_uso_pneu=sem_anos_pneu,
            )

            # Ajustar valores para usar os totais fornecidos
            # Reparos: o cálculo usa fator de 0.65 para trator e 0.3 para semeadora
            # Se o usuário forneceu valor total, precisamos ajustar
            vida_trator_rep = trator_horas_ano * trator_anos
            vida_sem_rep = semeadora_horas_ano * semeadora_anos
            vida_trator_lfa = trator_horas_ano_lfa * trator_anos_lfa
            vida_sem_lfa = sem_horas_ano_lfa * sem_anos_lfa
            vida_trator_pneu = trator_horas_ano_pneu * trator_anos_pneu
            vida_sem_pneu = sem_horas_ano_pneu * sem_anos_pneu

            # Calcular fixos via motor
            fx, _, _ = calcular_tudo_custos(fixos_inputs, variaveis_inputs)

            # Calcular variáveis de forma determinística (LFA/h = 10% do diesel/h)
            diesel_tr_h = trator_consumo_h * trator_preco_litro
            reparos_tr_h = (trator_reparo_total / vida_trator_rep) if vida_trator_rep else 0.0
            lfa_tr_h = 0.10 * diesel_tr_h
            pneus_tr_h = (trator_pneus_total / vida_trator_pneu) if vida_trator_pneu else 0.0
            trator_variaveis_h = diesel_tr_h + reparos_tr_h + lfa_tr_h + pneus_tr_h

            diesel_sem_h = 0.0
            reparos_sem_h = (semeadora_reparo_total / vida_sem_rep) if vida_sem_rep else 0.0
            # Mesmo LFA/h do trator
            lfa_sem_h = lfa_tr_h
            pneus_sem_h = (semeadora_pneus_total / vida_sem_pneu) if vida_sem_pneu else 0.0
            sem_variaveis_h = diesel_sem_h + reparos_sem_h + lfa_sem_h + pneus_sem_h

            # Calcular totais finais
            trator_hora_maq = fx.trator_fixos_h + trator_variaveis_h
            semeadora_hora_maq = fx.semeadora_fixos_h + sem_variaveis_h
            conjunto_hora_maq = fx.conjunto_fixos_h + trator_variaveis_h + sem_variaveis_h

            # Atualizar UI
            self._trator_hora_maq_var.set(self._format(trator_hora_maq, 2))
            self._semeadora_hora_maq_var.set(self._format(semeadora_hora_maq, 2))
            self._conjunto_hora_maq_var.set(self._format(conjunto_hora_maq, 2))

            self._status_resultados_var.set("Custos hora/máquina calculados com sucesso.")

        except Exception as exc:
            self._status_resultados_var.set(f"Erro ao calcular: {exc}")

    def on_show(self) -> None:
        """Atualiza valores quando a aba é mostrada."""
        # Tentar preencher consumo/h se disponível
        consumo_h = self._get_consumo_h()
        if consumo_h and not self._trator_consumo_h_var.get():
            self._trator_consumo_h_var.set(self._format(consumo_h, 1))

