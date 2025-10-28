from dataclasses import dataclass
from enum import Enum
from typing import Dict

class Preparo(Enum):
    CONVENCIONAL = "CONVENCIONAL"
    PLANTIO_DIRETO = "PLANTIO_DIRETO"


class Solo(Enum):
    ARENOSO = "ARENOSO"
    MEDIO = "MEDIO"
    ARGILOSO = "ARGILOSO"


class Tracao(Enum):
    QUATRO_X_DOIS = "4X2"
    QUATRO_X_DOIS_TDA = "4X2_TDA"
    QUATRO_X_QUATRO = "4X4"
    ESTEIRA = "ESTEIRA"


class Superficie(Enum):
    FIRME = "FIRME"
    MEDIA = "MEDIA"
    SOLTA = "SOLTA"


class Sulcador(Enum):
    DISCOS = "DISCOS"   # equivalente a "Discos Duplos"
    FACAO = "FACAO"


# =========================
# Entradas e Saídas
# =========================

@dataclass(frozen=True)
class Inputs:
    """Entradas do cálculo (espelham as células de entrada da planilha)

    - Preparo do solo           (planilha: C6)   -> Preparo
    - Tipo de solo              (planilha: C7)   -> Solo
    - Aclive (%)                (planilha: C8)   -> aclive_percent
    - Tipo de tra��ǜo           (planilha: C9)   -> tracao
    - Superf��cie de rolamento  (planilha: C9)   -> superficie
    - Sulcador                  (planilha: C10)  -> Sulcador
    - Número de linhas          (planilha: C11)  -> linhas
    - CV do trator disponível   (planilha: C12)  -> cv_trator_disponivel
    - Velocidade (km/h)         (planilha: C18)  -> velocidade_kmh
    """
    preparo: Preparo
    solo: Solo
    tracao: Tracao
    superficie: Superficie
    aclive_percent: float
    sulcador: Sulcador
    linhas: int
    cv_trator_disponivel: float
    velocidade_kmh: float


@dataclass(frozen=True)
class Results:
    """Saídas principais e intermediárias (com as mesmas grandezas da planilha)."""
    ft_N: float                   # Força de tração total (N)
    kw: float                     # Potência no ponto de tração (kW)
    cv_requerido: float           # Potência requerida (cv)
    peso_semeadora_t: float       # Peso estimado da semeadora (t)
    peso_trator_t: float          # Peso estimado do trator (t)
    acrescimo_aclive_N: float     # Acréscimo de força por aclive (N)
    cv_trator_disponivel: float   # Echo da entrada (cv)
    eficiencia_tracao: float      # Fator aplicado conforme tracao/superficie
    cv_tracionavel: float         # CV efetivamente disponivel para tracao
    atende: bool                  # Se o trator disponível atende ao requerido


# =========================
# Constantes da planilha
# =========================

# PROCV(C7, H10:I12, 2, FALSO)
FATOR_SOLO: Dict[Solo, float] = {
    Solo.ARENOSO: 1.00,
    Solo.MEDIO: 0.96,
    Solo.ARGILOSO: 0.92,
}

# PROCV(C10, H17:I18, 2, FALSO)
FORCA_SULCADOR_N_POR_LINHA: Dict[Sulcador, int] = {
    Sulcador.DISCOS: 1900,  # "Discos Duplos"
    Sulcador.FACAO: 3400,
}

EFICIENCIA_TRACAO: Dict[Tracao, Dict[Superficie, float]] = {
    Tracao.QUATRO_X_DOIS: {
        Superficie.FIRME: 0.60,
        Superficie.MEDIA: 0.56,
        Superficie.SOLTA: 0.46,
    },
    Tracao.QUATRO_X_DOIS_TDA: {
        Superficie.FIRME: 0.64,
        Superficie.MEDIA: 0.61,
        Superficie.SOLTA: 0.54,
    },
    Tracao.QUATRO_X_QUATRO: {
        Superficie.FIRME: 0.65,
        Superficie.MEDIA: 0.62,
        Superficie.SOLTA: 0.58,
    },
    Tracao.ESTEIRA: {
        Superficie.FIRME: 0.68,
        Superficie.MEDIA: 0.62,
        Superficie.SOLTA: 0.58,
    },
}

