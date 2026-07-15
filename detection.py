# =============================================================================
# detection.py — Détection des clignements via MediaPipe FaceMesh
# =============================================================================
# Principe :
#   1. Chaque frame vidéo est passée dans MediaPipe FaceMesh
#   2. On récupère les 6 landmarks de chaque oeil
#   3. On calcule l'EAR (Eye Aspect Ratio) sur les deux yeux
#   4. Si EAR < seuil pendant N frames consécutives → clignement détecté
#
# Entrée  : chemin vidéo (str) ou flux caméra (int)
# Sortie  : dict contenant le signal EAR, les timestamps, et les clignements
# =============================================================================

import cv2
import numpy as np
import mediapipe as mp
import sys
import time
from typing import Optional

import config
import visualisation


# ── Utilitaires géométriques ──────────────────────────────────────────────────

def _distance_euclidienne(p1: tuple, p2: tuple) -> float:
    """
    Calcule la distance euclidienne entre deux points 2D.

    Paramètres
    ----------
    p1, p2 : tuple (x, y)

    Retourne
    --------
    float
    """
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def calculer_ear(landmarks, indices_oeil: list, largeur: int, hauteur: int) -> float:
    """
    Calcule l'Eye Aspect Ratio (EAR) pour un oeil.

    Formule (Soukupova & Cech, 2016) :
        EAR = (dist(P2,P6) + dist(P3,P5)) / (2 * dist(P1,P4))

    Où P1–P6 sont les 6 landmarks de l'oeil :
        P1 = coin gauche    P4 = coin droit
        P2 = haut gauche    P5 = bas droit
        P3 = haut droit     P6 = bas gauche

    Paramètres
    ----------
    landmarks : mediapipe NormalizedLandmarkList
        Landmarks du visage détectés par FaceMesh.
    indices_oeil : list[int]
        6 indices MediaPipe dans l'ordre [P1, P2, P3, P4, P5, P6].
    largeur : int
        Largeur de la frame en pixels (pour dénormaliser les coordonnées).
    hauteur : int
        Hauteur de la frame en pixels.

    Retourne
    --------
    float
        Valeur EAR. Proche de 0 = oeil fermé, ~0.25–0.35 = oeil ouvert.
    """
    # Extraction des 6 points et dénormalisation
    pts = []
    for idx in indices_oeil:
        lm = landmarks[idx]
        pts.append((lm.x * largeur, lm.y * hauteur))

    P1, P2, P3, P4, P5, P6 = pts

    # Distances verticales
    A = _distance_euclidienne(P2, P6)   # haut gauche → bas gauche
    B = _distance_euclidienne(P3, P5)   # haut droit  → bas droit

    # Distance horizontale
    C = _distance_euclidienne(P1, P4)   # coin gauche → coin droit

    if C < 1e-6:
        return 0.0  # évite division par zéro

    ear = (A + B) / (2.0 * C)
    return float(ear)


def calculer_ear_moyen(landmarks, largeur: int, hauteur: int) -> float:
    """
    Calcule l'EAR moyenné sur les deux yeux.

    Moyenne les deux EAR pour plus de robustesse
    (compense les légères asymétries du visage ou de la caméra).

    Paramètres
    ----------
    landmarks : mediapipe NormalizedLandmarkList
    largeur, hauteur : int

    Retourne
    --------
    float
        EAR moyen des deux yeux.
    """
    ear_gauche = calculer_ear(landmarks, config.LANDMARKS_OEIL_GAUCHE, largeur, hauteur)
    ear_droit  = calculer_ear(landmarks, config.LANDMARKS_OEIL_DROIT,  largeur, hauteur)

    if config.MOYENNE_DEUX_YEUX:
        return (ear_gauche + ear_droit) / 2.0
    else:
        return ear_gauche


# ── Détection des clignements ─────────────────────────────────────────────────

class DetecteurClignements:
    """
    Détecte les clignements à partir du signal EAR frame par frame.

    Un clignement est validé quand l'EAR reste sous le seuil pendant
    au moins EAR_FRAMES_CONSECUTIVES frames consécutives.

    Attributs
    ---------
    n_frames_sous_seuil : int
        Compteur de frames consécutives sous le seuil (réinitialisé après chaque blink).
    en_clignement : bool
        True si on est actuellement dans un clignement.
    frame_debut_blink : int | None
        Index de frame du début du clignement en cours.
    """

    def __init__(self):
        self.n_frames_sous_seuil  = 0
        self.en_clignement        = False
        self.frame_debut_blink    = None

    def update(self, ear: float, index_frame: int) -> Optional[dict]:
        """
        Met à jour l'état du détecteur avec l'EAR de la frame courante.

        Paramètres
        ----------
        ear : float
            EAR de la frame courante.
        index_frame : int
            Index de la frame courante (depuis le début).

        Retourne
        --------
        dict si un clignement vient d'être complété :
            {
                "frame_debut"  : int,
                "frame_fin"    : int,
                "duree_frames" : int,
            }
        None si pas de clignement complété sur cette frame.
        """
        if ear < config.EAR_SEUIL:
            # On est sous le seuil
            if not self.en_clignement:
                self.frame_debut_blink = index_frame
            self.n_frames_sous_seuil += 1
            self.en_clignement = True

        else:
            # On est au-dessus du seuil
            if self.en_clignement and \
               self.n_frames_sous_seuil >= config.EAR_FRAMES_CONSECUTIVES:
                # Clignement validé
                blink = {
                    "frame_debut" : self.frame_debut_blink,
                    "frame_fin"   : index_frame - 1,
                    "duree_frames": self.n_frames_sous_seuil,
                }
                # Réinitialisation
                self.n_frames_sous_seuil = 0
                self.en_clignement       = False
                self.frame_debut_blink   = None
                return blink

            # Réinitialisation (clignement trop court → faux positif)
            self.n_frames_sous_seuil = 0
            self.en_clignement       = False
            self.frame_debut_blink   = None

        return None


