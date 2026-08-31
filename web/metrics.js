// =============================================================================
// metrics.js — Métriques blink et conversion en scores /100
// (port de metriques.py)
// =============================================================================

import { CONFIG } from "./config.js";

function mean(arr) {
  if (arr.length === 0) return NaN;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function std(arr) {
  if (arr.length === 0) return NaN;
  const m = mean(arr);
  return Math.sqrt(mean(arr.map((v) => (v - m) ** 2)));
}

function clip(v, lo, hi) {
  return Math.min(Math.max(v, lo), hi);
}

// ── 1. Blink Rate ────────────────────────────────────────────────────────────
export function calculerBR(clignements, dureeSec) {
  if (dureeSec < 1.0) return NaN;
  return (clignements.length / dureeSec) * 60.0;
}

// ── 2. Blink Duration ────────────────────────────────────────────────────────
export function calculerBD(clignements, fps) {
  if (clignements.length === 0) return { bdMoyenne: NaN, bdStd: NaN };
  const dureesMs = clignements.map((b) => (b.dureeFrames / fps) * 1000.0);
  return { bdMoyenne: mean(dureesMs), bdStd: std(dureesMs) };
}

// ── 3. Blink Rate Variability ────────────────────────────────────────────────
export function calculerBRV(clignements, fps, nFrames) {
  const tailleFenetreFrames = Math.floor(CONFIG.FENETRE_BR_SEC * fps);
  if (tailleFenetreFrames === 0 || nFrames < tailleFenetreFrames * 2) return NaN;

  const brFenetres = [];
  const pas = Math.max(1, Math.floor(tailleFenetreFrames / 2));
  for (let debut = 0; debut < nFrames - tailleFenetreFrames; debut += pas) {
    const fin = debut + tailleFenetreFrames;
    const nBlinksFenetre = clignements.filter(
      (b) => b.frameDebut >= debut && b.frameDebut < fin
    ).length;
    brFenetres.push((nBlinksFenetre / CONFIG.FENETRE_BR_SEC) * 60.0);
  }

  if (brFenetres.length < 2) return NaN;
  const m = mean(brFenetres);
  if (m < 1e-6) return NaN;
  return (std(brFenetres) / m) * 100.0;
}

// ── 4. EAR baseline ──────────────────────────────────────────────────────────
export function calculerEarBaseline(signalEar) {
  if (signalEar.length === 0) return NaN;
  const ouvert = signalEar.filter((v) => v >= CONFIG.EAR_SEUIL);
  if (ouvert.length === 0) return NaN;
  return mean(ouvert);
}

// ── 5. Conversion en scores /100 ────────────────────────────────────────────
function scoreGaussien(valeur, optimal, ecartMauvais) {
  if (Number.isNaN(valeur)) return NaN;
  const score = 100.0 * Math.exp(-0.5 * ((valeur - optimal) / ecartMauvais) ** 2);
  return clip(score, 0, 100);
}

function scoreLineaireInverse(valeur, bon, mauvais) {
  if (Number.isNaN(valeur)) return NaN;
  const score = (100.0 * (mauvais - valeur)) / (mauvais - bon);
  return clip(score, 0, 100);
}

export const scoreBR = (br) => scoreGaussien(br, CONFIG.BR_OPTIMAL, 8.0);
export const scoreBD = (bd) => scoreGaussien(bd, CONFIG.BD_OPTIMAL, 80.0);
export const scoreBRV = (brv) => scoreLineaireInverse(brv, CONFIG.BRV_BON, CONFIG.BRV_MAUVAIS);
export const scoreEAR = (ear) => scoreGaussien(ear, CONFIG.EAR_OPTIMAL, 0.06);

// ── 6. Score blink global ───────────────────────────────────────────────────
export function calculerScoreBlink(sBR, sBD, sBRV, sEAR) {
  const composantes = [
    [sBR, CONFIG.POIDS_BR],
    [sBD, CONFIG.POIDS_BD],
    [sBRV, CONFIG.POIDS_BRV],
    [sEAR, CONFIG.POIDS_EAR],
  ];
  const valides = composantes.filter(([s]) => !Number.isNaN(s));
  if (valides.length === 0) return NaN;

  const sommePonderee = valides.reduce((acc, [s, w]) => acc + s * w, 0);
  const sommePoids = valides.reduce((acc, [, w]) => acc + w, 0);
  return sommePonderee / sommePoids;
}

// ── 7. Pipeline complet ─────────────────────────────────────────────────────
export function calculerMetriques({ signalEar, clignements, fps, nFrames, dureeSec }) {
  const br = calculerBR(clignements, dureeSec);
  const { bdMoyenne, bdStd } = calculerBD(clignements, fps);
  const brv = calculerBRV(clignements, fps, nFrames);
  const earBaseline = calculerEarBaseline(signalEar);

  const sBR = scoreBR(br);
  const sBD = scoreBD(bdMoyenne);
  const sBRV = scoreBRV(brv);
  const sEAR = scoreEAR(earBaseline);

  const scoreBlink = calculerScoreBlink(sBR, sBD, sBRV, sEAR);

  return {
    br,
    bd: bdMoyenne,
    bdStd,
    brv,
    earBaseline,
    scoreBR: sBR,
    scoreBD: sBD,
    scoreBRV: sBRV,
    scoreEAR: sEAR,
    scoreBlink,
    nBlinks: clignements.length,
  };
}
