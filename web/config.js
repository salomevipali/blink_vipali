// =============================================================================
// config.js — Paramètres globaux (port de config.py)
// =============================================================================
// Tous les réglages sont centralisés ici. Ne rien mettre en dur ailleurs.
// =============================================================================

export const CONFIG = {
  // ── Détection EAR ────────────────────────────────────────────────────────
  EAR_SEUIL: 0.18,
  EAR_FRAMES_CONSECUTIVES: 2,

  // Indices MediaPipe FaceMesh (identiques à la version Python)
  LANDMARKS_OEIL_GAUCHE: [362, 385, 387, 263, 373, 380],
  LANDMARKS_OEIL_DROIT: [33, 160, 158, 133, 153, 144],
  MOYENNE_DEUX_YEUX: true,

  // ── Métriques ────────────────────────────────────────────────────────────
  FENETRE_BR_SEC: 30.0,

  BR_OPTIMAL: 15.0,
  BR_MIN: 5.0,
  BR_MAX: 30.0,

  BD_OPTIMAL: 150.0,
  BD_MIN: 80.0,
  BD_MAX: 350.0,

  BRV_BON: 25.0,
  BRV_MAUVAIS: 60.0,

  EAR_OPTIMAL: 0.28,
  EAR_MIN: 0.18,
  EAR_MAX: 0.38,

  POIDS_BR: 0.30,
  POIDS_BD: 0.25,
  POIDS_BRV: 0.25,
  POIDS_EAR: 0.20,

  // ── Qualité signal ───────────────────────────────────────────────────────
  DETECTION_RATE_MIN: 0.80,
  N_BLINKS_MIN: 5,

  // ── Affichage EAR max pour les jauges (borne haute visuelle) ────────────
  EAR_JAUGE_MAX: 0.40,

  // ── Couleurs ─────────────────────────────────────────────────────────────
  COULEUR_EAR: "#4A90D9",
  COULEUR_BLINKS: "#F39C12",
  COULEUR_SEUIL: "#E05C5C",
  COULEUR_BR: "#5CB85C",
};
