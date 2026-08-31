# Blink VIPALI — Web

Version navigateur du compteur de clignements (port de `blink_vipali`).
Détection en temps réel via MediaPipe FaceLandmarker (JS), calcul de l'EAR et
des mêmes métriques que la version Python (Blink Rate, Blink Duration, BRV,
EAR baseline) → score /100.

Aucune étape de build, aucune dépendance npm à installer : site 100% statique
(HTML/CSS/JS, MediaPipe chargé depuis un CDN). La détection tourne entièrement
côté client — aucune image n'est envoyée à un serveur.

Le parcours est en 4 écrans :

1. **Instructions** — prérequis, choix de la durée de mesure
2. **Calibration** — capture l'EAR yeux ouverts puis yeux fermés pour calculer
   un seuil personnalisé (pas d'équivalent côté Python — voir plus bas)
3. **Mesure en direct** — compteur, EAR, blink rate, barre de progression
4. **Rapport** — score, signal EAR complet, distribution des durées

## Structure

```
index.html            page + les 4 écrans
style.css              styles
js/config.js           seuils et pondérations (= config.py + paramètres de calibration)
js/earUtils.js          calcul de l'EAR (= partie géométrique de detection.py)
js/blinkDetector.js    détecteur de clignements frame par frame (= DetecteurClignements)
js/metrics.js          BR / BD / BRV / scores /100 (= metriques.py)
js/main.js             caméra, boucle MediaPipe, calibration, UI temps réel, rapport
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

Si ce dossier `web/` vit dans le même repo que le code Python
(`salomevipali/blink_vipali`), importer le repo dans Vercel puis régler
**Root Directory** sur `web` avant de déployer — sinon Vercel cherche
`index.html` à la racine du repo et ne le trouve pas.

⚠️ Le site doit être servi en HTTPS pour que la caméra fonctionne — c'est
automatique sur `*.vercel.app`.

## Notes de portage

- Les indices de landmarks des yeux, les pondérations et les plages
  normatives sont identiques à `config.py`.
- Le calcul du score global renormalise sur les métriques disponibles si
  l'une d'elles est `NaN` (signal trop court), comme dans `metriques.py`.
- Le rapport reprend les 4 métriques + le score global sous forme de barres,
  ainsi que le signal EAR complet (avec seuil et clignements marqués) et
  l'histogramme des durées — équivalent simplifié du panneau matplotlib
  4 volets de `visualisation.py`.
- `numFaces: 1`, delegate GPU : sur les machines sans WebGL correct, changer
  `delegate: "GPU"` en `delegate: "CPU"` dans `js/main.js` si le modèle ne
  charge pas.

### Calibration (nouveau, sans équivalent Python)

`config.py`/`EAR_SEUIL` fixe le seuil à 0.18 pour tout le monde. La version
web ajoute un écran de calibration qui mesure l'EAR moyen yeux ouverts puis
yeux fermés (2 secondes chacun), et calcule un seuil personnalisé :

```
seuil = ear_fermé + (ear_ouvert − ear_fermé) × CALIBRATION_RATIO   (0.5 par défaut, à mi-chemin)
```

Si l'écart entre les deux est trop faible (`CALIBRATION_ECART_MIN`, 0.04 par
défaut — mauvais éclairage, visage mal détecté...), le seuil par défaut de
`config.js` est conservé et un avertissement s'affiche. La calibration est
skippable (`Passer`) et se refait à chaque nouvelle session.

Techniquement : `CONFIG.EAR_SEUIL` est muté directement à la fin de la
calibration (`config.js` exporte un seul objet partagé, relu à chaque appel
par tous les modules) — aucun autre fichier n'a eu besoin d'être modifié pour
supporter un seuil dynamique.
