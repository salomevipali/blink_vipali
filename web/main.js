// =============================================================================
// main.js — Flux en 3 écrans (instructions → mesure → résultat)
// Capture caméra, détection MediaPipe, boucle temps réel, rapport final
// (port de detection.analyser_source() + visualisation.py + run.py)
// =============================================================================

import { FilesetResolver, FaceLandmarker } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs";
import { CONFIG } from "./config.js";
import { calculerEarMoyen } from "./earUtils.js";
import { BlinkDetector } from "./blinkDetector.js";
import { calculerMetriques } from "./metrics.js";

// ── Éléments DOM ─────────────────────────────────────────────────────────────

const stepIntro = document.getElementById("stepIntro");
const stepMesure = document.getElementById("stepMesure");
const stepReport = document.getElementById("stepReport");
const stepDots = document.querySelectorAll(".step-dot");

const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const octx = overlay.getContext("2d");

const btnStart = document.getElementById("btnStart");
const btnStop = document.getElementById("btnStop");
const btnRestart = document.getElementById("btnRestart");
const dureeInput = document.getElementById("dureeInput");
const introError = document.getElementById("introError");

const valBlinks = document.getElementById("valBlinks");
const valEar = document.getElementById("valEar");
const valBR = document.getElementById("valBR");
const valTemps = document.getElementById("valTemps");
const valQuality = document.getElementById("valQuality");

const gaugeEar = document.getElementById("gaugeEar");
const gaugeThreshold = document.getElementById("gaugeThreshold");
const progressFill = document.getElementById("progressFill");

const reportScoreBadge = document.getElementById("reportScoreBadge");
const repBR = document.getElementById("repBR");
const repBD = document.getElementById("repBD");
const repBRV = document.getElementById("repBRV");
const repEAR = document.getElementById("repEAR");
const reportBars = document.getElementById("reportBars");
const chartEarSignal = document.getElementById("chartEarSignal");
const chartDurations = document.getElementById("chartDurations");

gaugeThreshold.style.left = `${(CONFIG.EAR_SEUIL / CONFIG.EAR_JAUGE_MAX) * 100}%`;

// ── Navigation entre écrans ───────────────────────────────────────────────────

function goToStep(name) {
  stepIntro.hidden = name !== "intro";
  stepMesure.hidden = name !== "mesure";
  stepReport.hidden = name !== "report";

  const order = ["intro", "mesure", "report"];
  const idx = order.indexOf(name);
  stepDots.forEach((dot) => {
    const dotIdx = order.indexOf(dot.dataset.step);
    dot.classList.toggle("active", dotIdx === idx);
    dot.classList.toggle("done", dotIdx < idx);
  });

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── État de la session ───────────────────────────────────────────────────────

let faceLandmarker = null;
let stream = null;
let running = false;
let rafId = null;

let detector = null;
let indexFrame = 0;
let nFramesDetectees = 0;
let tDebut = 0;
let dureeCible = 90;
let fpsSession = 30;

const signalEar = [];
const timestamps = [];
const clignements = [];

// ── Initialisation MediaPipe ──────────────────────────────────────────────────

async function initFaceLandmarker() {
  const filesetResolver = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
  );
  faceLandmarker = await FaceLandmarker.createFromOptions(filesetResolver, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
      delegate: "GPU",
    },
    runningMode: "VIDEO",
    numFaces: 1,
  });
}

// ── Démarrage (étape 1 → 2) ───────────────────────────────────────────────────

async function start() {
  btnStart.disabled = true;
  introError.hidden = true;

  if (!faceLandmarker) {
    try {
      await initFaceLandmarker();
    } catch (err) {
      showIntroError("Le modèle de détection n'a pas pu se charger. Vérifie ta connexion et réessaie.");
      console.error(err);
      btnStart.disabled = false;
      return;
    }
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 },
      audio: false,
    });
  } catch (err) {
    showIntroError("Accès à la caméra refusé. Autorise-la dans les réglages de ton navigateur.");
    console.error(err);
    btnStart.disabled = false;
    return;
  }

  video.srcObject = stream;
  await video.play();

  overlay.width = video.videoWidth;
  overlay.height = video.videoHeight;

  dureeCible = Number(dureeInput.value);
  resetSession();
  goToStep("mesure");

  running = true;
  rafId = requestAnimationFrame(loop);
  btnStart.disabled = false;
}

