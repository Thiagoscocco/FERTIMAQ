"""Motores de cálculo da aba Custos Hora/Máquina (baseado em logica_custos_hora_maq.py)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional


@dataclass
class FixosInputs:
    """Inputs para cálculo de custos fixos."""
    # TRATOR
    trator_valor_aquisicao: float
    trator_valor_sucata: float
    trator_anos_uso: float
    trator_horas_ano: float
    trator_taxa_juros: float
    trator_seguro_taxa: float
    trator_abrigo_taxa: float
    # SEMEADORA
    semeadora_valor_aquisicao: float
    semeadora_valor_sucata: float
    semeadora_anos_uso: float
    semeadora_horas_ano: float
    semeadora_taxa_juros: float
    semeadora_seguro_taxa: float
    semeadora_abrigo_taxa: float
    # Mão de obra/hora
    mao_obra_hora: float


@dataclass
class VariaveisInputs:
    """Inputs para cálculo de custos variáveis."""
    # DIESEL
    trator_consumo_h: float
    trator_preco_litro: float
    semeadora_consumo_h: float
    semeadora_preco_litro: float
    # REPAROS
    trator_valor_aquisicao_rep: float
    trator_horas_ano_rep: float
    trator_anos_uso_rep: float
    sem_valor_aquisicao_rep: float
    sem_horas_ano_rep: float
    sem_anos_uso_rep: float
    # LUB/FILT/ADT
    trator_valor_aquisicao_lfa: float
    trator_valor_filtros_ano: float
    trator_horas_ano_lfa: float
    trator_anos_uso_lfa: float
    sem_valor_aquisicao_lfa: float
    sem_valor_filtros_ano: float
    sem_horas_ano_lfa: float
    sem_anos_uso_lfa: float
    # PNEUS
    trator_valor_aquisicao_pneu: float
    trator_horas_ano_pneu: float
    trator_anos_uso_pneu: float
    sem_valor_aquisicao_pneu: float
    sem_horas_ano_pneu: float
    sem_anos_uso_pneu: float


@dataclass
class FixosOut:
    """Saídas do cálculo de custos fixos."""
    trator_depreciacao_h: float
    trator_juros_h: float
    trator_seguro_h: float
    trator_abrigo_h: float
    trator_fixos_h: float
    semeadora_depreciacao_h: float
    semeadora_juros_h: float
    semeadora_seguro_h: float
    semeadora_abrigo_h: float
    semeadora_fixos_h: float
    conjunto_fixos_h: float


@dataclass
class VariaveisOut:
    """Saídas do cálculo de custos variáveis."""
    trator_diesel_h: float
    trator_reparos_h: float
    trator_lfa_total_h: float
    trator_pneus_h: float
    trator_variaveis_h: float
    sem_diesel_h: float
    sem_reparos_h: float
    sem_lfa_total_h: float
    sem_pneus_h: float
    sem_variaveis_h: float
    conjunto_variaveis_h: float


@dataclass
class TotaisOut:
    """Totais de hora/máquina."""
    trator_hora_maquina: float
    semeadora_hora_maquina: float
    conjunto_hora_maquina: float


def _vida_util_horas(horas_ano: float, anos_uso: float) -> float:
    return horas_ano * anos_uso


def _depreciacao_por_hora(valor_aquisicao: float, valor_sucata: float, vida_util_horas: float) -> float:
    return (valor_aquisicao - valor_sucata) / vida_util_horas if vida_util_horas else float("inf")


def _juros_por_hora(valor_aquisicao: float, taxa_juros: float, horas_ano: float, anos_uso: float) -> float:
    return ((valor_aquisicao / 2.0) * taxa_juros) / horas_ano if horas_ano else float("inf")


def _seguro_por_hora(valor_aquisicao: float, taxa_seguro: float, horas_ano: float) -> float:
    return (valor_aquisicao * taxa_seguro) / horas_ano if horas_ano else float("inf")


def _abrigo_por_hora(valor_aquisicao: float, taxa_abrigo: float, horas_ano: float) -> float:
    return (valor_aquisicao * taxa_abrigo) / horas_ano if horas_ano else float("inf")


def calc_fixos(inputs: FixosInputs) -> FixosOut:
    """Calcula custos fixos por hora."""
    # TRATOR
    vida_trator = _vida_util_horas(inputs.trator_horas_ano, inputs.trator_anos_uso)
    trator_depr = _depreciacao_por_hora(inputs.trator_valor_aquisicao, inputs.trator_valor_sucata, vida_trator)
    trator_juros = _juros_por_hora(inputs.trator_valor_aquisicao, inputs.trator_taxa_juros, inputs.trator_horas_ano, inputs.trator_anos_uso)
    trator_seguro = _seguro_por_hora(inputs.trator_valor_aquisicao, inputs.trator_seguro_taxa, inputs.trator_horas_ano)
    trator_abrigo = _abrigo_por_hora(inputs.trator_valor_aquisicao, inputs.trator_abrigo_taxa, inputs.trator_horas_ano)
    
    # SEMEADORA
    vida_sem = _vida_util_horas(inputs.semeadora_horas_ano, inputs.semeadora_anos_uso)
    sem_depr = _depreciacao_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_valor_sucata, vida_sem)
    sem_juros = _juros_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_taxa_juros, inputs.semeadora_horas_ano, inputs.semeadora_anos_uso)
    sem_seguro = _seguro_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_seguro_taxa, inputs.semeadora_horas_ano)
    sem_abrigo = _abrigo_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_abrigo_taxa, inputs.semeadora_horas_ano)

    # FIXOS por hora
    trator_fixos_h = trator_depr + trator_juros + trator_seguro + trator_abrigo + inputs.mao_obra_hora
    sem_fixos_h = sem_depr + sem_juros + sem_seguro + sem_abrigo
    conjunto_fixos_h = trator_fixos_h + sem_fixos_h

    return FixosOut(
        trator_depreciacao_h=trator_depr,
        trator_juros_h=trator_juros,
        trator_seguro_h=trator_seguro,
        trator_abrigo_h=trator_abrigo,
        trator_fixos_h=trator_fixos_h,
        semeadora_depreciacao_h=sem_depr,
        semeadora_juros_h=sem_juros,
        semeadora_seguro_h=sem_seguro,
        semeadora_abrigo_h=sem_abrigo,
        semeadora_fixos_h=sem_fixos_h,
        conjunto_fixos_h=conjunto_fixos_h
    )


def _diesel_por_hora(consumo_l_h: float, preco_litro: float) -> float:
    return consumo_l_h * preco_litro


def _reparos_por_hora(valor_aquisicao: float, fator_reparo: float, horas_ano: float, anos_uso: float) -> float:
    vida = horas_ano * anos_uso
    total_reparo = valor_aquisicao * fator_reparo
    return total_reparo / vida if vida else float("inf")


def _lfa_por_hora(valor_aquisicao: float, valor_filtros_ano: float, horas_ano: float, anos_uso: float,
                  fator_lub: float, fator_aditivo: float) -> float:
    vida = horas_ano * anos_uso
    lub = (valor_aquisicao * fator_lub) / vida if vida else float("inf")
    adt = (valor_aquisicao * fator_aditivo) / vida if vida else float("inf")
    filtros = (valor_filtros_ano * anos_uso) / vida if vida else float("inf")
    return lub + adt + filtros


def _pneus_por_hora(valor_aquisicao: float, horas_ano: float, anos_uso: float, fator: float) -> float:
    vida = horas_ano * anos_uso
    return (valor_aquisicao * fator) / vida if vida else float("inf")


def calc_variaveis(inputs: VariaveisInputs) -> VariaveisOut:
    """Calcula custos variáveis por hora."""
    # TRATOR
    trator_diesel = _diesel_por_hora(inputs.trator_consumo_h, inputs.trator_preco_litro)
    trator_reparos = _reparos_por_hora(inputs.trator_valor_aquisicao_rep, 0.65, inputs.trator_horas_ano_rep, inputs.trator_anos_uso_rep)
    trator_lfa = _lfa_por_hora(inputs.trator_valor_aquisicao_lfa, inputs.trator_valor_filtros_ano,
                               inputs.trator_horas_ano_lfa, inputs.trator_anos_uso_lfa,
                               fator_lub=0.10, fator_aditivo=0.015)
    trator_pneus = _pneus_por_hora(inputs.trator_valor_aquisicao_pneu, inputs.trator_horas_ano_pneu, inputs.trator_anos_uso_pneu, fator=0.15)
    trator_variaveis_h = trator_diesel + trator_reparos + trator_lfa + trator_pneus

    # SEMEADORA
    sem_diesel = _diesel_por_hora(inputs.semeadora_consumo_h, inputs.semeadora_preco_litro)
    sem_reparos = _reparos_por_hora(inputs.sem_valor_aquisicao_rep, 0.30, inputs.sem_horas_ano_rep, inputs.sem_anos_uso_rep)
    sem_lfa = _lfa_por_hora(inputs.sem_valor_aquisicao_lfa, 0.0,
                            inputs.sem_horas_ano_lfa, inputs.sem_anos_uso_lfa,
                            fator_lub=0.03, fator_aditivo=0.005)
    sem_pneus = _pneus_por_hora(inputs.sem_valor_aquisicao_pneu, inputs.sem_horas_ano_pneu, inputs.sem_anos_uso_pneu, fator=0.02)
    sem_variaveis_h = sem_diesel + sem_reparos + sem_lfa + sem_pneus

    conjunto_variaveis_h = trator_variaveis_h + sem_variaveis_h

    return VariaveisOut(
        trator_diesel_h=trator_diesel,
        trator_reparos_h=trator_reparos,
        trator_lfa_total_h=trator_lfa,
        trator_pneus_h=trator_pneus,
        trator_variaveis_h=trator_variaveis_h,
        sem_diesel_h=sem_diesel,
        sem_reparos_h=sem_reparos,
        sem_lfa_total_h=sem_lfa,
        sem_pneus_h=sem_pneus,
        sem_variaveis_h=sem_variaveis_h,
        conjunto_variaveis_h=conjunto_variaveis_h
    )


def calcular_tudo_custos(fixos: FixosInputs, variaveis: VariaveisInputs) -> tuple[FixosOut, VariaveisOut, TotaisOut]:
    """Calcula todos os custos e retorna os resultados completos."""
    fx = calc_fixos(fixos)
    var = calc_variaveis(variaveis)
    
    trator_hora_maq = fx.trator_fixos_h + var.trator_variaveis_h
    semeadora_hora_maq = fx.semeadora_fixos_h + var.sem_variaveis_h
    conjunto_hora_maq = fx.conjunto_fixos_h + var.conjunto_variaveis_h
    
    totais = TotaisOut(
        trator_hora_maquina=trator_hora_maq,
        semeadora_hora_maquina=semeadora_hora_maq,
        conjunto_hora_maquina=conjunto_hora_maq
    )
    
    return fx, var, totais


# ========================
# ESTIMATIVAS
# ========================
@dataclass
class EstimativasInputs:
    """Inputs para geração de estimativas."""
    trator_cv: float
    semeadora_linhas: float
    area_ha: float
    cce_ha_h: float
    trator_consumo_h: float
    preco_diesel: float = 6.0
    taxa_seguro: float = 0.02
    taxa_abrigo: float = 0.01
    taxa_juros: float = 0.06
    mao_obra_salario_min: float = 3000.0
    fator_salario_por_h: float = 2.8
    horas_mes: float = 240.0


@dataclass
class EstimativasOut:
    """Outputs das estimativas."""
    fixos_inputs: FixosInputs
    variaveis_inputs: VariaveisInputs


def estimar_parametros(inputs: EstimativasInputs) -> EstimativasOut:
    """Gera estimativas de parâmetros conforme planilha."""
    # Valores iniciais
    tr_val_ini = inputs.trator_cv * 3000.0
    sem_val_ini = inputs.semeadora_linhas * 20000.0
    # Sucata
    tr_suc = tr_val_ini * 0.30
    sem_suc = sem_val_ini * 0.40
    # Anos
    tr_anos = 10.0
    sem_anos = 10.0
    # Horas/ano
    tr_horas_ano = inputs.area_ha * 10.0
    sem_horas_ano = inputs.cce_ha_h * inputs.area_ha
    # Mão de obra
    mao_obra_h = (inputs.mao_obra_salario_min * inputs.fator_salario_por_h) / inputs.horas_mes

    fixos = FixosInputs(
        trator_valor_aquisicao=tr_val_ini,
        trator_valor_sucata=tr_suc,
        trator_anos_uso=tr_anos,
        trator_horas_ano=tr_horas_ano,
        trator_taxa_juros=inputs.taxa_juros,
        trator_seguro_taxa=inputs.taxa_seguro,
        trator_abrigo_taxa=inputs.taxa_abrigo,
        semeadora_valor_aquisicao=sem_val_ini,
        semeadora_valor_sucata=sem_suc,
        semeadora_anos_uso=sem_anos,
        semeadora_horas_ano=sem_horas_ano,
        semeadora_taxa_juros=inputs.taxa_juros,
        semeadora_seguro_taxa=inputs.taxa_seguro,
        semeadora_abrigo_taxa=inputs.taxa_abrigo,
        mao_obra_hora=mao_obra_h
    )

    # Variáveis estimadas
    preco = inputs.preco_diesel

    var = VariaveisInputs(
        trator_consumo_h=inputs.trator_consumo_h,
        trator_preco_litro=preco,
        semeadora_consumo_h=0.0,
        semeadora_preco_litro=preco,
        trator_valor_aquisicao_rep=tr_val_ini,
        trator_horas_ano_rep=tr_horas_ano,
        trator_anos_uso_rep=tr_anos,
        sem_valor_aquisicao_rep=sem_val_ini,
        sem_horas_ano_rep=sem_horas_ano,
        sem_anos_uso_rep=sem_anos,
        trator_valor_aquisicao_lfa=tr_val_ini,
        trator_valor_filtros_ano=800.0,
        trator_horas_ano_lfa=tr_horas_ano,
        trator_anos_uso_lfa=tr_anos,
        sem_valor_aquisicao_lfa=sem_val_ini,
        sem_valor_filtros_ano=0.0,
        sem_horas_ano_lfa=sem_horas_ano,
        sem_anos_uso_lfa=sem_anos,
        trator_valor_aquisicao_pneu=tr_val_ini,
        trator_horas_ano_pneu=tr_horas_ano,
        trator_anos_uso_pneu=tr_anos,
        sem_valor_aquisicao_pneu=sem_val_ini,
        sem_horas_ano_pneu=sem_horas_ano,
        sem_anos_uso_pneu=sem_anos
    )

    return EstimativasOut(fixos_inputs=fixos, variaveis_inputs=var)

