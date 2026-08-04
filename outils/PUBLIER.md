# Publier KnowYourCode

Mode d'emploi de la première publication : obtenir un certificat, une clé
d'API, ranger les identifiants, poser les secrets GitHub. Une fois ces quatre
choses faites, publier une version se résume à poser un tag.

Tout ce qui suit suppose un compte Apple Developer payant (99 $/an). Un compte
gratuit ne donne pas de certificat « Developer ID » et ne permet pas de
notariser : c'est le seul point qui ne se contourne pas.

> Les intitulés de menus sont ceux de macOS et d'Xcode récents. Apple les
> retouche d'une version à l'autre — si vous ne trouvez pas exactement le
> libellé cité, cherchez le voisin le plus proche, la place dans la
> hiérarchie, elle, ne bouge pas.

---

## 1. Le certificat « Developer ID Application »

C'est lui qui signe l'application. Sans lui, le DMG se fabrique quand même,
mais avec une signature ad hoc que macOS refuse dès que le fichier vient d'une
autre machine.

Attention : seul le **titulaire du compte** (Account Holder) peut créer un
certificat Developer ID, et le nombre de certificats de ce type est limité par
compte. Ne le révoquez pas à la légère.

### Le chemin court, par Xcode

1. Xcode → menu **Xcode** → **Settings…** (nommé **Preferences…** avant
   Xcode 14) → onglet **Accounts**.
2. Ajoutez votre Apple ID s'il n'y est pas, sélectionnez l'équipe, puis
   **Manage Certificates…**.
3. Bouton **+** en bas à gauche → **Developer ID Application**.

Xcode génère la demande, la soumet et installe le certificat dans votre
trousseau. C'est terminé.

### Le chemin long, sans Xcode

1. Ouvrez **Trousseaux d'accès** (Keychain Access). Menu **Trousseaux
   d'accès** → **Assistant de certification** → **Demander un certificat à une
   autorité de certification…**.
2. Renseignez votre adresse e-mail, cochez **Enregistrée sur le disque** et
   **Me laisser indiquer les informations sur la paire de clés**. Choisissez
   2048 bits / RSA. Vous obtenez un fichier `.certSigningRequest`.
3. Sur <https://developer.apple.com/account/resources/certificates/list>,
   bouton **+**, section **Software** → **Developer ID Application**, puis
   **Continue**. Choisissez le profil de « Developer ID » proposé (l'option
   par défaut convient).
4. Téléversez le `.certSigningRequest`, téléchargez le `.cer` produit et
   double-cliquez dessus : il s'installe dans le trousseau.

### Vérifier

```bash
security find-identity -v -p codesigning
```

Une ligne `"Developer ID Application: Votre Nom (XXXXXXXXXX)"` doit
apparaître. `creer_dmg.py` la trouvera tout seul. Le code entre parenthèses
est votre **Team ID**, notez-le.

Si la ligne manque alors que le certificat est bien là, c'est en général que
le certificat intermédiaire d'Apple manque : téléchargez **Developer ID
Certification Authority** depuis <https://www.apple.com/certificateauthority/>
et double-cliquez dessus.

### L'exporter pour GitHub

GitHub Actions démarre chaque fois sur une machine neuve : il lui faut le
certificat **et sa clé privée**, dans un `.p12`.

1. Dans **Trousseaux d'accès**, catégorie **Mes certificats**, dépliez la
   ligne `Developer ID Application: …` — la clé privée doit apparaître
   dessous. Sélectionnez la ligne du certificat.
2. Clic droit → **Exporter « Developer ID Application… »** → format **Échange
   d'informations personnelles (.p12)**.
3. Donnez un mot de passe solide et gardez-le : c'est le secret
   `MOT_DE_PASSE_P12`.

Puis, pour le transformer en texte transportable :

```bash
base64 -i certificat.p12 | pbcopy
```

Le presse-papier contient le secret `CERTIFICAT_P12_BASE64`. Supprimez le
`.p12` du disque ensuite, il n'a rien à faire dans un dossier de travail.

---

## 2. La clé d'API App Store Connect

C'est ce avec quoi `notarytool` s'authentifie. Un mot de passe d'application
marche aussi, mais une clé se révoque sans toucher au compte Apple.

