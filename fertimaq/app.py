"""Core application harness for the modular FertiMaq UI."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

import customtkinter as ctk

from ferticalc_ui_blueprint import (
    SPACING,
    FooterSpec,
    TabsetSpec,
    WindowSpec,
    build_tab_shell,
    configure_window,
    footer_label,
    init_theme,
)
from logica_calc import Inputs, Preparo, Results, Solo, Sulcador, calcular

from .tabs import FertiMaqTab, tab_registry


class FertiMaqApp:
    """Application runner responsible for orchestrating tabs and shared state."""

    def __init__(
        self,
        *,
        window_spec: WindowSpec | None = None,
        footer_spec: FooterSpec | None = None,
    ) -> None:
        init_theme()

        self.root = ctk.CTk()
        self.window_spec = window_spec or WindowSpec(title="FertiMaq - Console de Calculo")
        configure_window(self.root, spec=self.window_spec)

        self.preparo_options: Mapping[str, Preparo] = {
            "Convencional": Preparo.CONVENCIONAL,
            "Plantio Direto": Preparo.PLANTIO_DIRETO,
        }
        self.solo_options: Mapping[str, Solo] = {
            "Arenoso": Solo.ARENOSO,
            "Medio": Solo.MEDIO,
            "Argiloso": Solo.ARGILOSO,
        }
        self.sulcador_options: Mapping[str, Sulcador] = {
            "Discos/Botinha": Sulcador.DISCOS,
            "Facao": Sulcador.FACAO,
        }

        self.input_vars: Dict[str, ctk.StringVar] = {
            "preparo": ctk.StringVar(value="Plantio Direto"),
            "solo": ctk.StringVar(value="Medio"),
            "sulcador": ctk.StringVar(value="Facao"),
            "linhas": ctk.StringVar(value="7"),
            "aclive_percent": ctk.StringVar(value="12.0"),
            "cv_trator_disponivel": ctk.StringVar(value="80.0"),
            "velocidade_kmh": ctk.StringVar(value="5.6"),
        }

        self.status_var = ctk.StringVar(value="Informe os dados e execute o calculo.")
        self.result_vars: Dict[str, ctk.StringVar] = {
            "ft_N": ctk.StringVar(value="--"),
            "kw": ctk.StringVar(value="--"),
            "cv_requerido": ctk.StringVar(value="--"),
            "cv_trator_disponivel": ctk.StringVar(value="--"),
            "peso_semeadora_t": ctk.StringVar(value="--"),
            "peso_trator_t": ctk.StringVar(value="--"),
            "acrescimo_aclive_N": ctk.StringVar(value="--"),
            "atende": ctk.StringVar(value="--"),
        }

        self._tabs: Dict[str, FertiMaqTab] = {}
        self._tab_titles: Dict[str, str] = {}

        self.container, self.tabview = self._build_tabview()

        footer = footer_spec or FooterSpec(text="FertiMaq - Modular Prototype")
        self.footer = footer_label(self.container, spec=footer)
        self.footer.grid_configure(pady=SPACING["footer"]["pady"])

    # ------------------------------------------------------------------ #
    # UI assembly
    # ------------------------------------------------------------------ #

    def _build_tabview(self):
        tab_classes: Sequence[type[FertiMaqTab]] = tab_registry.get_tabs()
        if not tab_classes:
            raise RuntimeError("Nenhuma aba registrada para o FertiMaq.")

        tab_spec = TabsetSpec(names=tuple(cls.title for cls in tab_classes))
        container, tabview = build_tab_shell(self.root, spec=tab_spec)

        for tab_cls in tab_classes:
            instance = tab_cls(self)
            frame = tabview.tab(tab_cls.title)
            frame.grid_columnconfigure(0, weight=1)
            instance.build(frame)
            self._tabs[instance.tab_id] = instance
            self._tab_titles[instance.tab_id] = instance.title

        return container, tabview

    # ------------------------------------------------------------------ #
    # Public API for tabs
    # ------------------------------------------------------------------ #

    def show_tab(self, tab_id: str) -> None:
        """Select a tab by its internal identifier."""
        title = self._tab_titles.get(tab_id)
        if not title:
            raise KeyError(f"Aba desconhecida: {tab_id}")
        self.tabview.set(title)
        tab = self._tabs.get(tab_id)
        if tab:
            tab.on_show()

    # ------------------------------------------------------------------ #
    # Calculation pipeline shared with tabs
    # ------------------------------------------------------------------ #

    def execute_calculo(self) -> None:
        """Trigger the calculation using current widget bindings."""
        try:
            inputs = self._collect_inputs()
        except ValueError as exc:
            self.status_var.set(f"Erro nos dados: {exc}")
            self._update_results(None)
            return

        try:
            resultado = calcular(inputs)
        except Exception as exc:  # safeguard in case of unexpected runtime error
            self.status_var.set(f"Falha ao calcular: {exc}")
            self._update_results(None)
            return

        self.status_var.set("Calculo executado com sucesso.")
        self._update_results(resultado)
        self.show_tab("calculo_resultados")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _collect_inputs(self) -> Inputs:
        preparo = self._map_choice(self.input_vars["preparo"].get(), self.preparo_options, "preparo do solo")
        solo = self._map_choice(self.input_vars["solo"].get(), self.solo_options, "solo")
        sulcador = self._map_choice(self.input_vars["sulcador"].get(), self.sulcador_options, "sulcador")

        linhas = self._parse_int(self.input_vars["linhas"].get(), "numero de linhas")
        aclive = self._parse_float(self.input_vars["aclive_percent"].get(), "aclive (%)")
        cv_disponivel = self._parse_float(self.input_vars["cv_trator_disponivel"].get(), "cv disponivel")
        velocidade = self._parse_float(self.input_vars["velocidade_kmh"].get(), "velocidade (km/h)")

        return Inputs(
            preparo=preparo,
            solo=solo,
            aclive_percent=aclive,
            sulcador=sulcador,
            linhas=linhas,
            cv_trator_disponivel=cv_disponivel,
            velocidade_kmh=velocidade,
        )

    def _map_choice(self, value: str, mapping: Mapping[str, object], field: str):
        try:
            return mapping[value]
        except KeyError as exc:
            raise ValueError(f"Selecione um valor valido para {field}.") from exc

    def _parse_float(self, raw: str, field: str) -> float:
        text = (raw or "").strip().replace(",", ".")
        if not text:
            raise ValueError(f"Informe um numero para {field}.")
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"Valor invalido em {field}.") from exc

    def _parse_int(self, raw: str, field: str) -> int:
        text = (raw or "").strip()
        if not text:
            raise ValueError(f"Informe um numero inteiro para {field}.")
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"Valor invalido em {field}.") from exc

    def _update_results(self, resultado: Results | None) -> None:
        if resultado is None:
            for var in self.result_vars.values():
                var.set("--")
            return

        self.result_vars["ft_N"].set(f"{resultado.ft_N:,.2f}")
        self.result_vars["kw"].set(f"{resultado.kw:,.3f}")
        self.result_vars["cv_requerido"].set(f"{resultado.cv_requerido:,.2f}")
        self.result_vars["cv_trator_disponivel"].set(f"{resultado.cv_trator_disponivel:,.2f}")
        self.result_vars["peso_semeadora_t"].set(f"{resultado.peso_semeadora_t:,.2f}")
        self.result_vars["peso_trator_t"].set(f"{resultado.peso_trator_t:,.2f}")
        self.result_vars["acrescimo_aclive_N"].set(f"{resultado.acrescimo_aclive_N:,.2f}")
        self.result_vars["atende"].set("SIM" if resultado.atende else "NAO")

    # ------------------------------------------------------------------ #
    # Runtime helpers
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = FertiMaqApp()
    app.run()
