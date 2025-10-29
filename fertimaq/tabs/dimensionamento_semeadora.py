"""Tab responsible for sizing the seeder set based on the existing calculation engine."""

from __future__ import annotations

import math
from dataclasses import replace

import customtkinter as ctk

from ferticalc_ui_blueprint import create_card, primary_button, section_title
from fertimaq.plantabilidade_calcs import capacidade_campo
from logica_calc import Inputs, Sulcador, calcular

from .base import FertiMaqTab, tab_registry


@tab_registry.register
class DimensionamentoSemeadoraTab(FertiMaqTab):
    tab_id = "dimensionamento_semeadora"
    title = "DIMENSIONAMENTO DA SEMEADORA"

    def __init__(self, app: "FertiMaqApp") -> None:
        super().__init__(app)
        # Conjunto vars
        self._linhas_var = ctk.StringVar(value="7")
        self._sulcador_var = ctk.StringVar(value="Discos Duplos")
        self._tracao_var = ctk.StringVar(value="4 x 2")
        self._cv_trator_var = ctk.StringVar(value="80.0")
        self._velocidade_var = ctk.StringVar(value="5.6")
        self._rendimento_operacional_var = self.app.input_vars.get("rendimento_operacional", ctk.StringVar(value="65"))

        # Area vars
        self._preparo_var = ctk.StringVar(value="Plantio Direto")
        self._solo_var = ctk.StringVar(value="Medio")
        self._superficie_var = ctk.StringVar(value="Media")
        self._aclive_display_var = ctk.StringVar(value="Aclive selecionado: --")

        # Result vars
        self._status_var = ctk.StringVar(value="Informe os dados e calcule o dimensionamento.")
        self._peso_semeadora_var = ctk.StringVar(value="--")
        self._peso_trator_var = ctk.StringVar(value="--")
        self._peso_conjunto_var = ctk.StringVar(value="--")
        self._cv_com_aclive_var = ctk.StringVar(value="--")
        self._cv_plano_var = ctk.StringVar(value="--")
        self._cv_disponivel_var = ctk.StringVar(value="--")
        self._cv_util_var = ctk.StringVar(value="--")
        self._eficiencia_tracao_var = ctk.StringVar(value="--")
        self._status_label_ref: ctk.CTkLabel | None = None
        self._limite_aclive_var = ctk.StringVar(value="")
        self._sulcador_highlight_var = ctk.StringVar(value="")
        self._section_states: dict[str, bool] = {}
        self._collapsible_sections: dict[str, dict[str, object]] = {}

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

        # Tracao
        ctk.CTkLabel(conjunto_body, text="Tipo de tracao do trator", anchor="w").grid(row=3, column=0, sticky="w", pady=6)
        self._tracao_menu = ctk.CTkOptionMenu(
            conjunto_body,
            values=list(self.app.tracao_options.keys()),
            variable=self._tracao_var,
            anchor="w",
        )
        self._tracao_menu.grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=6)

        # Velocidade
        ctk.CTkLabel(conjunto_body, text="Velocidade desejada (km/h)", anchor="w").grid(
            row=4, column=0, sticky="w", pady=6
        )
        ctk.CTkEntry(conjunto_body, textvariable=self._velocidade_var, width=140).grid(
            row=4, column=1, sticky="ew", padx=(12, 0), pady=6
        )

        # Rendimento operacional (%)
        ctk.CTkLabel(conjunto_body, text="Rendimento operacional (%)", anchor="w").grid(row=5, column=0, sticky="w", pady=6)
        ctk.CTkEntry(conjunto_body, textvariable=self._rendimento_operacional_var, width=140).grid(
            row=5, column=1, sticky="ew", padx=(12, 0), pady=6
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

        ctk.CTkLabel(area_body, text="Superficie do solo", anchor="w").grid(row=2, column=0, sticky="w", pady=6)
        self._superficie_menu = ctk.CTkOptionMenu(
            area_body,
            values=list(self.app.superficie_options.keys()),
            variable=self._superficie_var,
            anchor="w",
        )
        self._superficie_menu.grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=6)

        ctk.CTkLabel(
            area_body,
            textvariable=self._aclive_display_var,
            anchor="w",
            text_color="#eef1fb",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))

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
        section_title(resultado_card, "CÁLCULOS REALIZADOS")

        self._status_label_ref = ctk.CTkLabel(
            resultado_card,
            textvariable=self._status_var,
            anchor="w",
            wraplength=320,
            text_color="#666666",
        )
        self._status_label_ref.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 16))
        self._status_var_color("#666666")

        current_row = 2
        self._pesos_content, current_row = self._create_collapsible_section(
            resultado_card, row=current_row, title="Pesos", key="pesos"
        )
        self._add_result_row(self._pesos_content, 0, "Peso da semeadora (t)", self._peso_semeadora_var)
        self._add_result_row(self._pesos_content, 1, "Peso do trator (t)", self._peso_trator_var)
        self._add_result_row(self._pesos_content, 2, "Peso do conjunto (t)", self._peso_conjunto_var)

        self._cv_content, current_row = self._create_collapsible_section(
            resultado_card, row=current_row, title="CV", key="cvs"
        )
        self._add_result_row(self._cv_content, 0, "CV disponivel informado", self._cv_disponivel_var)
        self._add_result_row(self._cv_content, 1, "CV necessario (com aclive)", self._cv_com_aclive_var)
        self._add_result_row(self._cv_content, 2, "CV necessario (terreno plano)", self._cv_plano_var)
        self._add_result_row(self._cv_content, 3, "Eficiencia de tracao (%)", self._eficiencia_tracao_var)
        self._add_result_row(self._cv_content, 4, "CV util (com eficiencia)", self._cv_util_var)

        recomendacao_card = create_card(
            bottom_row,
            row=0,
            column=1,
            sticky="nsew",
            padding={"padx": (10, 0), "pady": (0, 0)},
        )
        recomendacao_card.grid_columnconfigure(0, weight=1)
        recomendacao_card.grid_rowconfigure(2, weight=0)
        section_title(recomendacao_card, "RESULTADOS DO DIMENSIONAMENTO")

        self._recomendacao_var = ctk.StringVar(value="Calcule o dimensionamento para receber resultados.")
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
        ).grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 10))

        ctk.CTkLabel(
            recomendacao_card,
            textvariable=self._sulcador_highlight_var,
            anchor="w",
            wraplength=320,
            justify="left",
            text_color="#f0a935",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=4, column=0, sticky="sew", padx=20, pady=(0, 16))

        # Painel visual: rendimento e tempo estimado
        # Destaques diretamente no card (sem quadro interno)
        self._cce_display_var = ctk.StringVar(value="--")
        self._tempo_total_display_var = ctk.StringVar(value="--")
        ctk.CTkLabel(recomendacao_card, text="CCE (ha/h)", anchor="w", text_color="#a9b7d9").grid(row=2, column=0, sticky="w", pady=(6, 2), padx=20)
        ctk.CTkLabel(recomendacao_card, textvariable=self._cce_display_var, anchor="w", text_color="#f2f4ff", font=ctk.CTkFont(size=18, weight="bold")).grid(row=2, column=0, sticky="e", pady=(6, 2), padx=20)
        ctk.CTkLabel(recomendacao_card, text="Tempo estimado (toda operação)", anchor="w", text_color="#a9b7d9").grid(row=3, column=0, sticky="w", pady=(2, 10), padx=20)
        ctk.CTkLabel(recomendacao_card, textvariable=self._tempo_total_display_var, anchor="w", text_color="#f2f4ff", font=ctk.CTkFont(size=18, weight="bold")).grid(row=3, column=0, sticky="e", pady=(2, 10), padx=20)

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

    def _create_collapsible_section(
        self, parent: ctk.CTkFrame, *, row: int, title: str, key: str
    ) -> tuple[ctk.CTkFrame, int]:
        header_frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=12)
        header_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 6))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.configure(cursor="hand2")
        label_var = ctk.StringVar(value=self._format_section_label(title, expanded=False))
        header_label = ctk.CTkLabel(
            header_frame,
            textvariable=label_var,
            anchor="w",
            text_color="#eef1fb",
            font=ctk.CTkFont(weight="bold"),
        )
        header_label.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        header_label.configure(cursor="hand2")
        header_frame.bind("<Button-1>", lambda _event, k=key: self._toggle_section(k))
        header_label.bind("<Button-1>", lambda _event, k=key: self._toggle_section(k))

        content_frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=12)
        content_frame.grid(row=row + 1, column=0, sticky="ew", padx=20, pady=(0, 12))
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)

        self._collapsible_sections[key] = {
            "frame": content_frame,
            "label_var": label_var,
            "title": title,
        }
        self._set_section_state(key, expanded=False)

        return content_frame, row + 2

    def _format_section_label(self, title: str, *, expanded: bool) -> str:
        arrow = "▴" if expanded else "▾"
        return f"{title} {arrow}"

    def _set_section_state(self, key: str, *, expanded: bool) -> None:
        self._section_states[key] = expanded
        section = self._collapsible_sections.get(key)
        if not section:
            return
        frame = section["frame"]
        label_var: ctk.StringVar = section["label_var"]  # type: ignore[assignment]
        title = section["title"]
        if expanded:
            frame.grid()
        else:
            frame.grid_remove()
        label_var.set(self._format_section_label(str(title), expanded=expanded))

    def _toggle_section(self, key: str) -> None:
        current = self._section_states.get(key, False)
        self._set_section_state(key, expanded=not current)

    def _refresh_aclive_label(self) -> None:
        text = self.app.field_vars["slope_selected_deg"].get()
        if text:
            self._aclive_display_var.set(f"Aclive selecionado: {text} graus")
        else:
            self._aclive_display_var.set("Aclive selecionado: --")

    def _executar_calculo(self) -> None:
        self._sulcador_highlight_var.set("")
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
            tracao = self.app.tracao_options[self._tracao_var.get()]
            superficie = self.app.superficie_options[self._superficie_var.get()]
            sulcador = self.app.sulcador_options[self._sulcador_var.get()]
        except KeyError:
            self._status_var.set("Selecione preparo, solo, superficie, tracao e sulcador validos.")
            self._status_var_callback(error=True)
            return

        slope_deg_text = self.app.field_vars["slope_selected_deg"].get()
        slope_deg = float(slope_deg_text.replace(",", ".")) if slope_deg_text else 0.0
        aclive_percent = math.tan(math.radians(slope_deg)) * 100.0

        base_inputs = Inputs(
            preparo=preparo,
            solo=solo,
            tracao=tracao,
            superficie=superficie,
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
        if sulcador is Sulcador.DISCOS:
            self._sulcador_highlight_var.set(
                "Discos duplos selecionados:\nMilho: 6,5 km/h | Outras culturas: ate 7,5 km/h."
            )
        else:
            self._sulcador_highlight_var.set(
                "Facao selecionado:\nMilho: 5,5 km/h | Outras culturas: ate 6 km/h."
            )

        peso_conjunto = resultado.peso_semeadora_t + resultado.peso_trator_t
        self._peso_semeadora_var.set(f"{resultado.peso_semeadora_t:,.2f}".replace(",", "."))
        self._peso_trator_var.set(f"{resultado.peso_trator_t:,.2f}".replace(",", "."))
        self._peso_conjunto_var.set(f"{peso_conjunto:,.2f}".replace(",", "."))
        self._cv_com_aclive_var.set(f"{resultado.cv_requerido:,.2f}".replace(",", "."))
        self._cv_plano_var.set(f"{plano.cv_requerido:,.2f}".replace(",", "."))
        self._cv_disponivel_var.set(f"{resultado.cv_trator_disponivel:,.2f}".replace(",", "."))
        self._cv_util_var.set(f"{resultado.cv_tracionavel:,.2f}".replace(",", "."))
        eficiencia_pct = resultado.eficiencia_tracao * 100.0
        self._eficiencia_tracao_var.set(f"{eficiencia_pct:.0f}%".replace(",", "."))

        recomendacao, limite_info = self._gerar_recomendacao(
            resultado,
            plano,
            resultado.cv_tracionavel,
            linhas,
            velocidade,
            aclive_percent,
        )
        self._recomendacao_var.set(recomendacao)
        self._limite_aclive_var.set(limite_info)

        # Disponibilizar os valores dimensionados para outras abas (ex.: Plantabilidade)
        try:
            self.app.input_vars["linhas"].set(str(linhas))
            self.app.input_vars["cv_trator_disponivel"].set(f"{cv_disponivel:.2f}".replace(".", ","))
            self.app.input_vars["velocidade_kmh"].set(f"{velocidade:.2f}".replace(".", ","))
        except Exception:
            # Falha silenciosa para não quebrar o fluxo da aba
            pass

        # Calcular tempo total de operação usando rendimento, área e espaçamento (da aba Plantabilidade)
        try:
            rendimento_pct = float(self._rendimento_operacional_var.get().replace(",", "."))
            rendimento = rendimento_pct / 100.0 if rendimento_pct else 0.0
        except ValueError:
            rendimento = 0.0

        area_text = self.app.field_vars.get("area_hectares", ctk.StringVar(value="")).get()
        try:
            area_ha = float(area_text.replace(",", ".")) if area_text else 0.0
        except ValueError:
            area_ha = 0.0

        espacamento_m = None
        try:
            planta_tab = self.app._tabs.get("plantabilidade")
            if planta_tab is not None:
                espacamento_text = planta_tab._espacamento_var.get()
                espacamento_m = float(espacamento_text.replace(",", ".")) / 100.0
        except Exception:
            espacamento_m = None

        if espacamento_m and rendimento and area_ha:
            try:
                largura, cce, tempo = capacidade_campo(linhas, espacamento_m, velocidade, rendimento, area_ha)
                self._cce_display_var.set(f"{cce:,.2f}".replace(",", "."))
                self._tempo_total_display_var.set(f"{tempo:,.1f} h".replace(",", "."))
            except Exception:
                self._cce_display_var.set("--")
                self._tempo_total_display_var.set("--")
        else:
            # Tenta fallback ao tempo já calculado na Plantabilidade
            try:
                planta_tab = self.app._tabs.get("plantabilidade")
                tempo_text = getattr(planta_tab, "_tempo_operacao_var", ctk.StringVar(value="--")).get()
                self._tempo_total_display_var.set(tempo_text if tempo_text else "--")
                # Tenta também pegar CCE da plantabilidade
                cce_text = getattr(planta_tab, "_cce_var", ctk.StringVar(value="--")).get()
                self._cce_display_var.set(cce_text if cce_text else "--")
            except Exception:
                self._tempo_total_display_var.set("--")
                self._cce_display_var.set("--")

    def _gerar_recomendacao(
        self,
        resultado: "Results",
        plano: "Results",
        cv_tracionavel: float,
        linhas: int,
        velocidade_kmh: float,
        aclive_percent: float,
    ) -> tuple[str, str]:
        deficit = resultado.cv_requerido - cv_tracionavel
        if deficit <= 0:
            return ("O conjunto consegue atender a velocidade necessaria para a operacao.", "")

        if deficit > 25:
            limite_msg = self._slope_limite_mensagem(
                plano.cv_requerido, resultado.cv_requerido, cv_tracionavel, aclive_percent
            )
            return (
                "O trator atual nao atende. Considere reduzir o numero de linhas da semeadora "
                "ou utilizar um trator mais potente.",
                limite_msg,
            )

        # deficit <= 25: sugerir reduzir velocidade.
        # cv requerido proporcional a velocidade (kW cresce proporcionalmente). Ajuste multiplicativo:
        velocidade_sugerida = max(1.0, velocidade_kmh * (cv_tracionavel / resultado.cv_requerido))
        velocidade_sugerida = round(velocidade_sugerida, 2)
        limite_msg = self._slope_limite_mensagem(
            plano.cv_requerido, resultado.cv_requerido, cv_tracionavel, aclive_percent
        )
        return (
            "O trator atende se a velocidade for reduzida. "
            f"Sugestao: operar a aproximadamente {velocidade_sugerida} km/h.",
            limite_msg,
        )

    def _slope_limite_mensagem(
        self,
        cv_plano: float,
        cv_total: float,
        cv_tracionavel: float,
        aclive_percent: float,
    ) -> str:
        extra_atual = max(cv_total - cv_plano, 0.0)
        extra_disponivel = max(cv_tracionavel - cv_plano, 0.0)
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

