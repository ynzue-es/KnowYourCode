<img src="ressources/logo.png" alt="KnowYourCode" width="88">

# KnowYourCode

Clin d'œil au KYC bancaire : connaître son code plutôt que son client.

Quand une session Claude Code se met à travailler, une bulle discrète apparaît
sous la barre de menus : « Répondez à quelques questions sur votre code ! ».
Un clic ouvre une petite fenêtre qui tire au hasard une fonction du dépôt en
cours et vous demande de l'expliquer. Un modèle tiers compare votre
explication au code et vous dit ce que vous avez oublié.

Le but n'est pas de noter, c'est de garder la maîtrise d'un code qu'on ne
relit plus, et de s'entraîner au passage sur Python et TypeScript.

La fenêtre ne vole jamais le focus clavier : elle s'affiche pendant que vous
tapez dans votre terminal, et elle attend. Vous cliquez dedans si vous voulez
répondre, Esc la fait disparaître sans rien enregistrer.

## Installation

macOS, Python 3.10 ou plus récent.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

L'évaluation passe par l'API Mistral. Deux façons de fournir la clé, au choix :

```bash
export MISTRAL_API_KEY="votre-clé"
# ou, pour ne pas dépendre de l'environnement du terminal :
echo "votre-clé" > ~/.knowyourcode/cle_mistral && chmod 600 ~/.knowyourcode/cle_mistral
```

Sans clé, l'application démarre quand même et rend une évaluation factice :
tout le reste fonctionne, il n'y a que le verdict qui est faux.

## Lancement

```bash
python -m connais_ton_code
```

Ou, après un `pip install -e .`, simplement `knowyourcode`.

L'application n'apparaît pas dans le Dock. Sa seule présence permanente est
une icône dans la barre de menus, en haut à droite de l'écran. Elle dit son
état sans qu'on ait à ouvrir le menu :

| Icône | Sens |
| --- | --- |
| pleine | à l'écoute, une session détectée déclenchera une invitation |
| creuse | en pause, rien ne se déclenchera tout seul |

Le menu contient quatre entrées :

- **Détection active** — l'interrupteur. La pause survit au redémarrage, et
  n'empêche pas de demander une question à la main.
- **Poser une question** — ouvre directement une question, sans attendre.
- **Simuler une détection** — affiche l'invitation, comme le fait le démarrage
  d'une session. Grisée pendant la pause, puisqu'elle ne produirait rien.
- **Quitter KnowYourCode** — Ctrl+C dans le terminal fait la même chose.

## Vérification

```bash
python verifier.py
```

Le script contrôle d'abord le repérage des fonctions, puis déroule un cycle
complet dans l'interface en vérifiant à chaque étape que l'application ne
passe jamais au premier plan et que rien ne capte le clavier. Sa dernière
étape prend délibérément le focus une seconde, pour vérifier l'autre moitié de
la promesse : qu'un clic dans la fenêtre permet bien de taper sa réponse, et
qu'Esc rend ensuite le clavier. Il rend un code de sortie non nul en cas
d'échec, et n'a besoin ni de réseau, ni de clé, ni d'une session en cours.

## Le cycle

1. **Masquée** — l'état par défaut, rien à l'écran que l'icône de la barre.
2. **Invitation** — une bulle en haut à droite propose de répondre. Elle
   s'efface d'elle-même au bout de quinze secondes ; un clic ouvre la
   question, la croix l'écarte. Tant qu'elle est ignorée, aucun extrait n'est
   consommé.
3. **Question** — le chemin du fichier, le nom de la fonction, le code coloré,
   une zone de saisie, les boutons Répondre (Cmd+Entrée) et Passer.
4. **Évaluation** — un indicateur d'attente ; la fenêtre reste utilisable, on
   peut la déplacer, relire le code, ou l'écarter d'un Esc.
5. **Retour** — le verdict, ce qui a été oublié, et un bouton Suivant qui
   remet la fenêtre en sommeil.

Les transitions autorisées sont déclarées dans `etats.py` et vérifiées à
chaque passage : une transition hors table est traitée comme un bug, pas comme
un cas à absorber en silence.

## Comment ça marche

**La détection** (`detecteur.py`) surveille les dates de modification des
transcripts JSONL sous `~/.claude/projects/`. Claude Code y écrit en continu
pendant qu'il travaille : un fichier touché dans les vingt dernières secondes
signale une session active. L'invitation part sur le front montant, une seule
fois par épisode, et pas plus d'une fois par quart d'heure. Le dossier du
projet est lu dans le champ `cwd` du transcript, et non déduit du nom du
dossier, qui n'est pas réversible.

**La sélection** (`selecteur.py`, `extraction.py`) parcourt le projet détecté
et tire une fonction au hasard parmi celles de 4 à 60 lignes. Les fonctions
Python sont repérées avec `ast`, les fonctions TypeScript et TSX par un
comptage d'accolades qui saute les chaînes et les commentaires. Au hasard, et
non « la plus récente » : le code qu'on ne comprend plus n'est pas toujours
celui qu'on vient d'écrire.

**L'évaluation** (`evaluateur.py`) envoie le code et votre explication à
`mistral-small-latest` et en attend un verdict, une note et une liste de ce
que vous n'avez pas mentionné. Un modèle tiers plutôt que celui qui a écrit le
code : on ne demande pas à quelqu'un de corriger la copie qu'il a dictée.
L'appel a lieu hors du fil de l'interface, qui reste utilisable pendant ce
temps.

Chacune de ces trois briques est un `Protocol` doublé d'une version factice,
utilisée par la vérification et comme repli quand la vraie n'est pas
disponible.

## Données locales

Tout reste sur la machine, en clair, dans `~/.knowyourcode/` :

- `historique.json` — les questions posées, la réponse donnée, l'évaluation et
  la date. Sert à ne pas reposer deux fois la même question, et à mesurer la
  progression.
- `reglages.json` — la position de la fenêtre et l'état de la détection.
- `cle_mistral` — la clé d'API, si vous choisissez cette méthode. Hors du
  dépôt, exprès.

La variable d'environnement `KNOWYOURCODE_DOSSIER` déplace ce dossier, ce dont
se sert `verifier.py` pour ne pas polluer l'historique réel.

## Notes macOS

- **Le focus.** Sur macOS, `QWidget.show()` active l'application quoi qu'on
  fasse : ni `WA_ShowWithoutActivating`, ni `WindowDoesNotAcceptFocus`, ni le
  passage en application accessoire ne l'en empêchent (constaté avec Qt 6.11).
  L'affichage passe donc par `orderFrontRegardless` sur la fenêtre native, en
  contournant Qt. Voir `connais_ton_code/affichage.py`.
- **L'apparence.** Les composants viennent de PyQt6-Fluent-Widgets, mais le
  cadre est dessiné à la main : panneau sombre sans bordure de titre, coins
  arrondis, ombre douce, police d'interface du système. Le rendu Fluent
  d'origine, avec sa barre de titre et sa police Segoe UI, jure franchement à
  côté d'un terminal macOS. Aucun composant de la version Pro n'est utilisé.
- **Les certificats.** Les Python installés depuis python.org n'ont pas de
  magasin de certificats tant qu'on n'a pas lancé leur script d'installation.
  L'appel à Mistral passe donc par `certifi`.
- **Le logo et l'icône** sont dessinés par `outils/creer_logo.py` et
  `barre_menu.py` plutôt que chargés depuis des fichiers d'image. L'icône est
  déclarée comme masque : macOS la recolore alors selon le thème de la barre,
  comme ses propres icônes.

## Licence

MIT, voir [LICENSE](LICENSE).
