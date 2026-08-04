# Le site de KnowYourCode

La page de présentation et de téléchargement, en Next.js (App Router,
TypeScript, Tailwind CSS v4). Une seule page, aucune dépendance d'interface :
le peu d'icônes est dessiné en SVG dans le code.

## En local

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # ce que Vercel exécutera
npm run lint
```

## Le téléchargement

Le DMG ne vit pas ici : il pèse plus que la limite de 100 Mo de l'offre Hobby
de Vercel. Il est déposé dans les
[Releases du dépôt](https://github.com/ynzue-es/KnowYourCode/releases).

Le bouton pointe vers `/api/telecharger`, une adresse qui ne change jamais.
La route demande à l'API GitHub la dernière version, y cherche le fichier dont
le nom finit par `.dmg`, et redirige le navigateur vers lui. Si rien n'est
trouvable — pas de version, pas de `.dmg`, API muette — elle envoie sur la
page des versions plutôt que de rendre une erreur.

`lib/release.ts` porte le même appel, mis en cache cinq minutes, et sert à
afficher la version et la taille sous le bouton. Il rend `null` en cas
d'échec : la page se construit quand même, sans ces précisions.

## Déploiement sur Vercel

- **Root Directory** : `site`
- **Framework** : Next.js (détecté)
- Aucune commande de build à régler à la main.

### Variables d'environnement

Les deux sont facultatives.

| Variable | Rôle |
| --- | --- |
| `GITHUB_TOKEN` | Un jeton GitHub sans droits particuliers — pour un dépôt public, aucun périmètre n'est nécessaire. Il fait passer la limite d'appels à l'API de 60 à 5 000 par heure. Sans lui, le site fonctionne : le cache de cinq minutes tient largement dans les 60. |
| `NEXT_PUBLIC_ADRESSE_SITE` | L'adresse publique du site, utilisée par les métadonnées Open Graph. Par défaut `https://knowyourcode.vercel.app`. À régler dès qu'un nom de domaine est branché. |
