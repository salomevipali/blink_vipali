# -*- coding: utf-8 -*-
"""

@author: Restart
"""

# =============================================================================
# calibration.py — Calibration du seuil EAR (yeux ouverts / yeux fermés)
# =============================================================================
# Mesure l'EAR moyen sur deux phases (yeux ouverts puis yeux fermés) et en
# déduit un seuil personnalisé, à la place du seuil fixe config.EAR_SEUIL.
#
#     seuil = ear_ferme + (ear_ouvert - ear_ferme) * config.CALIBRATION_RATIO
#
# Utilisation typique, avant detection.analyser_source() :
#
#     import calibration
#     resultat = calibration.calibrer(source=0)
#     calibration.appliquer_calibration(resultat)   # met à jour config.EAR_SEUIL
#
# Le seuil est appliqué en modifiant directement config.EAR_SEUIL : comme les
# autres modules font `import config` puis lisent `config.EAR_SEUIL` à chaque
# appel (jamais `from config import EAR_SEUIL`), la mise à jour se propage
# automatiquement à detection.py et metriques.py sans les modifier.
# =============================================================================

import time

import cv2
import numpy as np
import mediapipe as mp

import config
from detection import calculer_ear_moyen


# ── Initialisation FaceMesh dédiée ────────────────────────────────────────────

def _init_facemesh():
    """
    Initialise une instance MediaPipe FaceMesh dédiée à la calibration.

    Dupliquée depuis detection._init_facemesh() (privée) plutôt que
    réutilisée, pour garder calibration.py indépendant de l'état interne de
    detection.py — les deux modules ne font que partager la fonction pure
    calculer_ear_moyen().
    """
    mp_face_mesh = mp.solutions.face_mesh
    return mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


# ── Capture d'une phase ────────────────────────────────────────────────────────

def _capturer_phase(cap, face_mesh, duree_sec: float, message: str) -> float:
    """
    Affiche `message` en overlay et moyenne l'EAR pendant `duree_sec` secondes.

    Paramètres
    ----------
    cap : cv2.VideoCapture
        Capture déjà ouverte.
    face_mesh : mediapipe.solutions.face_mesh.FaceMesh
    duree_sec : float
    message : str
        Instruction affichée à l'écran pendant la phase.

    Retourne
    --------
    float
        EAR moyen sur la phase. np.nan si aucune frame exploitable.
    """
    valeurs = []
    t_debut = time.time()

    while time.time() - t_debut < duree_sec:
        ret, frame = cap.read()
        if not ret:
            break

        hauteur, largeur = frame.shape[:2]
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        resultats = face_mesh.process(frame_rgb)
        frame_rgb.flags.writeable = True

        if resultats.multi_face_landmarks:
            landmarks = resultats.multi_face_landmarks[0].landmark
            ear = calculer_ear_moyen(landmarks, largeur, hauteur)
            valeurs.append(ear)

        temps_restant = max(duree_sec - (time.time() - t_debut), 0.0)
        cv2.rectangle(frame, (0, 0), (largeur, 90), (20, 20, 30), -1)
        cv2.putText(frame, message, (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        cv2.putText(frame, f"{temps_restant:.1f}s restantes",
                    (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 1)

        cv2.imshow("Calibration Blink VIPALI", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if len(valeurs) == 0:
        return float("nan")
    return float(np.mean(valeurs))


# ── Pipeline complet ────────────────────────────────────────────────────────────

def calibrer(source=0, duree_phase_sec: float = None) -> dict:
    """
    Pipeline complet de calibration : phase yeux ouverts puis yeux fermés.

    Paramètres
    ----------
    source : str | int
        Chemin vidéo ou index caméra (identique à detection.analyser_source()).
    duree_phase_sec : float | None
        Durée de chaque phase en secondes. Si None, utilise
        config.CALIBRATION_DUREE_SEC.

    Retourne
    --------
    dict avec les clés :
        ear_ouvert : float — EAR moyen yeux ouverts
        ear_ferme  : float — EAR moyen yeux fermés
        ecart      : float — ear_ouvert - ear_ferme
        seuil      : float — seuil calculé (ou config.EAR_SEUIL si peu fiable)
        fiable     : bool  — True si l'écart dépasse config.CALIBRATION_ECART_MIN
    """
    duree = duree_phase_sec if duree_phase_sec is not None else config.CALIBRATION_DUREE_SEC

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"[ERREUR] Impossible d'ouvrir la source : {source}")

    face_mesh = _init_facemesh()

    print("\n── Calibration ──────────────────────────────────────────────────")
    print("[INFO] Phase 1/2 : yeux ouverts")
    ear_ouvert = _capturer_phase(
        cap, face_mesh, duree, "Regarde la camera, yeux bien ouverts"
    )
    print(f"[INFO] EAR yeux ouverts : {ear_ouvert:.4f}")

    print("[INFO] Phase 2/2 : yeux fermes")
    ear_ferme = _capturer_phase(
        cap, face_mesh, duree, "Ferme les yeux et garde-les fermes"
    )
    print(f"[INFO] EAR yeux fermes  : {ear_ferme:.4f}")

    cap.release()
    cv2.destroyAllWindows()
    face_mesh.close()

    ecart = ear_ouvert - ear_ferme
    fiable = (not np.isnan(ecart)) and ecart >= config.CALIBRATION_ECART_MIN

    if fiable:
        seuil = ear_ferme + ecart * config.CALIBRATION_RATIO
    else:
        seuil = config.EAR_SEUIL
        print(f"[AVERTISSEMENT] Ecart trop faible ({ecart:.4f}) — "
              f"seuil par defaut conserve ({config.EAR_SEUIL}).")

    print(f"[INFO] Seuil calibre : {seuil:.4f}  (fiable={fiable})")
    print("─────────────────────────────────────────────────────────────────\n")

    return {
        "ear_ouvert": ear_ouvert,
        "ear_ferme": ear_ferme,
        "ecart": ecart,
        "seuil": seuil,
        "fiable": fiable,
    }


def appliquer_calibration(resultat: dict) -> None:
    """
    Applique le seuil calculé à config.EAR_SEUIL, si la calibration est fiable.

    Modifie config.EAR_SEUIL en place : comme detection.py et metriques.py
    font `import config` puis lisent `config.EAR_SEUIL` (jamais
    `from config import EAR_SEUIL`), la nouvelle valeur est prise en compte
    automatiquement dans le reste du pipeline, sans modifier ces fichiers.

    Paramètres
    ----------
    resultat : dict
        Dict retourné par calibrer().
    """
    if resultat["fiable"]:
        config.EAR_SEUIL = resultat["seuil"]
        print(f"[INFO] config.EAR_SEUIL mis a jour : {config.EAR_SEUIL:.4f}")
    else:
        print("[INFO] Seuil par defaut conserve (calibration non fiable).")