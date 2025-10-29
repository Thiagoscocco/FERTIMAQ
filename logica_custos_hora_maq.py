
"""
custos_hora_maquina.py
---------------------------------
Motores de cálculo extraídos 1:1 do arquivo "Hora Maquina.xlsx"
(abas: "fixos e variaveis" e "estimativas").

Este módulo NÃO lê a planilha: todas as fórmulas estão codificadas aqui,
reproduzindo a lógica de cada célula relevante.

Sumário das fórmulas (mapeamento por célula da planilha):
  [fixos e variaveis]
    - C11 = C9*C10                              (Vida útil TRATOR, horas)
    - C12 = (C7 - C8) / C11                     (Depreciação TRATOR por hora)
    - C20 = ((C17/2) * C18) / C19               (Juros TRATOR por hora)
    - C28 = (C25 * C26) / C27                   (Seguro TRATOR por hora)
    - C36 = (C33 * C34) / C35                   (Abrigo TRATOR por hora)
    - F11 = F9 * F10                            (Vida útil SEMEADORA, horas)
    - F12 = (F7 - F8) / F11                     (Depreciação SEMEADORA por hora)
    - F20 = ((F17/2) * F18) / F19               (Juros SEMEADORA por hora)
    - F28 = (F25 * F26) / F27                   (Seguro SEMEADORA por hora)
    - F36 = (F33 * F34) / F35                   (Abrigo SEMEADORA por hora)
    - I9  = I7 * I8                             (Diesel TRATOR por hora: consumo * preço)
    - I16 = I15 * 0.65                          (Custo reparo TRATOR total ref. aquisição)
    - I18 = I14 * I17                           (Vida útil TRATOR p/ reparos, horas)
    - I19 = I16 / I18                           (Reparos TRATOR por hora)
    - L19 = L16 / L18                           (Reparos SEMEADORA por hora; L16 = L15*0.3 ; L18 = L14*L17)
    - I26 = I24 * 0.015                         (Aditivos TRATOR base)
    - L26 = L24 * 0.005                         (Aditivos SEMEADORA base)
    - I29 = I27 * I28                           (Vida útil TRATOR lubs, horas)
    - L29 = L27 * L28                           (Vida útil SEMEADORA lubs, horas)
    - I30 = (I24 * 0.1) / I29                   (Lubrificantes TRATOR por hora)
    - L30 = (L24 * 0.03) / L29                  (Lubrificantes SEMEADORA por hora)
    - I31 = I26 / I29                           (Aditivos TRATOR por hora)
    - L31 = L26 / L29                           (Aditivos SEMEADORA por hora)
    - I32 = (I25 * I28) / I29                   (Filtros TRATOR por hora)
    - L32 = 0                                   (Filtros SEMEADORA por hora, fixado na planilha)
    - I33 = SUM(I30:I32)                        (Total LUB/FILT/ADT TRATOR por hora)
    - L33 = SUM(L30:L32)                        (Total LUB/FILT/ADT SEMEADORA por hora)
    - I41 = I39 * I40                           (Vida útil TRATOR pneus, horas)
    - L41 = L39 * L40                           (Vida útil SEMEADORA pneus, horas)
    - I42 = (I38 * 0.15) / I41                  (Pneus TRATOR por hora)
    - L42 = (L38 * 0.02) / L41                  (Pneus SEMEADORA por hora)
    - O5  = C12 + C20 + C28 + C36 + F42         (FIXOS TRATOR por hora; inclui Mão de Obra/h calculada em F42)
    - O10 = F12 + F20 + F28 + F36               (FIXOS SEMEADORA por hora)
    - O6  = I9 + I19 + I33 + I42                (VARIÁVEIS TRATOR por hora)
    - O11 = L9 + L19 + L33 + L42                (VARIÁVEIS SEMEADORA por hora)
    - O15 = O5 + O10                            (FIXOS CONJUNTO por hora)
    - O16 = O6 + O11                            (VARIÁVEIS CONJUNTO por hora)
    - O17 = O15 + O16                           (TOTAL HORA/MÁQUINA)

    Observação: F42 = (C42 * 2.8) / 240         (Mão de obra por hora) entra em O5

  [estimativas]
    - C15 = C5 * 3000                           (Valor inicial TRATOR estimado: CV * 3000)
    - F15 = C6 * 20000                          (Valor inicial SEMEADORA estimado: Nº linhas * 20000)
    - C16 = C15 * 0.3                           (Sucata TRATOR 30%)
    - F16 = F15 * 0.4                           (Sucata SEMEADORA 40%)
    - C17 = 10 ; F17 = 10                       (Anos de uso)
    - C18 = C7 * 10                             (Horas/ano TRATOR: Área * 10)
    - F18 = C8 * C7                             (Horas/ano SEMEADORA: CCE * Área)
    - C19 = C18 * C17 ; F19 = F18 * F17         (Vida útil horas)
    - C26 = 6 ; F26 = 0                         (Diesel/h estimado TRATOR e SEMEADORA)
    - C27 = C15 * 0.4 ; F27 = F15 * 0.4         (Custo reparo total p/ cálculo hora)
    - C28 = 0.1 * (C26 * C9) ; F28 igual        (Lubs/filters/adt estimados em função de diesel e consumo/h)
    - C29 = (C15*0.07)/C18 ; F29 = (F15*0.01)/F18 (Pneus por hora estimados)
    - C22 = 0.02 ; C23 = 0.01                   (Taxas: seguro 2%; abrigo 1%)
    - C24 (Mão de Obra): 35 (valor de referência, usado externamente)

Convenções:
  - Percentuais são informados como frações (ex.: 6% -> 0.06).
  - Esta implementação aceita valores do usuário (inputs) ou
    gera valores estimados pelas fórmulas da aba "estimativas".

"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict


# ========================
# Dataclasses de entrada
# ========================
@dataclass
class FixosInputs:
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
    # Mão de obra/hora (F42), calculada externamente a partir do salário-mínimo, mas aceita aqui como input direto
    mao_obra_hora: float


@dataclass
class VariaveisInputs:
    # DIESEL
    trator_consumo_h: float    # I7 (L/h)
    trator_preco_litro: float  # I8 (R$/L)
    semeadora_consumo_h: float # L7 (normalmente 0)
    semeadora_preco_litro: float # L8 (R$/L)
    # REPAROS (base)
    trator_valor_aquisicao_rep: float  # I15
    trator_horas_ano_rep: float        # I14
    trator_anos_uso_rep: float         # I17
    sem_valor_aquisicao_rep: float     # L15
    sem_horas_ano_rep: float           # L14
    sem_anos_uso_rep: float            # L17
    # LUB/FILT/ADT (base)
    trator_valor_aquisicao_lfa: float  # I24
    trator_valor_filtros_ano: float    # I25
    trator_horas_ano_lfa: float        # I27
    trator_anos_uso_lfa: float         # I28
    sem_valor_aquisicao_lfa: float     # L24
    sem_valor_filtros_ano: float       # L25
    sem_horas_ano_lfa: float           # L27
    sem_anos_uso_lfa: float            # L28
    # PNEUS
    trator_valor_aquisicao_pneu: float # I38
    trator_horas_ano_pneu: float       # I39
    trator_anos_uso_pneu: float        # I40
    sem_valor_aquisicao_pneu: float    # L38
    sem_horas_ano_pneu: float          # L39
    sem_anos_uso_pneu: float           # L40


# ========================
# Dataclasses de saída
# ========================
@dataclass
class FixosOut:
    # TRATOR
    trator_depreciacao_h: float   # C12
    trator_juros_h: float         # C20
    trator_seguro_h: float        # C28
    trator_abrigo_h: float        # C36
    trator_fixos_h: float         # O5
    # SEMEADORA
    semeadera_depreciacao_h: float # F12
    semeadora_juros_h: float       # F20
    semeadora_seguro_h: float      # F28
    semeadora_abrigo_h: float      # F36
    semeadora_fixos_h: float       # O10
    # CONJUNTO
    conjunto_fixos_h: float        # O15


@dataclass
class VariaveisOut:
    # TRATOR
    trator_diesel_h: float         # I9
    trator_reparos_h: float        # I19
    trator_lfa_total_h: float      # I33 (Lub+Adt+Filtros)
    trator_pneus_h: float          # I42
    trator_variaveis_h: float      # O6
    # SEMEADORA
    sem_diesel_h: float            # L9
    sem_reparos_h: float           # L19
    sem_lfa_total_h: float         # L33
    sem_pneus_h: float             # L42
    sem_variaveis_h: float         # O11
    # CONJUNTO
    conjunto_variaveis_h: float    # O16


@dataclass
class TotaisOut:
    total_hora_maquina: float      # O17


# ========================
# Bloco: FIXOS
# ========================
def _vida_util_horas(horas_ano: float, anos_uso: float) -> float:
    return horas_ano * anos_uso

def _depreciacao_por_hora(valor_aquisicao: float, valor_sucata: float, vida_util_horas: float) -> float:
    return (valor_aquisicao - valor_sucata) / vida_util_horas if vida_util_horas else float("inf")

def _juros_por_hora(valor_aquisicao: float, taxa_juros: float, horas_ano: float, anos_uso: float) -> float:
    # ((Valor Aquisição/2) * taxa) / horas_ano
    return ((valor_aquisicao / 2.0) * taxa_juros) / horas_ano if horas_ano else float("inf")

def _seguro_por_hora(valor_aquisicao: float, taxa_seguro: float, horas_ano: float) -> float:
    return (valor_aquisicao * taxa_seguro) / horas_ano if horas_ano else float("inf")

def _abrigo_por_hora(valor_aquisicao: float, taxa_abrigo: float, horas_ano: float) -> float:
    return (valor_aquisicao * taxa_abrigo) / horas_ano if horas_ano else float("inf")

def calc_fixos(inputs: FixosInputs) -> FixosOut:
    # TRATOR
    vida_trator = _vida_util_horas(inputs.trator_horas_ano, inputs.trator_anos_uso)   # C11
    trator_depr = _depreciacao_por_hora(inputs.trator_valor_aquisicao, inputs.trator_valor_sucata, vida_trator)  # C12
    trator_juros = _juros_por_hora(inputs.trator_valor_aquisicao, inputs.trator_taxa_juros, inputs.trator_horas_ano, inputs.trator_anos_uso)  # C20 pattern
    trator_seguro = _seguro_por_hora(inputs.trator_valor_aquisicao, inputs.trator_seguro_taxa, inputs.trator_horas_ano)  # C28 pattern
    trator_abrigo = _abrigo_por_hora(inputs.trator_valor_aquisicao, inputs.trator_abrigo_taxa, inputs.trator_horas_ano)  # C36 pattern
    # SEMEADORA
    vida_sem = _vida_util_horas(inputs.semeadora_horas_ano, inputs.semeadora_anos_uso)  # F11
    sem_depr = _depreciacao_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_valor_sucata, vida_sem)  # F12
    sem_juros = _juros_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_taxa_juros, inputs.semeadora_horas_ano, inputs.semeadora_anos_uso)  # F20
    sem_seguro = _seguro_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_seguro_taxa, inputs.semeadora_horas_ano)  # F28
    sem_abrigo = _abrigo_por_hora(inputs.semeadora_valor_aquisicao, inputs.semeadora_abrigo_taxa, inputs.semeadora_horas_ano)  # F36

    # FIXOS por hora (planilha)
    # F42: mão de obra por hora = (C42 * 2.8) / 240 -> aqui já fornecida como mao_obra_hora
    trator_fixos_h = trator_depr + trator_juros + trator_seguro + trator_abrigo + inputs.mao_obra_hora  # O5
    sem_fixos_h = sem_depr + sem_juros + sem_seguro + sem_abrigo                                        # O10
    conjunto_fixos_h = trator_fixos_h + sem_fixos_h                                                      # O15

    return FixosOut(
        trator_depreciacao_h=trator_depr,
        trator_juros_h=trator_juros,
        trator_seguro_h=trator_seguro,
        trator_abrigo_h=trator_abrigo,
        trator_fixos_h=trator_fixos_h,
        semeadera_depreciacao_h=sem_depr,
        semeadora_juros_h=sem_juros,
        semeadora_seguro_h=sem_seguro,
        semeadora_abrigo_h=sem_abrigo,
        semeadora_fixos_h=sem_fixos_h,
        conjunto_fixos_h=conjunto_fixos_h
    )


# ========================
# Bloco: VARIÁVEIS
# ========================
def _diesel_por_hora(consumo_l_h: float, preco_litro: float) -> float:
    return consumo_l_h * preco_litro

def _reparos_por_hora(valor_aquisicao: float, fator_reparo: float, horas_ano: float, anos_uso: float) -> float:
    vida = horas_ano * anos_uso
    total_reparo = valor_aquisicao * fator_reparo  # I16 (0.65) / L16 (0.3)
    return total_reparo / vida if vida else float("inf")

def _lfa_por_hora(valor_aquisicao: float, valor_filtros_ano: float, horas_ano: float, anos_uso: float,
                  fator_lub: float, fator_aditivo: float) -> float:
    vida = horas_ano * anos_uso                # I29 / L29
    lub = (valor_aquisicao * fator_lub) / vida if vida else float("inf")     # I30 / L30
    adt = (valor_aquisicao * fator_aditivo) / vida if vida else float("inf") # I31 / L31, com base em I26/L26
    # Na planilha, aditivos = (valor_aquisicao * 0.015)/vida (trator) e 0.005 (semeadora)
    # Mas há também filtros: (valor_filtros_ano * anos_uso) / vida
    filtros = (valor_filtros_ano * anos_uso) / vida if vida else float("inf")  # I32 / L32
    return lub + adt + filtros

def _pneus_por_hora(valor_aquisicao: float, horas_ano: float, anos_uso: float, fator: float) -> float:
    vida = horas_ano * anos_uso   # I41/L41
    return (valor_aquisicao * fator) / vida if vida else float("inf")

def calc_variaveis(inputs: VariaveisInputs) -> VariaveisOut:
    # TRATOR
    trator_diesel = _diesel_por_hora(inputs.trator_consumo_h, inputs.trator_preco_litro)  # I9
    trator_reparos = _reparos_por_hora(inputs.trator_valor_aquisicao_rep, 0.65, inputs.trator_horas_ano_rep, inputs.trator_anos_uso_rep)  # I19
    trator_lfa = _lfa_por_hora(inputs.trator_valor_aquisicao_lfa, inputs.trator_valor_filtros_ano,
                               inputs.trator_horas_ano_lfa, inputs.trator_anos_uso_lfa,
                               fator_lub=0.10, fator_aditivo=0.015)  # I33
    trator_pneus = _pneus_por_hora(inputs.trator_valor_aquisicao_pneu, inputs.trator_horas_ano_pneu, inputs.trator_anos_uso_pneu, fator=0.15)  # I42
    trator_variaveis_h = trator_diesel + trator_reparos + trator_lfa + trator_pneus  # O6

    # SEMEADORA
    sem_diesel = _diesel_por_hora(inputs.semeadora_consumo_h, inputs.semeadora_preco_litro)  # L9 (normalmente 0)
    sem_reparos = _reparos_por_hora(inputs.sem_valor_aquisicao_rep, 0.30, inputs.sem_horas_ano_rep, inputs.sem_anos_uso_rep)  # L19
    # L32 = 0 fixo na planilha, então filtros_sem = 0; para manter 1:1, passamos valor_filtros_ano=0
    sem_lfa = _lfa_por_hora(inputs.sem_valor_aquisicao_lfa, 0.0,
                            inputs.sem_horas_ano_lfa, inputs.sem_anos_uso_lfa,
                            fator_lub=0.03, fator_aditivo=0.005)  # L33
    sem_pneus = _pneus_por_hora(inputs.sem_valor_aquisicao_pneu, inputs.sem_horas_ano_pneu, inputs.sem_anos_uso_pneu, fator=0.02)  # L42
    sem_variaveis_h = sem_diesel + sem_reparos + sem_lfa + sem_pneus  # O11

    conjunto_variaveis_h = trator_variaveis_h + sem_variaveis_h  # O16

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


# ========================
# Bloco: TOTAl (Hora Máquina)
# ========================
@dataclass
class Totais:
    fixos: FixosOut
    variaveis: VariaveisOut
    total: TotaisOut

    def asdict(self) -> Dict:
        return {
            "fixos": asdict(self.fixos),
            "variaveis": asdict(self.variaveis),
            "total": asdict(self.total),
        }

def calcular_tudo_custos(fixos: FixosInputs, variaveis: VariaveisInputs) -> Totais:
    fx = calc_fixos(fixos)
    var = calc_variaveis(variaveis)
    total_h = fx.conjunto_fixos_h + var.conjunto_variaveis_h  # O17
    return Totais(fixos=fx, variaveis=var, total=TotaisOut(total_hora_maquina=total_h))


# ========================
# ESTIMATIVAS (aba "estimativas")
# ========================
@dataclass
class EstimativasInputs:
    # DADOS USADOS (C5..C9 etc)
    trator_cv: float              # C5
    semeadora_linhas: float       # C6
    area_ha: float                # C7
    cce_ha_h: float               # C8
    trator_consumo_h: float       # C9 (L/h)

    preco_diesel: float = 6.0     # I8/L8 na planilha (teste)
    taxa_seguro: float = 0.02     # C22/F22 (estimativas)
    taxa_abrigo: float = 0.01     # C23/F23 (estimativas)
    taxa_juros: float = 0.06      # padrão utilizado na aba fixos (pode ajustar)
    mao_obra_salario_min: float = 3000.0  # C42 (fixos)
    fator_salario_por_h: float = 2.8      # F42 numerador
    horas_mes: float = 240.0              # F42 denominador

@dataclass
class EstimativasOut:
    # Valores estimados para alimentar as funções de cálculo
    fixos_inputs: FixosInputs
    variaveis_inputs: VariaveisInputs

def estimar_parametros(inputs: EstimativasInputs) -> EstimativasOut:
    # FIXOS estimados (TRATOR e SEMEADORA)
    # Valores iniciais (C15/F15)
    tr_val_ini = inputs.trator_cv * 3000.0
    sem_val_ini = inputs.semeadora_linhas * 20000.0
    # Sucata (C16/F16)
    tr_suc = tr_val_ini * 0.30
    sem_suc = sem_val_ini * 0.40
    # Anos (C17/F17)
    tr_anos = 10.0
    sem_anos = 10.0
    # Horas/ano (C18/F18)
    tr_horas_ano = inputs.area_ha * 10.0
    sem_horas_ano = inputs.cce_ha_h * inputs.area_ha
    # Mão de obra (F42): (C42 * 2.8) / 240
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

    # VARIÁVEIS estimadas
    # Diesel/h (C26/F26) + preço (I8/L8)
    tr_diesel_l_h = 6.0
    sem_diesel_l_h = 0.0
    preco = inputs.preco_diesel

    # Reparos (I16/L16) via fatores (0.65 trator; 0.3 semeadora) — valores baseados nos valores iniciais acima
    # Horas/ano (I14/L14) e anos (I17/L17)
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
        trator_valor_filtros_ano=800.0,  # I25 (valor de teste, a planilha usa 800)
        trator_horas_ano_lfa=tr_horas_ano,
        trator_anos_uso_lfa=tr_anos,
        sem_valor_aquisicao_lfa=sem_val_ini,
        sem_valor_filtros_ano=0.0,       # L25 = 0 na planilha
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


# ========================
# Exemplos de uso (teste rápido)
# ========================
if __name__ == "__main__":
    # Exemplo com ESTIMATIVAS padrão (igual à planilha)
    est_in = EstimativasInputs(
        trator_cv=80,
        semeadora_linhas=5,
        area_ha=40,
        cce_ha_h=1.3,
        trator_consumo_h=8.8,
        preco_diesel=6.0
    )
    est = estimar_parametros(est_in)
    totais = calcular_tudo_custos(est.fixos_inputs, est.variaveis_inputs)
    print(totais.asdict())
