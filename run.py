# -*- coding: utf-8 -*-
"""
Created on Wed Jul  1 11:26:40 2026

@author: Restart
"""

# -*- coding: utf-8 -*-
"""
Created on Wed Jul  1 11:26:40 2026

@author: Restart
"""

# =============================================================================
# run.py — Lanceur Spyder / console IPython
# =============================================================================
# Lance directement depuis la console Spyder :
#   runfile('C:/chemin/vers/blink_vipali/run.py')
# =============================================================================

import calibration
import detection
import metriques
import visualisation

# ── Choix du mode ─────────────────────────────────────────────────────────────

MODE   = "camera"                        # "video" ou "camera"
VIDEO  = r"C:\chemin\vers\video.mp4"    # ignoré si MODE = "camera"
DUREE  = 90.0                            # secondes, ignoré si MODE = "video"

CALIBRER = True                          # False pour sauter la calibration
                                          # et garder config.EAR_SEUIL tel quel

# ── 0. Calibration (yeux ouverts / yeux fermés) ───────────────────────────────
# N'a de sens qu'en caméra live (on demande d'ouvrir/fermer les yeux) —
# ignorée automatiquement en mode "video".

if CALIBRER and MODE == "camera":
    resultat_calibration = calibration.calibrer(source=0)
    calibration.appliquer_calibration(resultat_calibration)
elif CALIBRER and MODE == "video":
    print("[INFO] Calibration ignorée en mode 'video' (seuil par défaut conservé).")

# ── 1. Détection ──────────────────────────────────────────────────────────────

if MODE == "video":
    resultats_detection = detection.analyser_source(
        source=VIDEO,
        afficher_preview=True,
        duree_totale=None,       # durée lue depuis la vidéo
    )
else:
    resultats_detection = detection.analyser_source(
        source=0,                # caméra frontale
        afficher_preview=True,
        duree_totale=DUREE,
    )

# ── 2. Métriques ──────────────────────────────────────────────────────────────

resultats_metriques = metriques.calculer_metriques(resultats_detection)

# ── 3. Rapport post-capture ───────────────────────────────────────────────────

visualisation.afficher_rapport(
    signal_ear  = resultats_detection["signal_ear"],
    clignements = resultats_detection["clignements"],
    metriques   = resultats_metriques,
    fps         = resultats_detection["fps"],
    sauvegarder = True,
    afficher    = True,
)