function showIntroError(msg) {
  introError.textContent = msg;
  introError.hidden = false;
}

function resetSession() {
  detector = new BlinkDetector();
  indexFrame = 0;
  nFramesDetectees = 0;
  tDebut = performance.now();
  signalEar.length = 0;
  timestamps.length = 0;
  clignements.length = 0;
  valBlinks.textContent = "0";
  progressFill.style.width = "0%";
  valQuality.textContent = "démarrage…";
  valQuality.className = "quality-note";
}

// ── Boucle principale ────────────────────────────────────────────────────────

function loop() {
  if (!running) return;

  const now = performance.now();
  const tSec = (now - tDebut) / 1000;

  const result = faceLandmarker.detectForVideo(video, now);

  let ear;
  if (result.faceLandmarks && result.faceLandmarks.length > 0) {
    const landmarks = result.faceLandmarks[0];
    ear = calculerEarMoyen(landmarks, video.videoWidth, video.videoHeight);
    nFramesDetectees += 1;
  } else {
    ear = signalEar.length > 0 ? signalEar[signalEar.length - 1] : CONFIG.EAR_SEUIL + 0.05;
  }

  signalEar.push(ear);
  timestamps.push(tSec);

  const blink = detector.update(ear, indexFrame, tSec);
  if (blink) clignements.push(blink);

  updateReadouts(ear, tSec);
  drawOverlay(ear);

  indexFrame += 1;

  if (dureeCible > 0 && tSec >= dureeCible) {
    stop();
    return;
  }

  rafId = requestAnimationFrame(loop);
}

// ── Mise à jour des lectures (étape 2) ────────────────────────────────────────

function brGlissant(tActuel) {
  const fenetre = CONFIG.FENETRE_BR_SEC;
  const recents = clignements.filter((b) => b.timestampFin >= tActuel - fenetre);
  return (recents.length / fenetre) * 60.0;
}

function updateReadouts(ear, tSec) {
  valBlinks.textContent = String(clignements.length);
  valEar.textContent = ear.toFixed(3);

  const ratio = Math.min(Math.max(ear / CONFIG.EAR_JAUGE_MAX, 0), 1);
  gaugeEar.style.width = `${ratio * 100}%`;
  gaugeEar.style.background = ear < CONFIG.EAR_SEUIL ? "var(--alert-red)" : "var(--good-green)";

  const br = brGlissant(tSec);
  valBR.textContent = tSec >= 5 ? `${br.toFixed(1)} /min` : "— /min";

  valTemps.textContent = `${tSec.toFixed(0)} s${dureeCible > 0 ? ` / ${dureeCible} s` : ""}`;
  if (dureeCible > 0) {
    progressFill.style.width = `${Math.min((tSec / dureeCible) * 100, 100)}%`;
  } else {
    progressFill.style.width = "100%";
  }

  const detectionRate = indexFrame > 0 ? nFramesDetectees / (indexFrame + 1) : 0;
  if (indexFrame < 30) {
    valQuality.textContent = "en cours d'évaluation…";
    valQuality.className = "quality-note";
  } else if (detectionRate >= CONFIG.DETECTION_RATE_MIN) {
    valQuality.textContent = `signal bon (${(detectionRate * 100).toFixed(0)}%)`;
    valQuality.className = "quality-note ok";
  } else {
    valQuality.textContent = `signal faible (${(detectionRate * 100).toFixed(0)}%)`;
    valQuality.className = "quality-note warn";
  }
}

function drawOverlay(ear) {
  octx.clearRect(0, 0, overlay.width, overlay.height);
  if (ear < CONFIG.EAR_SEUIL) {
    octx.strokeStyle = CONFIG.COULEUR_SEUIL;
    octx.lineWidth = 6;
    octx.strokeRect(3, 3, overlay.width - 6, overlay.height - 6);
  }
}

// ── Arrêt & rapport (étape 2 → 3) ─────────────────────────────────────────────

