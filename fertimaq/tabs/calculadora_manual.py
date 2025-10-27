"""Manual calculation tabs reused from the original prototype."""

from __future__ import annotations

from typing import Iterable

import customtkinter as ctk

from ferticalc_ui_blueprint import SPACING, create_card, primary_button, section_title

from .base import FertiMaqTab, tab_registry


@tab_registry.register
class ConfiguracaoTab(FertiMaqTab):
    tab_id = "calculo_configuracao"
    title = "CONFIGURACAO"

    def build(self, frame: ctk.CTkFrame) -> None:
        frame.grid_columnconfigure(0, weight=1)

        card = create_card(frame, row=0, column=0)
        card.grid_columnconfigure(1, weight=1)
        section_title(card, "Entrada de parametros")

        label_padx = 20
        label_pady = (10, 2)
        control_pady = (0, 10)

        def add_option_row(row: int, text: str, variable: ctk.StringVar, values: Iterable[str]) -> None:
            ctk.CTkLabel(card, text=text, anchor="w").grid(
                row=row,
                column=0,
                sticky="ew",
                padx=label_padx,
                pady=label_pady,
            )
            menu = ctk.CTkOptionMenu(card, variable=variable, values=list(values))
            menu.grid(row=row, column=1, sticky="ew", padx=label_padx, pady=control_pady)

        def add_entry_row(row: int, text: str, variable: ctk.StringVar, placeholder: str) -> None:
            ctk.CTkLabel(card, text=text, anchor="w").grid(
                row=row,
                column=0,
                sticky="ew",
                padx=label_padx,
                pady=label_pady,
            )
            entry = ctk.CTkEntry(card, textvariable=variable, placeholder_text=placeholder)
            entry.grid(row=row, column=1, sticky="ew", padx=label_padx, pady=control_pady)

        add_option_row(1, "Preparo do solo", self.app.input_vars["preparo"], self.app.preparo_options.keys())
        add_option_row(2, "Tipo de solo", self.app.input_vars["solo"], self.app.solo_options.keys())
        add_option_row(3, "Sulcador", self.app.input_vars["sulcador"], self.app.sulcador_options.keys())

        add_entry_row(4, "Numero de linhas", self.app.input_vars["linhas"], "ex: 7")
        add_entry_row(5, "Aclive (%)", self.app.input_vars["aclive_percent"], "ex: 12.0")
        add_entry_row(6, "CV disponivel", self.app.input_vars["cv_trator_disponivel"], "ex: 80.0")
        add_entry_row(7, "Velocidade (km/h)", self.app.input_vars["velocidade_kmh"], "ex: 5.6")

        primary_button(card, text="Calcular", command=self.app.execute_calculo, row=8)


@tab_registry.register
class ResultadosTab(FertiMaqTab):
    tab_id = "calculo_resultados"
    title = "RESULTADOS"

    def build(self, frame: ctk.CTkFrame) -> None:
        frame.grid_columnconfigure(0, weight=1)

        card = create_card(frame, row=0, column=0)
        card.grid_columnconfigure(1, weight=1)
        section_title(card, "Resultados")

        ctk.CTkLabel(
            card,
            textvariable=self.app.status_var,
            anchor="w",
            text_color="#666666",
            wraplength=680,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(8, 12))

        rows = [
            ("Forca de tracao (N)", "ft_N"),
            ("Potencia na barra (kW)", "kw"),
            ("CV requerido", "cv_requerido"),
            ("CV disponivel", "cv_trator_disponivel"),
            ("Peso semeadora (t)", "peso_semeadora_t"),
            ("Peso trator (t)", "peso_trator_t"),
            ("Acrescimo por aclive (N)", "acrescimo_aclive_N"),
            ("Trator atende?", "atende"),
        ]

        start_row = 2
        for index, (label_text, key) in enumerate(rows):
            row = start_row + index
            ctk.CTkLabel(card, text=label_text, anchor="w").grid(
                row=row,
                column=0,
                sticky="ew",
                padx=20,
                pady=(0, 6),
            )
            ctk.CTkLabel(
                card,
                textvariable=self.app.result_vars[key],
                anchor="w",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=row, column=1, sticky="ew", padx=20, pady=(0, 6))
