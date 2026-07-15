# -*- coding: utf-8 -*-
"""
Created on Wed Jul  1 11:18:08 2026

@author: Restart
"""

# =============================================================================
# metriques.py — Calcul des métriques blink et conversion en scores /100
# =============================================================================
# Prend en entrée le dict retourné par detection.analyser_source()
# et calcule les 4 métriques + leur score /100.
#
# Fonctions :
#   1. calculer_br(clignements, fps, n_frames)   → Blink Rate (blinks/min)
#   2. calculer_bd(clignements, fps)              → Blink Duration (ms)
#   3. calculer_brv(clignements, fps, n_frames)   → Blink Rate Variability (CV%)
#   4. calculer_ear_moyen(signal_ear)             → EAR moyen baseline
#   5. score_br / score_bd / score_brv / score_ear → conversion /100
#   6. calculer_score_blink(...)                  → score final pondéré /100
#   7. calculer_metriques(detection_dict)         → pipeline complet
# =============================================================================

import numpy as np
import config


# ── 1. Blink Rate ─────────────────────────────────────────────────────────────

def calculer_br(clignements: list, fps: float, n_frames: int) -> float:
    """
    Calcule le Blink Rate moyen (blinks/min) sur toute la durée de mesure.

    Formule :
        BR = (nombre de clignements / durée totale en secondes) × 60

    Paramètres
    ----------
    clignements : list[dict]
        Liste des clignements issus de detection.analyser_source().
    fps : float
        Fréquence d'échantillonnage.
    n_frames : int
        Nombre total de frames analysées.

    Retourne
    --------
    float
        Blink Rate en blinks/min. np.nan si durée nulle.
    """
    duree_sec = n_frames / fps
    if duree_sec < 1.0:
        return np.nan

    br = (len(clignements) / duree_sec) * 60.0

    print(f"[INFO] Blink Rate (BR)      : {br:.1f} blinks/min "
          f"({len(clignements)} blinks sur {duree_sec:.1f}s)")
    return br


# ── 2. Blink Duration ─────────────────────────────────────────────────────────

def calculer_bd(clignements: list, fps: float) -> tuple[float, float]:
    """
    Calcule la durée moyenne et l'écart-type des clignements (en ms).

    Formule :
        BD = (duree_frames / fps) × 1000  → en millisecondes

    Un clignement normal dure 100–200ms.
    Au-delà de 300ms → signe de fatigue oculaire.

    Paramètres
    ----------
    clignements : list[dict]
        Liste des clignements (chaque dict contient "duree_frames").
    fps : float

    Retourne
    --------
    bd_moyenne : float
        Durée moyenne des clignements en ms. np.nan si aucun clignement.
    bd_std : float
        Écart-type de la durée en ms.
    """
    if len(clignements) == 0:
        return np.nan, np.nan

    durees_ms = np.array([b["duree_frames"] / fps * 1000.0 for b in clignements])

    bd_moyenne = float(np.mean(durees_ms))
    bd_std     = float(np.std(durees_ms))

    print(f"[INFO] Blink Duration (BD)  : {bd_moyenne:.1f} ± {bd_std:.1f} ms")
    return bd_moyenne, bd_std


# ── 3. Blink Rate Variability ─────────────────────────────────────────────────