function stop() {
  running = false;
  if (rafId) cancelAnimationFrame(rafId);
  if (stream) stream.getTracks().forEach((t) => t.stop());

  btnStop.disabled = true;

  const nFrames = signalEar.length;
  const dureeSec = timestamps.length > 0 ? timestamps[timestamps.length - 1] : 0;
  fpsSession = dureeSec > 1 ? nFrames / dureeSec : 30;

  const metriques = calculerMetriques({
    signalEar,
    clignements,
    fps: fpsSession,
    nFrames,
    dureeSec,
  });

  goToStep("report");
  showReport(metriques);
  btnStop.disabled = false;
}

function showReport(m) {
  reportScoreBadge.textContent = Number.isNaN(m.scoreBlink)
    ? "— /100"
    : `${m.scoreBlink.toFixed(0)} /100`;

  repBR.textContent = Number.isNaN(m.br) ? "—" : `${m.br.toFixed(1)} /min`;
  repBD.textContent = Number.isNaN(m.bd) ? "—" : `${m.bd.toFixed(0)} ms`;
  repBRV.textContent = Number.isNaN(m.brv) ? "—" : `${m.brv.toFixed(1)} %`;
  repEAR.textContent = Number.isNaN(m.earBaseline) ? "—" : m.earBaseline.toFixed(3);

  const bars = [
    { label: "score br", value: m.scoreBR, color: "var(--ear-blue)" },
    { label: "score bd", value: m.scoreBD, color: "var(--blink-orange)" },
    { label: "score brv", value: m.scoreBRV, color: "var(--good-green)" },
    { label: "score ear", value: m.scoreEAR, color: "var(--alert-red)" },
    { label: "global", value: m.scoreBlink, color: "var(--ear-blue)" },
  ];

  reportBars.innerHTML = bars
    .map((b) => {
      const v = Number.isNaN(b.value) ? 0 : b.value;
      const label = Number.isNaN(b.value) ? "—" : v.toFixed(0);
      return `
        <div class="report-bar-row">
          <span class="report-bar-label">${b.label}</span>
          <div class="report-bar-track">
            <div class="report-bar-fill" style="width:${v}%; background:${b.color}"></div>
          </div>
          <span class="report-bar-num">${label}</span>
        </div>`;
    })
    .join("");

  // Les canvas doivent être dimensionnés une fois affichés (clientWidth > 0)
  requestAnimationFrame(() => {
    drawEarSignalChart();
    drawDurationsHistogram();
  });
}

// ── ① Signal EAR complet + clignements (port de tracer_ear) ──────────────────

