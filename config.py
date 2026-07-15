# -*- coding: utf-8 -*-
"""
Created on Wed Jul  1 11:11:10 2026

@author: Restart
"""

# =============================================================================
# config.py — Paramètres globaux du module Blink VIPALI
# =============================================================================
# Tous les réglages sont centralisés ici.
# Ne jamais mettre de valeurs "en dur" dans les autres modules.
# =============================================================================


# ── Acquisition ───────────────────────────────────────────────────────────────

# Index caméra (0 = caméra frontale par défaut)
CAMERA_INDEX = 0

# FPS fallback si non détecté automatiquement
FPS_FALLBACK = 30.0

# Durée minimale de mesure (secondes)
DUREE_MIN_SEC = 30.0

# Durée recommandée (secondes)
DUREE_RECOMMANDEE_SEC = 90.0


# ── Détection EAR ─────────────────────────────────────────────────────────────

# Seuil EAR en dessous duquel un clignement est détecté
# Valeur classique issue de la littérature (Soukupova & Cech, 2016)
EAR_SEUIL = 0.18

# Nombre de frames consécutives sous le seuil pour valider un clignement
# Évite les faux positifs sur un seul frame bruité
EAR_FRAMES_CONSECUTIVES = 2

# Indices MediaPipe FaceMesh pour les deux yeux (landmarks 468 points)
# Source : https://developers.google.com/mediapipe/solutions/vision/face_landmarker
# Ordre : [coin_gauche, haut_gauche, haut_droit, coin_droit, bas_droit, bas_gauche]
LANDMARKS_OEIL_GAUCHE = [362, 385, 387, 263, 373, 380]
LANDMARKS_OEIL_DROIT  = [33,  160, 158, 133, 153, 144]

# On moyenne les deux yeux pour plus de robustesse
MOYENNE_DEUX_YEUX = True


# ── Métriques ─────────────────────────────────────────────────────────────────

# Taille de la fenêtre glissante pour le calcul du Blink Rate (secondes)
FENETRE_BR_SEC = 30.0

# Plages normatives pour conversion en score /100
# (min, max) → score 0 à 100 via interpolation
# Basé sur Doughty 2001 + Maffei & Angrilli 2018

# Blink Rate (blinks/min) — optimum autour de 15
BR_OPTIMAL    = 15.0
BR_MIN        = 5.0    # en dessous → concentration extrême ou fatigue
BR_MAX        = 30.0   # au dessus  → stress/anxiété

# Blink Duration (ms) — optimum autour de 150ms
BD_OPTIMAL    = 150.0
BD_MIN        = 80.0   # très court → alerte maximale
BD_MAX        = 350.0  # très long  → fatigue / somnolence

# Blink Rate Variability — CV % (coefficient de variation)
# Bas = régulier = bon ; élevé = irrégulier = stress
BRV_BON       = 25.0   # CV% → score 100
BRV_MAUVAIS   = 60.0   # CV% → score 0

# EAR moyen — optimum autour de 0.28
EAR_OPTIMAL   = 0.28
EAR_MIN       = 0.18   # mi-clos chronique → fatigue
EAR_MAX       = 0.38   # très ouvert → hypervigilance

# Pondérations des 4 métriques dans le score_blink
# Somme = 1.0
POIDS_BR      = 0.30
POIDS_BD      = 0.25
POIDS_BRV     = 0.25
POIDS_EAR     = 0.20


# ── Fusion ────────────────────────────────────────────────────────────────────

# Pondération fusion blink + NeuroQuest → score cognitif final
POIDS_BLINK       = 0.40
POIDS_NEUROQUEST  = 0.60


# ── Qualité signal ────────────────────────────────────────────────────────────

# Ratio de frames avec landmarks détectés pour valider la mesure
DETECTION_RATE_MIN = 0.80   # < 80% de frames détectées → mesure rejetée

# Nombre minimum de clignements pour calculer les métriques
N_BLINKS_MIN = 5


# ── Visualisation ─────────────────────────────────────────────────────────────

COULEUR_EAR      = "#4A90D9"   # bleu
COULEUR_BLINKS   = "#F39C12"   # orange
COULEUR_SEUIL    = "#E05C5C"   # rouge
COULEUR_BR       = "#5CB85C"   # vert
COULEUR_FOND     = "#F4F6F8"   # gris clair

FIGURE_DPI    = 150
FIGURE_OUTPUT = "blink_result.png"