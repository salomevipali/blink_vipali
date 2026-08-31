// =============================================================================
// earUtils.js — Calcul de l'Eye Aspect Ratio (port de detection.py)
// =============================================================================

import { CONFIG } from "./config.js";

/**
 * Distance euclidienne entre deux points {x, y}.
 */
function distance(p1, p2) {
  return Math.hypot(p1.x - p2.x, p1.y - p2.y);
}

/**
 * Calcule l'EAR pour un œil à partir des 6 landmarks normalisés
 * MediaPipe (coordonnées [0,1], on les remet à l'échelle pixel pour
 * rester cohérent avec la formule d'origine — le ratio est invariant
 * mais on garde le même code que la version Python).
 *
 * Formule (Soukupova & Cech, 2016) :
 *   EAR = (dist(P2,P6) + dist(P3,P5)) / (2 * dist(P1,P4))
 *
 * @param {Array} landmarks - tableau de landmarks normalisés {x,y,z}
 * @param {number[]} indicesOeil - 6 indices [P1..P6]
 * @param {number} largeur - largeur de la frame en pixels
 * @param {number} hauteur - hauteur de la frame en pixels
 */
export function calculerEar(landmarks, indicesOeil, largeur, hauteur) {
  const pts = indicesOeil.map((idx) => {
    const lm = landmarks[idx];
    return { x: lm.x * largeur, y: lm.y * hauteur };
  });
  const [P1, P2, P3, P4, P5, P6] = pts;

  const A = distance(P2, P6);
  const B = distance(P3, P5);
  const C = distance(P1, P4);

  if (C < 1e-6) return 0.0;

  return (A + B) / (2.0 * C);
}

/**
 * EAR moyenné sur les deux yeux.
 */
export function calculerEarMoyen(landmarks, largeur, hauteur) {
  const earGauche = calculerEar(landmarks, CONFIG.LANDMARKS_OEIL_GAUCHE, largeur, hauteur);
  const earDroit = calculerEar(landmarks, CONFIG.LANDMARKS_OEIL_DROIT, largeur, hauteur);

  return CONFIG.MOYENNE_DEUX_YEUX ? (earGauche + earDroit) / 2.0 : earGauche;
}