1. <https://appstoreconnect.apple.com/access/integrations/api> — onglet
   **Integrations**, section **App Store Connect API**, sous-onglet **Team
   Keys**. (Avant 2024, cette page s'appelait **Users and Access → Keys**.)
2. Bouton **+**, nommez la clé (`KnowYourCode notarisation`), rôle
   **Developer** — c'est le rôle le plus faible qui autorise la notarisation.
3. **Generate**, puis **Download API Key**. Le `.p8` ne se télécharge
   qu'**une seule fois** : rangez-le tout de suite.
4. Notez les deux identifiants affichés sur la page :
   - **Issuer ID**, en haut de la section, un UUID ;
   - **Key ID**, dans la ligne de la clé, dix caractères.

Rangez le fichier hors du dépôt, par exemple :

```bash
mkdir -p ~/.appstoreconnect/private_keys
mv ~/Downloads/AuthKey_XXXXXXXXXX.p8 ~/.appstoreconnect/private_keys/
chmod 600 ~/.appstoreconnect/private_keys/AuthKey_XXXXXXXXXX.p8
```

---

## 3. Le profil de trousseau, pour publier depuis cette machine

Pour ne pas retaper les trois identifiants à chaque fois, `notarytool` sait
les ranger dans le trousseau sous un nom :

```bash
xcrun notarytool store-credentials "knowyourcode" \
  --key ~/.appstoreconnect/private_keys/AuthKey_XXXXXXXXXX.p8 \
  --key-id XXXXXXXXXX \
  --issuer 00000000-0000-0000-0000-000000000000
```

À partir de là, une publication locale complète tient en une commande :

```bash
python outils/creer_dmg.py --notariser --profil-trousseau knowyourcode
```

Le DMG signé, notarisé et agrafé atterrit dans `dist/`. La première
notarisation prend souvent une dizaine de minutes ; les suivantes, deux ou
trois.

---

## 4. Les secrets GitHub

Dépôt → **Settings** → **Secrets and variables** → **Actions** → **New
repository secret**. Cinq secrets, dont les noms sont ceux qu'attend
`.github/workflows/publication.yml` :

| Secret | Contenu |
| --- | --- |
| `CERTIFICAT_P12_BASE64` | le `.p12` du §1, encodé en base64 |
| `MOT_DE_PASSE_P12` | le mot de passe choisi à l'export du `.p12` |
| `ASC_ISSUER_ID` | l'Issuer ID du §2 |
| `ASC_KEY_ID` | le Key ID du §2 |
| `ASC_CLE_P8_BASE64` | le `.p8` du §2, encodé en base64 |

Pour le `.p8` :

```bash
base64 -i ~/.appstoreconnect/private_keys/AuthKey_XXXXXXXXXX.p8 | pbcopy
```

Aucun secret d'accès au dépôt n'est nécessaire : le workflow crée la Release
avec le `GITHUB_TOKEN` fourni d'office.

---

## 5. Publier une version

1. Mettez à jour `version` dans `pyproject.toml`. C'est la seule source du
   numéro : `creer_dmg.py` le lit, et le DMG en tire son nom.
2. Committez, puis posez le tag correspondant :

```bash
git tag v0.1.0
git push origin v0.1.0
```

Le workflow se déclenche sur les tags `v*`. Il importe le certificat dans un
trousseau temporaire, fabrique le DMG signé, le notarise, crée la Release sur
le tag et y attache le DMG.

Si la notarisation échoue, le journal de l'étape contient l'identifiant de
soumission. Le détail se lit avec :

```bash
xcrun notarytool log <identifiant> --keychain-profile knowyourcode
```

---

## Ce qui peut mal se passer

**« aucune identité de signature »** — `security find-identity -v -p
codesigning` ne montre rien. Le certificat est absent ou sa clé privée l'est
(un `.cer` importé sans la clé qui a servi à la demande ne sert à rien).
`creer_dmg.py` retombe alors sur la signature ad hoc et le dit ; le DMG
produit ne vaut que sur cette machine.

**Notarisation refusée pour cause de runtime durci** — la soumission est
rejetée si un binaire du paquet n'est pas signé avec `--options runtime`.
`creer_dmg.py` parcourt le paquet et signe chaque binaire, mais un `.so`
ajouté par une dépendance nouvelle peut passer entre les mailles :
`xcrun notarytool log` nomme précisément le fichier fautif.

**L'application refuse de démarrer après installation** — le journal est dans
`~/.knowyourcode/journal.log`. Une erreur d'import y désigne un module que le
gel n'a pas vu passer ; il se rattrape avec un `--hidden-import` ajouté à
`geler()` dans `creer_dmg.py`.
