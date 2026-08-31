# Blink VIPALI — Web

Version navigateur du compteur de clignements (port de `blink_vipali`).
Détection en temps réel via MediaPipe FaceLandmarker (JS), calcul de l'EAR et
des mêmes métriques que la version Python (Blink Rate, Blink Duration, BRV,
EAR baseline) → score /100.

Aucune étape de build, aucune dépendance npm à installer : site 100% statique
(HTML/CSS/JS, MediaPipe chargé depuis un CDN). La détection tourne entièrement
côté client — aucune image n'est envoyée à un serveur.

## Structure

```
index.html          page + panneau de mesures
style.css            styles
js/config.js         seuils et pondérations (= config.py)
js/earUtils.js        calcul de l'EAR (= partie géométrique de detection.py)
js/blinkDetector.js  détecteur de clignements frame par frame (= DetecteurClignements)
js/metrics.js        BR / BD / BRV / scores /100 (= metriques.py)
js/main.js           caméra, boucle MediaPipe, UI temps réel, rapport final
```

## Tester en local

Un simple serveur statique suffit (nécessaire car `getUserMedia` exige
http/https, pas `file://`) :

```bash
npx serve .
# ou
python3 -m http.server 8080
```

Puis ouvrir `http://localhost:8080` (ou le port indiqué) — Chrome/Edge/Safari
récents recommandés.

## Déployer sur Vercel

Depuis ce dossier :

```bash
npm i -g vercel   # si pas déjà installé
vercel
```

Répondre aux questions par défaut (aucun framework détecté → "Other", pas de
build command, output directory = `.`). Vercel sert directement `index.html`
à la racine.

Ou en passant par GitHub :

1. `git init && git add . && git commit -m "blink vipali web"`
2. Pousser sur un repo GitHub
3. Sur vercel.com → "Add New Project" → importer le repo → déployer
   (aucune configuration à changer)

⚠️ Le site doit être servi en HTTPS pour que la caméra fonctionne — c'est
automatique sur `*.vercel.app`.

## Notes de portage

- Les indices de landmarks des yeux, le seuil EAR, les pondérations et les
  plages normatives sont identiques à `config.py`.
- Le calcul du score global renormalise sur les métriques disponibles si
  l'une d'elles est `NaN` (signal trop court), comme dans `metriques.py`.
- Le rapport post-capture reprend les 4 métriques + le score global sous
  forme de barres, en équivalent simplifié du panneau matplotlib 4 volets de
  `visualisation.py` (pas de reproduction du signal EAR complet ni de
  l'histogramme des durées pour l'instant — à ajouter si besoin).
- `numFaces: 1`, delegate GPU : sur les machines sans WebGL correct, changer
  `delegate: "GPU"` en `delegate: "CPU"` dans `js/main.js` si le modèle ne
  charge pas.
