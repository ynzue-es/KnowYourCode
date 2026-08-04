# KnowYourCode

Clin d'œil au KYC bancaire : connaître son code plutôt que son client.

Pendant que Claude Code travaille, une petite fenêtre flottante apparaît dans
un coin de l'écran, affiche un bout de votre code récent et vous demande de
l'expliquer. Le but n'est pas de noter, c'est de garder la maîtrise d'un code
qu'on ne relit plus, et de s'entraîner au passage sur Python et TypeScript.

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

## Lancement

```bash
python -m connais_ton_code
```

Ou, après un `pip install -e .`, simplement `knowyourcode`.

L'application n'apparaît ni dans le Dock ni dans la barre de menus. Au
démarrage, seule une petite pastille flottante s'affiche : c'est le
déclencheur de test, en attendant la détection automatique. Son bouton pose
une question ; l'icône à côté quitte l'application (Ctrl+C dans le terminal
fait la même chose).

## Vérification

```bash
python verifier.py
```

Le script déroule tout seul un cycle complet et contrôle, à chaque étape, que
l'application ne passe jamais au premier plan et que rien ne capte le clavier.
Il rend un code de sortie non nul en cas d'échec.

## Le cycle

1. **Masquée** — l'état par défaut, rien à l'écran.
2. **Question** — le chemin du fichier, le nom de la fonction, le code coloré,
   une zone de saisie, les boutons Répondre (Cmd+Entrée) et Passer.
3. **Évaluation** — un indicateur d'attente ; la fenêtre reste utilisable, on
   peut la déplacer, relire le code, ou l'écarter d'un Esc.
4. **Retour** — le verdict, ce qui a été oublié, et un bouton Suivant qui
   remet la fenêtre en sommeil.

## État d'avancement

Cette étape ne contient que l'interface et son cycle d'états. Les trois
briques qui la nourrissent existent sous forme de contrats documentés, avec
une implémentation factice derrière :

| Brique | Contrat | Aujourd'hui | Plus tard |
| --- | --- | --- | --- |
| `detecteur.py` | dire quand poser une question | un bouton de test | surveiller les dates de modification des transcripts JSONL sous `~/.claude/projects/` |
| `selecteur.py` | rendre un bout de code récent | trois extraits en dur, deux Python et un TSX | les fonctions tirées du diff des sept derniers jours |
| `evaluateur.py` | juger la réponse | un retour en dur après une seconde | un appel à l'API Anthropic en Haiku |

Chacune est un `Protocol` : remplacer la version factice par la vraie ne
demande de toucher ni à l'interface ni à l'orchestrateur.

## Données locales

Tout reste sur la machine, en clair, dans `~/.knowyourcode/` :

- `historique.json` — les questions posées, la réponse donnée, l'évaluation et
  la date. Sert à ne pas reposer deux fois la même question, et plus tard à
  mesurer la progression.
- `reglages.json` — la position des fenêtres.

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
  côté d'un terminal macOS.
- **Version gratuite uniquement.** Aucun composant de la version Pro n'est
  utilisé.

## Licence

MIT, voir [LICENSE](LICENSE).
