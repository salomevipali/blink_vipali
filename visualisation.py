# -*- coding: utf-8 -*-
"""
Created on Wed Jul  1 11:25:20 2026

@author: Restart
"""

# =============================================================================
# visualisation.py — Affichage temps réel + rapport post-capture
# =============================================================================
# Deux modes :
#
#   MODE 1 — Temps réel (pendant la capture)
#   → overlay OpenCV sur la frame caméra
#   → affiche : EAR, BR glissant, compteur blinks, barre de qualité
#   → appelé depuis detection.analyser_source() via un callback
#
#   MODE 2 — Rapport post-capture (après analyse)
#   → figure matplotlib 4 panneaux :
#       ① Signal EAR + seuil + clignements
#       ② Blink Rate (fenêtre glissante)
#       ③ Distribution durées clignements
#       ④ Scores radar /100
#   → sauvegarde PNG + affichage
#
# =============================================================================

import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from collections import deque

import config


# ─────────────────────────────────────────────────────────────────────────────
# MODE 1 — Overlay temps réel
# ─────────────────────────────────────────────────────────────────────────────

class OverlayTempsReel:
    """
    Gère l'affichage des métriques en temps réel sur la frame OpenCV.

    Utilise une fenêtre glissante pour calculer le BR en direct.
    Toutes les métriques sont mises à jour frame par frame.

    Usage :
        overlay = OverlayTempsReel(fps=30)
        ...
        frame_annotee = overlay.update(frame, ear, clignements, t_frame)
        cv2.imshow("Blink VIPALI", frame_annotee)
    """

    def __init__(self, fps: float):
        self.fps = fps
        # Fenêtre glissante EAR pour mini-graphe en temps réel
        taille_fenetre = int(fps * 5)   # 5 secondes d'historique
        self.historique_ear = deque(maxlen=taille_fenetre)
        self.historique_br  = deque(maxlen=10)   # BR des 10 dernières fenêtres

    def _br_glissant(self, clignements: list, t_actuel: float) -> float:
        """Calcule le BR sur la dernière fenêtre de FENETRE_BR_SEC secondes."""
        fenetre = config.FENETRE_BR_SEC
        blinks_recents = [
            b for b in clignements
            if b.get("timestamp_fin", 0) >= t_actuel - fenetre
        ]
        return (len(blinks_recents) / fenetre) * 60.0

    def update(self, frame: np.ndarray, ear: float,
               clignements: list, t_frame: float,
               duree_totale: float) -> np.ndarray:
        """
        Applique l'overlay sur une frame et retourne la frame annotée.

        Paramètres
        ----------
        frame : np.ndarray
            Frame BGR brute de la caméra.
        ear : float
            EAR calculé sur cette frame.
        clignements : list[dict]
            Liste des clignements détectés jusqu'ici.
        t_frame : float
            Temps écoulé depuis le début (secondes).
        duree_totale : float
            Durée totale prévue de la capture (secondes).

        Retourne
        --------
        np.ndarray
            Frame annotée prête pour cv2.imshow().
        """
        self.historique_ear.append(ear)
        frame_out = frame.copy()
        h, w = frame_out.shape[:2]

        # ── Panneau semi-transparent gauche ───────────────────────────────────
        overlay_bg = frame_out.copy()
        cv2.rectangle(overlay_bg, (0, 0), (280, h), (20, 20, 30), -1)
        cv2.addWeighted(overlay_bg, 0.6, frame_out, 0.4, 0, frame_out)

        # ── EAR ───────────────────────────────────────────────────────────────
        couleur_ear = (0, 80, 220) if ear < config.EAR_SEUIL else (80, 220, 80)
        cv2.putText(frame_out, "EAR", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
        cv2.putText(frame_out, f"{ear:.3f}", (10, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, couleur_ear, 2)

        # Barre EAR
        barre_w = 240
        barre_h = 12
        ratio_ear = np.clip(ear / 0.40, 0, 1)
        cv2.rectangle(frame_out, (10, 72), (10 + barre_w, 72 + barre_h),
                      (60, 60, 60), -1)
        cv2.rectangle(frame_out, (10, 72),
                      (10 + int(barre_w * ratio_ear), 72 + barre_h),
                      couleur_ear, -1)
        # Seuil sur la barre
        x_seuil = 10 + int(barre_w * config.EAR_SEUIL / 0.40)
        cv2.line(frame_out, (x_seuil, 70), (x_seuil, 86), (0, 0, 220), 2)

        # ── Séparateur ────────────────────────────────────────────────────────
        cv2.line(frame_out, (10, 96), (260, 96), (80, 80, 80), 1)

        # ── Blink Rate glissant ───────────────────────────────────────────────
        br = self._br_glissant(clignements, t_frame)
        couleur_br = (80, 220, 80)
        if br > config.BR_MAX or br < config.BR_MIN:
            couleur_br = (0, 80, 220)
        cv2.putText(frame_out, "Blink Rate", (10, 118),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        cv2.putText(frame_out, f"{br:.1f} /min", (10, 142),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, couleur_br, 2)

        # ── Compteur clignements ──────────────────────────────────────────────
        cv2.line(frame_out, (10, 155), (260, 155), (80, 80, 80), 1)
        cv2.putText(frame_out, "Blinks", (10, 175),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        cv2.putText(frame_out, str(len(clignements)), (10, 205),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.3, (255, 200, 0), 2)

        # ── Mini-graphe EAR historique ────────────────────────────────────────
        cv2.line(frame_out, (10, 218), (260, 218), (80, 80, 80), 1)
        if len(self.historique_ear) >= 2:
            pts = list(self.historique_ear)
            g_x, g_y, g_w, g_h = 10, 225, 250, 60
            cv2.rectangle(frame_out, (g_x, g_y), (g_x + g_w, g_y + g_h),
                           (40, 40, 50), -1)
            # Ligne seuil
            y_seuil_g = g_y + g_h - int(g_h * config.EAR_SEUIL / 0.40)
            cv2.line(frame_out, (g_x, y_seuil_g), (g_x + g_w, y_seuil_g),
                     (0, 0, 180), 1)
            # Signal EAR
            for i in range(1, len(pts)):
                x1 = g_x + int((i - 1) / (len(pts) - 1) * g_w)
                x2 = g_x + int(i / (len(pts) - 1) * g_w)
                y1 = g_y + g_h - int(np.clip(pts[i-1] / 0.40, 0, 1) * g_h)
                y2 = g_y + g_h - int(np.clip(pts[i]   / 0.40, 0, 1) * g_h)
                cv2.line(frame_out, (x1, y1), (x2, y2), (80, 180, 255), 1)
        cv2.putText(frame_out, "EAR (5s)", (10, 298),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (120, 120, 120), 1)

        # ── Progression temps ─────────────────────────────────────────────────
        cv2.line(frame_out, (10, 308), (260, 308), (80, 80, 80), 1)
        ratio_temps = np.clip(t_frame / duree_totale, 0, 1)
        cv2.rectangle(frame_out, (10, 315), (260, 330), (60, 60, 60), -1)
        couleur_prog = (80, 220, 80) if ratio_temps < 0.8 else (0, 200, 255)
        cv2.rectangle(frame_out, (10, 315),
                      (10 + int(250 * ratio_temps), 330), couleur_prog, -1)
        cv2.putText(frame_out,
                    f"{t_frame:.0f}s / {duree_totale:.0f}s",
                    (10, 346), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        # ── Alerte clignement en cours ────────────────────────────────────────
        if ear < config.EAR_SEUIL:
            cv2.rectangle(frame_out, (w // 2 - 100, h - 55),
                          (w // 2 + 100, h - 15), (0, 0, 180), -1)
            cv2.putText(frame_out, "CLIGNEMENT",
                        (w // 2 - 90, h - 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # ── Instructions ──────────────────────────────────────────────────────
        cv2.putText(frame_out, "'q' pour arreter",
                    (w - 175, h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

        return frame_out


# ─────────────────────────────────────────────────────────────────────────────
# MODE 2 — Rapport post-capture matplotlib
# ─────────────────────────────────────────────────────────────────────────────

def _appliquer_style(ax, titre, xlabel, ylabel):
    ax.set_title(titre, fontsize=9, color='white', loc='left', pad=5,
                 bbox=dict(boxstyle='round,pad=0.3',
                           facecolor=config.COULEUR_EAR, alpha=0.7))
    ax.set_xlabel(xlabel, fontsize=8, color='#444444')
    ax.set_ylabel(ylabel, fontsize=8, color='#444444')
    ax.grid(True, alpha=0.2, linestyle='--')
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=7)


def tracer_ear(ax, signal_ear: np.ndarray, clignements: list, fps: float):
    """① Signal EAR avec seuil et clignements annotés."""
    t = np.arange(len(signal_ear)) / fps

    ax.plot(t, signal_ear, color=config.COULEUR_EAR, lw=0.9, alpha=0.9,
            label="Signal EAR")
    ax.axhline(config.EAR_SEUIL, color=config.COULEUR_SEUIL,
               ls='--', lw=1.5, label=f"Seuil ({config.EAR_SEUIL})")
    ax.fill_between(t, signal_ear, config.EAR_SEUIL,
                    where=(signal_ear < config.EAR_SEUIL),
                    alpha=0.3, color=config.COULEUR_SEUIL, label="Clignements")

    # Triangles sur chaque clignement
    for b in clignements:
        t_blink = (b["frame_debut"] + b["duree_frames"] / 2) / fps
        if t_blink < t[-1]:
            ax.plot(t_blink, config.EAR_SEUIL - 0.015, 'v',
                    color=config.COULEUR_BLINKS, ms=5, zorder=5)

    ax.legend(fontsize=7, loc='upper right')
    _appliquer_style(ax, "① Signal EAR — détection des clignements",
                     "Temps (s)", "EAR")


def tracer_blink_rate(ax, clignements: list, fps: float, n_frames: int):
    """② Blink Rate calculé sur fenêtres glissantes."""
    duree_totale = n_frames / fps
    taille_fen   = config.FENETRE_BR_SEC
    taille_frames = int(taille_fen * fps)

    if taille_frames == 0 or n_frames < taille_frames:
        ax.text(0.5, 0.5, "Signal trop court", ha='center', va='center',
                transform=ax.transAxes, color=config.COULEUR_BR)
        return

    temps_centres = []
    br_valeurs    = []

    for debut in range(0, n_frames - taille_frames, taille_frames // 2):
        fin = debut + taille_frames
        n   = sum(1 for b in clignements if debut <= b["frame_debut"] < fin)
        br  = (n / taille_fen) * 60.0
        temps_centres.append((debut + taille_frames / 2) / fps)
        br_valeurs.append(br)

    ax.bar(temps_centres, br_valeurs, width=taille_fen * 0.4,
           color=config.COULEUR_BR, alpha=0.7, label="BR fenêtre")
    ax.axhline(config.BR_OPTIMAL, color=config.COULEUR_BLINKS,
               ls='--', lw=1.5, label=f"Optimal ({config.BR_OPTIMAL:.0f}/min)")
    ax.axhspan(config.BR_MIN, config.BR_MAX, alpha=0.08,
               color=config.COULEUR_BR, label="Zone normale")

    ax.legend(fontsize=7, loc='upper right')
    _appliquer_style(ax, f"② Blink Rate (fenêtre {taille_fen:.0f}s)",
                     "Temps (s)", "Blinks/min")


def tracer_durees(ax, clignements: list, fps: float):
    """③ Distribution des durées de clignements."""
    if len(clignements) < 3:
        ax.text(0.5, 0.5, "Pas assez de clignements", ha='center', va='center',
                transform=ax.transAxes)
        return

    durees_ms = [b["duree_frames"] / fps * 1000.0 for b in clignements]

    ax.hist(durees_ms, bins=min(15, len(durees_ms)),
            color=config.COULEUR_BLINKS, alpha=0.75, edgecolor='white')
    ax.axvline(np.mean(durees_ms), color=config.COULEUR_SEUIL,
               ls='--', lw=1.5, label=f"Moyenne : {np.mean(durees_ms):.0f}ms")
    ax.axvline(config.BD_OPTIMAL, color=config.COULEUR_BR,
               ls=':', lw=1.5, label=f"Optimal : {config.BD_OPTIMAL:.0f}ms")

    ax.legend(fontsize=7)
    _appliquer_style(ax, "③ Distribution des durées (ms)",
                     "Durée (ms)", "Nombre de blinks")


def tracer_scores(ax, metriques: dict):
    """④ Barres horizontales des scores /100."""
    labels = ["Score BR", "Score BD", "Score BRV", "Score EAR", "Score Global"]
    valeurs = [
        metriques.get("score_br",    0) or 0,
        metriques.get("score_bd",    0) or 0,
        metriques.get("score_brv",   0) or 0,
        metriques.get("score_ear",   0) or 0,
        metriques.get("score_blink", 0) or 0,
    ]
    couleurs = [
        config.COULEUR_EAR,
        config.COULEUR_BLINKS,
        config.COULEUR_BR,
        config.COULEUR_SEUIL,
        config.COULEUR_EAR,
    ]

    bars = ax.barh(labels, valeurs, color=couleurs, alpha=0.75, height=0.5)

    # Zones de référence
    ax.axvspan(0,  35, alpha=0.06, color='red')
    ax.axvspan(35, 65, alpha=0.06, color='orange')
    ax.axvspan(65, 100, alpha=0.06, color='green')

    for bar, val in zip(bars, valeurs):
        if not np.isnan(val):
            ax.text(min(val + 1.5, 97), bar.get_y() + bar.get_height() / 2,
                    f"{val:.0f}", va='center', fontsize=8.5,
                    color='#2C3E50', fontweight='bold')

    ax.set_xlim(0, 105)
    ax.axvline(100, color='#CCCCCC', lw=0.8)
    _appliquer_style(ax, "④ Scores /100", "Score", "")


def afficher_rapport(signal_ear: np.ndarray,
                     clignements: list,
                     metriques: dict,
                     fps: float,
                     sauvegarder: bool = True,
                     afficher: bool = True):
    """
    Génère la figure complète 4 panneaux post-capture.

    Disposition :
    ┌─────────────────────┬─────────────────────┐
    │ ① Signal EAR        │ ② Blink Rate         │
    ├─────────────────────┼─────────────────────┤
    │ ③ Distribution BD   │ ④ Scores /100        │
    └─────────────────────┴─────────────────────┘

    Paramètres
    ----------
    signal_ear : np.ndarray
        Signal EAR frame par frame.
    clignements : list[dict]
        Clignements détectés.
    metriques : dict
        Dict retourné par metriques.calculer_metriques().
    fps : float
    sauvegarder : bool
    afficher : bool
    """
    score      = metriques.get("score_blink", np.nan)
    n_blinks   = metriques.get("n_blinks", 0)
    br         = metriques.get("br", np.nan)
    bd         = metriques.get("bd", np.nan)
    brv        = metriques.get("brv", np.nan)
    ear_bl     = metriques.get("ear_baseline", np.nan)

    # Couleur bandeau selon score
    if np.isnan(score):
        couleur_score = "#7F8C8D"
    elif score >= 70:
        couleur_score = "#27AE60"
    elif score >= 45:
        couleur_score = "#F39C12"
    else:
        couleur_score = "#E74C3C"

    fig = plt.figure(figsize=(14, 9), facecolor='white')
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.32)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    tracer_ear(ax1, signal_ear, clignements, fps)
    tracer_blink_rate(ax2, clignements, fps, len(signal_ear))
    tracer_durees(ax3, clignements, fps)
    tracer_scores(ax4, metriques)

    # Bandeau titre
    titre = (
        f"Blink VIPALI  —  Score : {score:.0f}/100  "
        f"|  Blinks : {n_blinks}  "
        f"|  BR : {br:.1f}/min  "
        f"|  BD : {bd:.0f}ms  "
        f"|  BRV : {brv:.1f}%  "
        f"|  EAR : {ear_bl:.3f}"
    )
    fig.suptitle(titre, fontsize=10, fontweight='bold',
                 color='white', y=0.98,
                 bbox=dict(boxstyle='round,pad=0.4',
                           facecolor=couleur_score, alpha=0.9))

    if sauvegarder:
        fig.savefig(config.FIGURE_OUTPUT, dpi=config.FIGURE_DPI,
                    bbox_inches='tight', facecolor='white')
        print(f"[INFO] Rapport sauvegardé : {config.FIGURE_OUTPUT}")

    if afficher:
        plt.show()

    plt.close(fig)