# =========================
# Funções auxiliares (espelham fórmulas)
# =========================

def _validar_inputs(inp: Inputs) -> None:
    """Validações de sanidade das entradas."""
    if inp.linhas < 1:
        raise ValueError("Número de linhas deve ser >= 1.")
    if inp.velocidade_kmh <= 0:
        raise ValueError("Velocidade (km/h) deve ser > 0.")
    if inp.cv_trator_disponivel <= 0:
        raise ValueError("CV do trator disponível deve ser > 0.")
    if not (0 <= inp.aclive_percent <= 100):
        raise ValueError("Aclive (%) deve estar entre 0 e 100.")


def peso_por_linha_kg(linhas: int) -> int:
    """Regra de I27 (planilha):
       - até 8 linhas           → 450 kg/linha
       - de 9 a 15 linhas       → 650 kg/linha
       - acima de 15 linhas     → 850 kg/linha
    """
    if linhas <= 8:
        return 450
    if 9 <= linhas <= 15:
        return 650
    return 850


def calc_peso_semeadora_t(linhas: int) -> float:
    """Equivalente a F7 = (I27 * C11) / 1000 (t)"""
    return (peso_por_linha_kg(linhas) * linhas) / 1000.0


def calc_peso_trator_t(cv_trator: float) -> float:
    """Peso estimado do trator (t) usando 55 kg/cv ate 110 cv, depois 50 kg/cv."""
    fator_kg_por_cv = 55.0 if cv_trator <= 110.0 else 50.0
    return (cv_trator * fator_kg_por_cv) / 1000.0


def calc_acrescimo_aclive_N(aclive_percent: float, peso_semeadora_t: float, peso_trator_t: float) -> float:
    """Equivalente a I7 = (C8 * 90) * (F7 * F8)
       Obs.: F7 e F8 estão em toneladas, a constante é 90 (da planilha).
    """
    return (aclive_percent * 90.0) * (peso_semeadora_t * peso_trator_t)


def calc_ft_N(preparo: Preparo,
              linhas: int,
              solo: Solo,
              sulcador: Sulcador,
              acrescimo_aclive_N: float) -> float:
    """Força de tração total Ft (N).
       - Se Convencional: Ft = (1500 * C11) + I7
       - Se Plantio Direto: Ft = (FATOR_SOLO * FORCA_SULCADOR * C11) + I7
    """
    if preparo == Preparo.CONVENCIONAL:
        return (1500.0 * linhas) + acrescimo_aclive_N
    else:
        fator = FATOR_SOLO[solo]
        forca_linha = FORCA_SULCADOR_N_POR_LINHA[sulcador]
        return (fator * forca_linha * linhas) + acrescimo_aclive_N


def calc_kw(ft_N: float, velocidade_kmh: float) -> float:
    """Potência (kW) na barra:
       kW = (Ft * (Vel/3,6)) / 1000
    """
    return (ft_N * (velocidade_kmh / 3.6)) / 1000.0


def kw_to_cv(kw: float) -> float:
    """Conversão: cv = kW * 1,36"""
    return kw * 1.36


# =========================
# Orquestrador
# =========================