function drawEarSignalChart() {
  const canvas = chartEarSignal;
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight || 180;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  if (signalEar.length < 2) {
    ctx.fillStyle = "#8b96a5";
    ctx.font = "12px sans-serif";
    ctx.fillText("Signal trop court", 10, cssH / 2);
    return;
  }

  const padL = 30, padB = 16, padT = 6, padR = 6;
  const w = cssW - padL - padR;
  const h = cssH - padT - padB;
  const tMax = timestamps[timestamps.length - 1] || 1;
  const yMax = CONFIG.EAR_JAUGE_MAX;

  const xOf = (t) => padL + (t / tMax) * w;
  const yOf = (ear) => padT + h - (Math.min(Math.max(ear, 0), yMax) / yMax) * h;

  // Axe Y (seuil)
  const ySeuil = yOf(CONFIG.EAR_SEUIL);
  ctx.strokeStyle = CONFIG.COULEUR_SEUIL;
  ctx.setLineDash([4, 3]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padL, ySeuil);
  ctx.lineTo(padL + w, ySeuil);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = CONFIG.COULEUR_SEUIL;
  ctx.font = "9px ui-monospace, monospace";
  ctx.fillText(CONFIG.EAR_SEUIL.toFixed(2), 2, ySeuil + 3);

  // Zone sous le seuil (clignements)
  ctx.fillStyle = "rgba(224,92,92,0.15)";
  for (let i = 1; i < signalEar.length; i++) {
    if (signalEar[i] < CONFIG.EAR_SEUIL) {
      const x1 = xOf(timestamps[i - 1]);
      const x2 = xOf(timestamps[i]);
      ctx.fillRect(x1, ySeuil, Math.max(x2 - x1, 1), yOf(0) - ySeuil);
    }
  }

  // Signal EAR
  ctx.strokeStyle = CONFIG.COULEUR_EAR;
  ctx.lineWidth = 1.3;
  ctx.beginPath();
  signalEar.forEach((ear, i) => {
    const x = xOf(timestamps[i]);
    const y = yOf(ear);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Marqueurs de clignements
  ctx.fillStyle = CONFIG.COULEUR_BLINKS;
  clignements.forEach((b) => {
    const tMid = (b.timestampDebut + b.timestampFin) / 2;
    const x = xOf(tMid);
    const y = ySeuil + 9;
    ctx.beginPath();
    ctx.moveTo(x - 3, y - 5);
    ctx.lineTo(x + 3, y - 5);
    ctx.lineTo(x, y);
    ctx.closePath();
    ctx.fill();
  });

  // Axe X (temps)
  ctx.fillStyle = "#8b96a5";
  ctx.font = "9px ui-monospace, monospace";
  ctx.fillText("0s", padL, cssH - 4);
  ctx.fillText(`${tMax.toFixed(0)}s`, padL + w - 18, cssH - 4);
}

// ── ② Distribution des durées de clignements (port de tracer_durees) ─────────

function drawDurationsHistogram() {
  const canvas = chartDurations;
  const dpr = window.devicePixelRatio || 1;
  const cssW = canvas.clientWidth;
  const cssH = canvas.clientHeight || 180;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  if (clignements.length < 3) {
    ctx.fillStyle = "#8b96a5";
    ctx.font = "12px sans-serif";
    ctx.fillText("Pas assez de clignements", 10, cssH / 2);
    return;
  }

  const durees = clignements.map((b) => (b.dureeFrames / fpsSession) * 1000.0);
  const nBins = Math.min(15, durees.length);
  const dMin = Math.min(...durees);
  const dMax = Math.max(...durees);
  const range = Math.max(dMax - dMin, 1);
  const binW = range / nBins;

  const bins = new Array(nBins).fill(0);
  durees.forEach((d) => {
    let idx = Math.floor((d - dMin) / binW);
    if (idx >= nBins) idx = nBins - 1;
    if (idx < 0) idx = 0;
    bins[idx] += 1;
  });

  const padL = 26, padB = 16, padT = 6, padR = 6;
  const w = cssW - padL - padR;
  const h = cssH - padT - padB;
  const maxCount = Math.max(...bins, 1);

  const barGap = 2;
  const barW = w / nBins - barGap;

  ctx.fillStyle = CONFIG.COULEUR_BLINKS;
  bins.forEach((count, i) => {
    const barH = (count / maxCount) * h;
    const x = padL + i * (w / nBins) + barGap / 2;
    const y = padT + h - barH;
    ctx.fillRect(x, y, Math.max(barW, 1), barH);
  });

  // Ligne moyenne
  const moyenne = durees.reduce((a, b) => a + b, 0) / durees.length;
  const xMoy = padL + ((moyenne - dMin) / range) * w;
  ctx.strokeStyle = CONFIG.COULEUR_SEUIL;
  ctx.setLineDash([4, 3]);
  ctx.beginPath();
  ctx.moveTo(xMoy, padT);
  ctx.lineTo(xMoy, padT + h);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#8b96a5";
  ctx.font = "9px ui-monospace, monospace";
  ctx.fillText(`${dMin.toFixed(0)}ms`, padL, cssH - 4);
  ctx.fillText(`${dMax.toFixed(0)}ms`, padL + w - 24, cssH - 4);
  ctx.fillStyle = CONFIG.COULEUR_SEUIL;
  ctx.fillText(`moy ${moyenne.toFixed(0)}ms`, Math.min(Math.max(xMoy - 20, padL), padL + w - 50), padT + 10);
}

// ── Écouteurs ────────────────────────────────────────────────────────────────

btnStart.addEventListener("click", start);
btnStop.addEventListener("click", stop);
btnRestart.addEventListener("click", () => {
  goToStep("intro");
});
