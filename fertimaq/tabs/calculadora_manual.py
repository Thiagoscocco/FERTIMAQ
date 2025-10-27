"""Manual calculation tabs reused from the original prototype."""

from __future__ import annotations

from typing import Iterable

import customtkinter as ctk

from ferticalc_ui_blueprint import SPACING, create_card, primary_button, section_title

from .base import FertiMaqTab, tab_registry


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

        primary_button(
            card,
            text="Executar cálculo com dados atuais",
            command=self.app.execute_calculo,
            row=start_row + len(rows),
            pady=(12, SPACING["card_padding"]["pady"]),
        )