def calcular(inp: Inputs) -> Results:
    """Executa o pipeline com a MESMA ordem e lógica da planilha.

    Passos equivalentes:
      (1) F7: peso semeadora (t) = (I27 * C11) / 1000
      (2) F8: peso trator (t)    = (C12 * 60) / 1000
      (3) I7: acréscimo aclive   = (C8 * 90) * (F7 * F8)
      (4) I14: fator do solo     = PROCV(C7, H10:I12, 2, FALSO) [embutido na calc_ft_N]
      (5) I20: força sulcador    = PROCV(C10, H17:I18, 2, FALSO) [embutido na calc_ft_N]
      (6) Ft (N):
            - Convencional: (1500 * C11) + I7
            - Plantio Direto: (I14 * I20 * C11) + I7
      (7) kW = (Ft * (Vel/3,6)) / 1000
      (8) cv = kW * 1,36
    """
    _validar_inputs(inp)

    peso_sem_t = calc_peso_semeadora_t(inp.linhas)
    peso_trat_t = calc_peso_trator_t(inp.cv_trator_disponivel)
    acrescimo_N = calc_acrescimo_aclive_N(inp.aclive_percent, peso_sem_t, peso_trat_t)
    ft = calc_ft_N(inp.preparo, inp.linhas, inp.solo, inp.sulcador, acrescimo_N)
    kw = calc_kw(ft, inp.velocidade_kmh)
    cv_req = kw_to_cv(kw)
    eficiencia = EFICIENCIA_TRACAO[inp.tracao][inp.superficie]
    cv_tracionavel = inp.cv_trator_disponivel * eficiencia
    atende = cv_tracionavel >= cv_req

    return Results(
        ft_N=ft,
        kw=kw,
        cv_requerido=cv_req,
        peso_semeadora_t=peso_sem_t,
        peso_trator_t=peso_trat_t,
        acrescimo_aclive_N=acrescimo_N,
        cv_trator_disponivel=inp.cv_trator_disponivel,
        eficiencia_tracao=eficiencia,
        cv_tracionavel=cv_tracionavel,
        atende=atende,
    )


# =========================
# Utilidades opcionais
# =========================

def normalizar_preparo(texto: str) -> Preparo:
    """Helper para mapear strings livres ao Enum Preparo."""
    t = (texto or "").strip().upper().replace(" ", "_")
    if t in {"CONVENCIONAL"}:
        return Preparo.CONVENCIONAL
    if t in {"PLANTIO_DIRETO", "PLANTIODIRETO", "DIRETO"}:
        return Preparo.PLANTIO_DIRETO
    raise ValueError(f"Preparo inválido: {texto}")


def normalizar_solo(texto: str) -> Solo:
    t = (texto or "").strip().upper()
    if t in {"ARENOSO"}:
        return Solo.ARENOSO
    if t in {"MEDIO", "MÉDIO"}:
        return Solo.MEDIO
    if t in {"ARGILOSO"}:
        return Solo.ARGILOSO
    raise ValueError(f"Solo inválido: {texto}")


def normalizar_sulcador(texto: str) -> Sulcador:
    t = (texto or "").strip().upper()
    if "DISCO" in t or "BOTINHA" in t:
        return Sulcador.DISCOS
    if "FACAO" in t or "FACÃO" in t:
        return Sulcador.FACAO
    raise ValueError(f"Sulcador inválido: {texto}")


# =========================
# Exemplo rápido (pode remover)
# =========================

if __name__ == "__main__":
    # Exemplo usando os mesmos valores de teste citados no desenho técnico:
    exemplo = Inputs(
        preparo=Preparo.PLANTIO_DIRETO,
        solo=Solo.ARGILOSO,
        tracao=Tracao.QUATRO_X_DOIS_TDA,
        superficie=Superficie.MEDIA,
        aclive_percent=12.0,
        sulcador=Sulcador.FACAO,
        linhas=7,
        cv_trator_disponivel=80.0,
        velocidade_kmh=5.6,
    )
    res = calcular(exemplo)
    print("=== Resultado Exemplo ===")
    print(f"Ft (N): {res.ft_N:,.2f}")
    print(f"kW: {res.kw:,.3f}")
    print(f"cv requerido: {res.cv_requerido:,.2f}")
    print(f"Peso semeadora (t): {res.peso_semeadora_t:,.2f}")
    print(f"Peso trator (t): {res.peso_trator_t:,.2f}")
    print(f"Acrescimo aclive (N): {res.acrescimo_aclive_N:,.2f}")
    print(f"CV disponivel: {res.cv_trator_disponivel:,.2f}")
    print(f"Eficiencia de tracao: {res.eficiencia_tracao:.2f}")
    print(f"CV util para tracao: {res.cv_tracionavel:,.2f}")
    print(f"Atende? {res.atende}")
