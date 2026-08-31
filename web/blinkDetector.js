// =============================================================================
// blinkDetector.js — Détection des clignements frame par frame
// (port de la classe DetecteurClignements dans detection.py)
// =============================================================================

import { CONFIG } from "./config.js";

export class BlinkDetector {
  constructor() {
    this.nFramesSousSeuil = 0;
    this.enClignement = false;
    this.frameDebutBlink = null;
    this.tDebutBlink = null;
  }

  /**
   * Met à jour l'état du détecteur avec l'EAR de la frame courante.
   *
   * @param {number} ear - EAR de la frame courante
   * @param {number} indexFrame - index de frame depuis le début
   * @param {number} tSec - timestamp en secondes depuis le début
   * @returns {object|null} le clignement complété, ou null
   */
  update(ear, indexFrame, tSec) {
    if (ear < CONFIG.EAR_SEUIL) {
      if (!this.enClignement) {
        this.frameDebutBlink = indexFrame;
        this.tDebutBlink = tSec;
      }
      this.nFramesSousSeuil += 1;
      this.enClignement = true;
      return null;
    }

    if (this.enClignement && this.nFramesSousSeuil >= CONFIG.EAR_FRAMES_CONSECUTIVES) {
      const blink = {
        frameDebut: this.frameDebutBlink,
        frameFin: indexFrame - 1,
        dureeFrames: this.nFramesSousSeuil,
        timestampDebut: this.tDebutBlink,
        timestampFin: tSec,
      };
      this._reset();
      return blink;
    }

    this._reset();
    return null;
  }

  _reset() {
    this.nFramesSousSeuil = 0;
    this.enClignement = false;
    this.frameDebutBlink = null;
    this.tDebutBlink = null;
  }
}