def calculer_brv(clignements: list, fps: float, n_frames: int) -> float:
    """
    Calcule la variabilité du Blink Rate (BRV) via le coefficient de variation.

    Principe :
    - On découpe la mesure en fenêtres de FENETRE_BR_SEC secondes
    - On calcule le BR dans chaque fenêtre
    - BRV = std(BR_fenêtres) / mean(BR_fenêtres) × 100   [en %]

    Un CV faible → rythme de clignement régulier → état calme
    Un CV élevé  → rythme irrégulier → stress, instabilité

    Paramètres
    ----------
    clignements : list[dict]
        Liste des clignements.
    fps : float
    n_frames : int
        Nombre total de frames.

    Retourne
    --------
    float
        Coefficient de variation en %. np.nan si pas assez de fenêtres.
    """
    taille_fenetre_frames = int(config.FENETRE_BR_SEC * fps)
    if taille_fenetre_frames == 0 or n_frames < taille_fenetre_frames * 2:
        print("[AVERTISSEMENT] BRV : signal trop court pour calculer la variabilité.")
        return np.nan

    # BR par fenêtre
    br_fenetres = []
    for debut in range(0, n_frames - taille_fenetre_frames, taille_fenetre_frames // 2):
        fin = debut + taille_fenetre_frames
        n_blinks_fenetre = sum(
            1 for b in clignements
            if debut <= b["frame_debut"] < fin
        )
        br_fenetre = (n_blinks_fenetre / config.FENETRE_BR_SEC) * 60.0
        br_fenetres.append(br_fenetre)

    if len(br_fenetres) < 2:
        return np.nan

    br_fenetres = np.array(br_fenetres)
    moyenne = np.mean(br_fenetres)
    if moyenne < 1e-6:
        return np.nan

    cv = (np.std(br_fenetres) / moyenne) * 100.0

    print(f"[INFO] BRV (CV%)            : {cv:.1f}%  "
          f"({len(br_fenetres)} fenêtres de {config.FENETRE_BR_SEC:.0f}s)")
    return float(cv)


# ── 4. EAR moyen baseline ─────────────────────────────────────────────────────

def calculer_ear_baseline(signal_ear: np.ndarray) -> float:
    """
    Calcule l'EAR moyen en excluant les clignements (frames sous le seuil).

    On ne veut pas la moyenne brute (qui inclurait les clignements → trop bas),
    mais la baseline de l'œil ouvert entre les clignements.

    Paramètres
    ----------
    signal_ear : np.ndarray
        Signal EAR frame par frame issu de detection.analyser_source().

    Retourne
    --------
    float
        EAR baseline (œil ouvert). np.nan si signal vide.
    """
    if len(signal_ear) == 0:
        return np.nan

    # On garde uniquement les frames où l'œil est ouvert
    masque_ouvert = signal_ear >= config.EAR_SEUIL
    ear_ouvert    = signal_ear[masque_ouvert]

    if len(ear_ouvert) == 0:
        return np.nan

    ear_baseline = float(np.mean(ear_ouvert))
    print(f"[INFO] EAR baseline          : {ear_baseline:.4f} "
          f"({masque_ouvert.sum()} frames œil ouvert / {len(signal_ear)} total)")
    return ear_baseline


# ── 5. Conversion en scores /100 ──────────────────────────────────────────────

def _score_gaussien(valeur: float, optimal: float, ecart_mauvais: float) -> float:
    """
    Convertit une valeur en score /100 via une courbe gaussienne centrée sur l'optimal.

    Score = 100 × exp( -0.5 × ((valeur - optimal) / ecart_mauvais)² )

    Plus la valeur s'éloigne de l'optimal, plus le score baisse.

    Paramètres
    ----------
    valeur : float
    optimal : float
        Valeur idéale → score 100.
    ecart_mauvais : float
        Écart à l'optimal qui donne un score d'environ 60.

    Retourne
    --------
    float
        Score entre 0 et 100.
    """
    if np.isnan(valeur):
        return np.nan
    score = 100.0 * np.exp(-0.5 * ((valeur - optimal) / ecart_mauvais) ** 2)
    return float(np.clip(score, 0, 100))


def _score_lineaire_inverse(valeur: float, bon: float, mauvais: float) -> float:
    """
    Convertit une valeur en score /100 via interpolation linéaire inverse.

    valeur = bon    → score 100
    valeur = mauvais → score 0
    (utilisé pour BRV : plus c'est élevé, plus c'est mauvais)

    Paramètres
    ----------
    valeur : float
    bon : float
        Valeur associée au score 100.
    mauvais : float
        Valeur associée au score 0.

    Retourne
    --------
    float
        Score entre 0 et 100.
    """
    if np.isnan(valeur):
        return np.nan
    score = 100.0 * (mauvais - valeur) / (mauvais - bon)
    return float(np.clip(score, 0, 100))


def score_br(br: float) -> float:
    """
    Convertit le Blink Rate en score /100.

    Optimal : BR_OPTIMAL (15 blinks/min)
    Score gaussien : s'éloigner dans les deux sens fait baisser le score.

    Paramètres
    ----------
    br : float
        Blink Rate en blinks/min.

    Retourne
    --------
    float
        Score /100.
    """
    return _score_gaussien(br, config.BR_OPTIMAL, ecart_mauvais=8.0)


def score_bd(bd: float) -> float:
    """
    Convertit la Blink Duration en score /100.

    Optimal : BD_OPTIMAL (150ms)
    Score gaussien : trop court (hypervigilance) ou trop long (fatigue) → score bas.

    Paramètres
    ----------
    bd : float
        Blink Duration moyenne en ms.

    Retourne
    --------
    float
        Score /100.
    """
    return _score_gaussien(bd, config.BD_OPTIMAL, ecart_mauvais=80.0)


def score_brv(brv: float) -> float:
    """
    Convertit la BRV (CV%) en score /100.

    Relation inverse : CV faible → bon score, CV élevé → mauvais score.

    Paramètres
    ----------
    brv : float
        Coefficient de variation en %.

    Retourne
    --------
    float
        Score /100.
    """
    return _score_lineaire_inverse(brv, bon=config.BRV_BON, mauvais=config.BRV_MAUVAIS)


def score_ear(ear: float) -> float:
    """
    Convertit l'EAR baseline en score /100.

    Optimal : EAR_OPTIMAL (0.28)
    Score gaussien : trop bas (fatigue) ou trop haut (hypervigilance) → score bas.

    Paramètres
    ----------
    ear : float
        EAR baseline (œil ouvert).

    Retourne
    --------
    float
        Score /100.
    """
    return _score_gaussien(ear, config.EAR_OPTIMAL, ecart_mauvais=0.06)


# ── 6. Score blink global ─────────────────────────────────────────────────────

def calculer_score_blink(s_br: float, s_bd: float,
                          s_brv: float, s_ear: float) -> float:
    """
    Calcule le score blink global pondéré /100.

    Formule :
        score = (w_br×s_br + w_bd×s_bd + w_brv×s_brv + w_ear×s_ear)
                / (w_br + w_bd + w_brv + w_ear)

    Les pondérations sont définies dans config.py.
    Si une métrique est nan (données insuffisantes), elle est exclue
    et les autres sont renormalisées.

    Paramètres
    ----------
    s_br, s_bd, s_brv, s_ear : float
        Scores /100 de chaque métrique.

    Retourne
    --------
    float
        Score blink global /100. np.nan si toutes les métriques sont nan.
    """
    composantes = [
        (s_br,  config.POIDS_BR),
        (s_bd,  config.POIDS_BD),
        (s_brv, config.POIDS_BRV),
        (s_ear, config.POIDS_EAR),
    ]

    # Exclure les nan
    valides = [(s, w) for s, w in composantes if not np.isnan(s)]

    if len(valides) == 0:
        return np.nan

    somme_ponderee = sum(s * w for s, w in valides)
    somme_poids    = sum(w for _, w in valides)

    return float(somme_ponderee / somme_poids)


# ── 7. Pipeline complet ───────────────────────────────────────────────────────

def calculer_metriques(detection: dict) -> dict:
    """
    Pipeline complet : détection → métriques → scores → score_blink.

    Fonction principale à appeler depuis run.py après detection.analyser_source().

    Paramètres
    ----------
    detection : dict
        Dict retourné par detection.analyser_source().

    Retourne
    --------
    dict avec les clés :
        br          : float  — Blink Rate (blinks/min)
        bd          : float  — Blink Duration moyenne (ms)
        bd_std      : float  — Écart-type BD (ms)
        brv         : float  — BRV coefficient de variation (%)
        ear_baseline: float  — EAR moyen œil ouvert
        score_br    : float  — Score BR /100
        score_bd    : float  — Score BD /100
        score_brv   : float  — Score BRV /100
        score_ear   : float  — Score EAR /100
        score_blink : float  — Score blink global /100
        n_blinks    : int    — Nombre total de clignements
        valide      : bool   — True si mesure fiable
    """
    print("\n── Calcul des métriques ──────────────────────────────────────────")

    signal_ear  = detection["signal_ear"]
    clignements = detection["clignements"]
    fps         = detection["fps"]
    n_frames    = detection["n_frames_total"]
    valide      = detection["valide"]

    # Métriques brutes
    br               = calculer_br(clignements, fps, n_frames)
    bd, bd_std       = calculer_bd(clignements, fps)
    brv              = calculer_brv(clignements, fps, n_frames)
    ear_baseline     = calculer_ear_baseline(signal_ear)

    # Scores /100
    s_br  = score_br(br)
    s_bd  = score_bd(bd)
    s_brv = score_brv(brv)
    s_ear = score_ear(ear_baseline)

    score = calculer_score_blink(s_br, s_bd, s_brv, s_ear)

    print(f"\n  Score BR   : {s_br:.1f}/100")
    print(f"  Score BD   : {s_bd:.1f}/100")
    print(f"  Score BRV  : {s_brv:.1f}/100")
    print(f"  Score EAR  : {s_ear:.1f}/100")
    print(f"  ──────────────────────")
    print(f"  Score Blink: {score:.1f}/100")
    print("─────────────────────────────────────────────────────────────────\n")

    return {
        "br"          : br,
        "bd"          : bd,
        "bd_std"      : bd_std,
        "brv"         : brv,
        "ear_baseline": ear_baseline,
        "score_br"    : s_br,
        "score_bd"    : s_bd,
        "score_brv"   : s_brv,
        "score_ear"   : s_ear,
        "score_blink" : score,
        "n_blinks"    : len(clignements),
        "valide"      : valide,
    }