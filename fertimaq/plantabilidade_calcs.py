"""Motores de cálculo da aba Plantabilidade (versão incorporada ao app)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Tuple


def sementes_por_ha(populacao_alvo: float, germinacao: float, sementes_puras: float, qualidade_plantio: float) -> float:
    """Calcula sementes necessárias por hectare conforme planilha."""
    base = populacao_alvo / germinacao / sementes_puras
    ajuste_qualidade = base * ((10.0 - qualidade_plantio) / 10.0)
    return base + ajuste_qualidade


def insumos_por_m_linear(sementes_ha: float, fertilizante_kg_ha: float, espacamento_m: float) -> Tuple[float, float, float]:
    """Retorna sementes/m, fertilizante g/m e espaçamento entre sementes (cm)."""
    sementes_por_m = (sementes_ha * espacamento_m) / 10000.0
    fertilizante_g_por_m = ((fertilizante_kg_ha * espacamento_m) / 10000.0) * 1000.0
    espacamento_sementes_cm = (100.0 / sementes_por_m) if sementes_por_m else float("inf")
    return sementes_por_m, fertilizante_g_por_m, espacamento_sementes_cm


def capacidade_campo(
    linhas_n: int,
    espacamento_m: float,
    velocidade_kmh: float,
    rendimento_operacional: float,
    area_total_ha: float,
) -> Tuple[float, float, float]:
    """Calcula largura útil, CCE (ha/h) e tempo de operação (h)."""
    largura_util_m = linhas_n * espacamento_m
    cce_ha_h = (largura_util_m * velocidade_kmh * rendimento_operacional) / 10.0
    tempo_operacao_h = (area_total_ha / cce_ha_h) if cce_ha_h else float("inf")
    return largura_util_m, cce_ha_h, tempo_operacao_h


def consumo_diesel_total(potencia_cv: float, tempo_operacao_h: float, fator_ml_por_cv_h: float = 110.0) -> float:
    """Calcula consumo total de diesel em litros."""
    return (fator_ml_por_cv_h * potencia_cv * tempo_operacao_h) / 1000.0


@dataclass
class ResultadosPlantabilidade:
    sementes_por_ha: float
    sementes_por_m: float
    fertilizante_g_por_m: float
    espacamento_sementes_cm: float
    largura_util_m: float
    cce_ha_h: float
    tempo_operacao_h: float
    consumo_total_l: float

    def asdict(self) -> Dict[str, float]:
        return asdict(self)


def calcular_tudo(
    populacao_alvo: float,
    germinacao: float,
    sementes_puras: float,
    qualidade_plantio: float,
    fertilizante_kg_ha: float,
    espacamento_m: float,
    linhas_n: int,
    velocidade_kmh: float,
    area_total_ha: float,
    rendimento_operacional: float,
    potencia_cv: float,
    fator_ml_por_cv_h: float = 110.0,
) -> ResultadosPlantabilidade:
    """Executa todos os cálculos principais de plantabilidade."""
    sementes_ha = sementes_por_ha(populacao_alvo, germinacao, sementes_puras, qualidade_plantio)
    sementes_m, fert_g_m, esp_cm = insumos_por_m_linear(sementes_ha, fertilizante_kg_ha, espacamento_m)
    largura, cce, tempo = capacidade_campo(linhas_n, espacamento_m, velocidade_kmh, rendimento_operacional, area_total_ha)
    consumo = consumo_diesel_total(potencia_cv, tempo, fator_ml_por_cv_h=fator_ml_por_cv_h)

    return ResultadosPlantabilidade(
        sementes_por_ha=sementes_ha,
        sementes_por_m=sementes_m,
        fertilizante_g_por_m=fert_g_m,
        espacamento_sementes_cm=esp_cm,
        largura_util_m=largura,
        cce_ha_h=cce,
        tempo_operacao_h=tempo,
        consumo_total_l=consumo,
    )