# ── Pipeline principal ────────────────────────────────────────────────────────

def _init_facemesh():
    """Initialise et retourne l'instance MediaPipe FaceMesh."""
    mp_face_mesh = mp.solutions.face_mesh
    return mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,       # active les landmarks iris (plus précis)
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def analyser_source(source, afficher_preview: bool = True,
                    duree_totale: float = None) -> dict:
    """
    Pipeline complet de détection sur une source vidéo ou caméra.

    Paramètres
    ----------
    source : str | int
        Chemin vers un fichier vidéo (str) ou index caméra (int, ex: 0).
    afficher_preview : bool
        Si True, affiche une fenêtre OpenCV avec l'EAR en overlay.
        Mettre False pour une utilisation en backend sans écran.

    Retourne
    --------
    dict avec les clés :
        signal_ear     : np.ndarray  — EAR frame par frame
        timestamps     : np.ndarray  — temps en secondes depuis le début
        clignements    : list[dict]  — liste des clignements détectés
                         chaque dict : {frame_debut, frame_fin, duree_frames}
        fps            : float       — FPS réel mesuré
        n_frames_total : int         — frames totales lues
        n_frames_detectees : int     — frames avec landmarks trouvés
        detection_rate : float       — ratio frames_detectées / total [0–1]
        valide         : bool        — True si detection_rate >= seuil config
    """
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        sys.exit(f"[ERREUR] Impossible d'ouvrir la source : {source}")

    # FPS
    fps_declare = cap.get(cv2.CAP_PROP_FPS)
    fps = fps_declare if fps_declare and fps_declare > 0 else config.FPS_FALLBACK
    print(f"[INFO] Source       : {source}")
    print(f"[INFO] FPS déclaré  : {fps:.1f}")

    face_mesh  = _init_facemesh()
    detecteur  = DetecteurClignements()
    overlay    = visualisation.OverlayTempsReel(fps)
    _duree     = duree_totale or config.DUREE_RECOMMANDEE_SEC

    signal_ear         = []
    timestamps         = []
    clignements        = []
    n_frames_detectees = 0
    index_frame        = 0
    t_debut            = time.time()

    print("[INFO] Analyse en cours... (appuyez sur 'q' pour arrêter)")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        hauteur, largeur = frame.shape[:2]
        t_frame = time.time() - t_debut

        # MediaPipe attend du RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        resultats = face_mesh.process(frame_rgb)
        frame_rgb.flags.writeable = True

        if resultats.multi_face_landmarks:
            landmarks = resultats.multi_face_landmarks[0].landmark
            ear = calculer_ear_moyen(landmarks, largeur, hauteur)
            n_frames_detectees += 1
        else:
            # Pas de visage détecté → on interpole avec la dernière valeur
            ear = signal_ear[-1] if signal_ear else config.EAR_SEUIL + 0.05

        signal_ear.append(ear)
        timestamps.append(t_frame)

        # Détection clignement
        blink = detecteur.update(ear, index_frame)
        if blink:
            clignements.append(blink)

        # Preview OpenCV avec overlay temps réel
        if afficher_preview:
            # Ajout du timestamp_fin sur le dernier clignement (pour BR glissant)
            if clignements and "timestamp_fin" not in clignements[-1]:
                clignements[-1]["timestamp_fin"] = t_frame

            frame_annotee = overlay.update(
                frame, ear, clignements, t_frame, _duree
            )
            cv2.imshow("Blink VIPALI — Detection", frame_annotee)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("[INFO] Arrêt manuel.")
                break

        index_frame += 1

    cap.release()
    cv2.destroyAllWindows()
    face_mesh.close()

    # FPS réel mesuré sur les timestamps
    if len(timestamps) >= 2:
        fps_reel = (len(timestamps) - 1) / (timestamps[-1] - timestamps[0])
        print(f"[INFO] FPS réel mesuré : {fps_reel:.2f}")
        fps = fps_reel

    signal_ear  = np.array(signal_ear,  dtype=np.float64)
    timestamps  = np.array(timestamps,  dtype=np.float64)

    n_total        = index_frame
    detection_rate = n_frames_detectees / n_total if n_total > 0 else 0.0
    valide         = detection_rate >= config.DETECTION_RATE_MIN

    print(f"[INFO] Frames totales    : {n_total}")
    print(f"[INFO] Frames détectées  : {n_frames_detectees} ({detection_rate*100:.1f}%)")
    print(f"[INFO] Clignements       : {len(clignements)}")

    if not valide:
        print(f"[AVERTISSEMENT] Taux de détection trop faible ({detection_rate*100:.1f}%). "
              f"Vérifiez l'éclairage et la position du visage.")

    if len(clignements) < config.N_BLINKS_MIN:
        print(f"[AVERTISSEMENT] Seulement {len(clignements)} clignements détectés "
              f"(minimum recommandé : {config.N_BLINKS_MIN}). "
              f"Métriques peu fiables.")

    return {
        "signal_ear"         : signal_ear,
        "timestamps"         : timestamps,
        "clignements"        : clignements,
        "fps"                : fps,
        "n_frames_total"     : n_total,
        "n_frames_detectees" : n_frames_detectees,
        "detection_rate"     : detection_rate,
        "valide"             : valide,
    }