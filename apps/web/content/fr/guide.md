Ce guide suit une revue du premier import jusqu'au diagramme PRISMA. Chaque section indique l'onglet de la revue où se fait le travail : Données, Tri, Texte intégral, Extraction, PRISMA, Exports et Paramètres.

## Avant de commencer

**Une revue, un projet.** Créez une revue depuis votre tableau de bord, puis ouvrez les **Paramètres** :

- **Général** : le titre et la **question de recherche**. Rédigez-la tôt : l'IA la lit.
- **Critères de tri** : critères d'inclusion, critères d'exclusion et liste des motifs d'exclusion (un par ligne), ainsi que les mots-clés surlignés en vert et en rouge.
- **Équipe** : invitez des personnes par e-mail et donnez un rôle à chacune, choisissez combien de relecteurs doivent trier chaque notice, et activez ou non le mode aveugle.
- **IA** : le fournisseur et les modèles utilisés pour les suggestions et l'extraction (Google Gemini par défaut, avec `gemini-3.8-flash`).

**Les rôles.**

- *Propriétaire* et *Admin* modifient les paramètres, les critères, les mots-clés et les fichiers, et résolvent les conflits.
- *Relecteur* trie et extrait.
- *Lecteur* consulte et exporte.

**L'IA est facultative.** Les suggestions et les brouillons d'extraction utilisent votre propre clé d'API (Google Gemini, Anthropic Claude ou DeepSeek). La clé est stockée chiffrée ; vous pouvez l'ajouter dans le panneau IA de l'onglet Tri ou dans les paramètres de votre compte. L'IA propose et ne décide jamais : ses réponses sont gardées à part des décisions humaines.

## 1. Importer vos recherches (onglet Données)

Cliquez sur **Ajouter des résultats de recherche** et déposez vos exports : RIS, BibTeX, PubMed (`.nbib`), Web of Science (`.txt`), CSV, TSV ou Excel. Indiquer la base source (Scopus, PubMed…) est facultatif ; PRISMA compte les notices de chaque source.

Chaque fichier reste un import distinct. Vous pouvez le supprimer, filtrer les listes par fichier, et lui donner ses propres mots-clés, critères et champs d'extraction. Si votre revue a plusieurs sous-questions, importez **un fichier par recherche** : le reste de Krinea peut alors travailler recherche par recherche.

## 2. Retirer les doublons (onglet Données)

**Détecter les doublons** compare toutes les notices :

- même DOI ou titre identique : toujours fusionnées ;
- titres semblables à 95 % ou plus (réglable), avec le même premier auteur ou la même année : fusionnées automatiquement ;
- titres semblables de 85 % à 95 % : proposées dans **Paires à vérifier**, où vous choisissez **Garder celle-ci** ou **Différentes, garder les deux** ;
- en dessous de 85 % : études différentes.

Les doublons ne sont jamais supprimés : ils sont mis de côté, et **Restaurer** ou **Tout restaurer** les fait revenir.

**Quelle notice est gardée.** Dans les **Paramètres**, **Notice gardée parmi les doublons** propose trois règles :

- la notice la plus complète (par défaut) ;
- l'ordre de vos fichiers importés ;
- l'ordre des bases de données.

La notice gardée voit ses champs vides complétés par les autres, et chaque source qui a trouvé l'étude compte pour PRISMA.

**Une recherche par sous-question : choisissez l'ordre de vos fichiers.** Avec cette règle, chaque étude appartient au fichier de sa notice gardée, et à lui seul. Tout suit ce fichier : les filtres par fichier, les lancements de l'IA, les mots-clés et critères de chaque requête, les champs d'extraction propres à chaque requête et les exports. Placez en premier les requêtes dont les critères doivent l'emporter.

**Détectez les doublons avant le tri.** Une nouvelle détection repart de zéro : les paires réglées à la main reviennent à vérifier, et si une autre notice d'une étude est gardée, les décisions prises sur l'ancienne ne comptent plus. Évitez de la relancer une fois le tri commencé.

## 3. Tri sur titre et résumé (onglet Tri)

La page a trois colonnes : la liste à gauche, la référence au centre, les panneaux à droite.

**La liste.**

- **Vues** : À trier, Incluses par moi, Peut-être, Exclues par moi, Conflits, Incluses, Exclues, Toutes. Cochez-en plusieurs pour voir les références de l'une ou l'autre, par exemple *Incluses par moi* et *Peut-être*.
- **Filtres** : fichier importé, étiquette, et une zone de recherche. Fichiers et étiquettes se cochent aussi à plusieurs. Une référence s'affiche si elle correspond à l'une des vues, à l'un des fichiers et à l'une des étiquettes cochés, ainsi qu'à la recherche.
- **Ordre de la liste** : ordre d'import, titre, année, premier auteur, revue, *IA : à inclure d'abord* ou *IA : à exclure d'abord*, et *Vos suggestions : à inclure d'abord* ou *à exclure d'abord* (plus bas).
- La liste charge 200 références à la fois. Les liens aux deux bouts de la liste, ainsi que **Suivant** et **Précédent**, passent aux suivantes.

**Décider.**

- **Inclure**, **Peut-être** ou **Exclure**.
- Quand vous excluez, choisissez un **motif d'exclusion**. *Aucun motif* vide le champ ; un motif ne compte que pour une exclusion.
- Les **étiquettes** (séparées par des virgules) sont partagées avec l'équipe et servent de filtre. Une **note** reste attachée à votre décision.
- **Effacer ma décision** la retire.
- Clavier : **I** inclure, **M** peut-être, **E** exclure, **←** **→** (ou **J** **K**) pour naviguer, **P** pour ouvrir le PDF.

**Les mots-clés.** Les surlignages en vert et en rouge aident à lire. La revue a les siens, et chaque requête peut ajouter les siens quand un fichier est sélectionné. Cliquez sur un mot-clé pour ne montrer que les références qui le contiennent ; avec plusieurs mots-clés, choisissez *Tous* ou *Au moins un*. Les mots-clés ne sont qu'une aide visuelle : l'IA ne les lit jamais.

**Critères de la requête.** Quand une requête a sa propre sous-question et ses propres critères d'inclusion ou d'exclusion, la colonne de droite les affiche pour la référence à l'écran (ou pour le fichier sur lequel la liste est filtrée). Les admins les saisissent à cet endroit. Ils s'ajoutent aux critères de la revue, pour vous et pour l'IA.

**Travailler en équipe.** Avec deux relecteurs ou plus par notice (**Paramètres**, **Équipe**), une notice est décidée quand les décisions requises concordent ; sinon elle passe dans **Conflits**, où un admin la règle avec **Résoudre en consensus**. En mode aveugle, les relecteurs ne voient pas les décisions des autres ; les admins, si.

**Suggestions d'après vos décisions.** Dès que vous avez fait 50 inclusions ou exclusions, dont au moins 5 de chaque (*Peut-être* ne compte pas), le panneau **D'après vos décisions** peut suggérer une décision pour chaque référence, apprise de vos propres décisions dans cette revue. Il n'utilise aucun service d'IA et ne coûte rien : un petit modèle statistique (TF-IDF et régression logistique, comme en proposent d'autres outils de tri) lit les titres, mots-clés et résumés sur le serveur.

- Cliquez sur **Calculer les suggestions**. Quand elles sont prêtes, la liste montre d'abord les références que vous inclurez le plus probablement (*Vos suggestions : à inclure d'abord*) ; *Vos suggestions : à exclure d'abord* montre d'abord les autres.
- Chaque référence affiche la suggestion et son score sur 100, à côté de la suggestion de l'IA s'il y en a une. Une exclusion probable vient avec le motif d'exclusion des références qui lui ressemblent, déjà choisi pour vous.
- Une exclusion n'est suggérée que pour une référence dont le score est inférieur à celui de 19 de vos inclusions sur 20, dans un test sur des décisions que le modèle n'a pas apprises.
- Le panneau indique la fiabilité des suggestions (l'AUC : la probabilité qu'une référence incluse ait un meilleur score qu'une référence exclue) et les mots qui pèsent le plus. Plus vous décidez, meilleures elles sont : recalculez-les de temps en temps ; le panneau compte les décisions prises depuis.
- Elles ne sont qu'à vous : les suggestions de chaque relecteur n'apprennent que de ses propres décisions, si bien que le mode aveugle cache autant qu'avant. Elles n'existent qu'au tri sur titre et résumé et ne comptent jamais comme une décision.

## 4. Suggestions de l'IA (onglets Tri et Texte intégral)

**Ce que l'IA reçoit pour chaque référence :**

- la question de recherche ;
- les critères de la revue ;
- les critères de la requête de la référence, s'il y en a ;
- la liste des motifs d'exclusion ;
- la notice : titre, résumé, mots-clés, etc.

Au texte intégral, elle reçoit aussi le texte du PDF, jusqu'à 120 000 caractères ; pour un document plus long, le début et la fin. Elle ne reçoit jamais les mots-clés surlignés.

**La lancer.** Dans le panneau IA :

- réglez **Références par lancement** : 50 par défaut au tri sur titre et résumé, 1 au texte intégral. **Toute la liste** inscrit le maximum que permet la liste.
- Cliquez sur **Demander des suggestions à l'IA**.

Le lancement commence par la référence affichée et suit la liste telle qu'elle est filtrée et triée, en repartant du haut à la fin. Il saute les références que vous avez déjà décidées et celles qui ont déjà une suggestion, sauf si vous cochez **Refaire aussi celles qui ont déjà une suggestion**. Au-delà de 500 références, une confirmation est demandée. Les longs lancements continuent en arrière-plan, et vous pouvez continuer à travailler.

**Utiliser une suggestion.** La référence affiche la décision de l'IA, sa confiance et ses raisons. **Accepter la suggestion** l'enregistre comme votre propre décision. Sinon, une suggestion ne compte jamais comme une décision.

**Le coût.** Chaque référence est un appel facturé sur la clé utilisée, sauf si l'offre gratuite du fournisseur le couvre. Un quota quotidien peut arrêter un lancement ; le suivant reprend là où il s'était arrêté.

## 5. Tri sur texte intégral (onglet Texte intégral)

Cet onglet contient les références incluses au tri sur titre et résumé.

**Obtenir les PDF :**

- **Téléverser le PDF** ;
- **Chercher un PDF en accès libre** (il faut un DOI) ;
- une fois le PDF en place, **Remplacer le PDF** ou **Retirer le PDF**.

**Plusieurs PDF d'un coup.** Dans le panneau **PDF** à droite, **Ajouter plusieurs PDF** prend autant de fichiers que vous en choisissez, ou en déposez. Krinea lit chacun et retrouve son étude parmi celles incluses au tri sur titre et résumé :

- par son DOI, dans les métadonnées du fichier, sur sa première page ou dans son nom (la bibliographie n'est jamais lue : ses DOI sont ceux d'autres articles) ;
- sinon par son titre, trouvé en haut de ses premières pages ;
- sinon par le nom du fichier, tel que l'écrivent Zotero ou Mendeley (*Auteur - Année - Titre.pdf*).

Rien n'est encore ajouté : une liste montre chaque fichier avec l'étude trouvée et comment. Changez une étude ou laissez un fichier de côté, puis cliquez sur **Ajouter**. Quand deux études conviennent autant, aucune n'est choisie et les deux sont proposées en premier. Une étude déjà choisie pour un fichier ne peut pas l'être pour un autre, et une étude qui a déjà un PDF le garde, sauf si vous la choisissez vous-même. Le même bouton se trouve dans l'onglet Extraction.

Les vues **Sans PDF** et **Introuvables** listent ce qui manque.

**Les rapports introuvables.** Cliquez sur **Introuvable**. La référence sort de *À trier* et du compte de ce qu'il vous reste, et PRISMA la compte parmi les *rapports non récupérés* : elle n'a besoin ni de décision ni de motif. Cliquez de nouveau pour annuler.

**Décider** fonctionne comme au tri sur titre et résumé, avec un motif pour chaque exclusion. PRISMA liste les motifs d'exclusion au texte intégral.

**L'IA au texte intégral** ne prend que les références qui ont un PDF. Un PDF scanné sans texte est mis de côté sans interroger l'IA, et le panneau IA indique combien.

## 6. Extraction des données (onglet Extraction)

### La grille (Paramètres, Grille d'extraction)

Chaque champ a :

- une **Clé** : son identifiant, qui sert à enregistrer les données, de nom de colonne dans les exports et dans ce que lit l'IA ;
- un **Libellé** : le nom que vous lisez dans la vue d'extraction ;
- un **Type** ;
- des **Options**, pour les types enum et multi ;
- une **Consigne pour l'IA** ;
- des **Requêtes** : les requêtes auxquelles le champ appartient ;
- **Obligatoire** : s'il doit être rempli.

Les flèches règlent l'ordre des champs : l'ordre de la grille, des consignes données à l'IA et des colonnes des exports. Les **Modèles** proposent pour démarrer une grille PICO ou une grille de modélisation énergétique.

**Depuis un tableur.** **Importer une grille (CSV, Excel)** remplit la grille à partir d'un fichier avec une ligne par champ et le nom des colonnes sur la première ligne : Clé, Libellé, Type, Options, Consigne pour l'IA, Obligatoire, Requêtes (les noms anglais marchent aussi). Les requêtes sont des noms de fichiers, séparés par `;` ou `|`. Rien n'est enregistré tant que vous ne cliquez pas sur **Enregistrer**, et Krinea indique ce qu'il n'a pas pu lire. **Télécharger la grille (Excel)** donne un modèle à remplir.

**Les types.**

| Type | Ce que renvoie l'IA |
|---|---|
| text | un texte court |
| sentences | une ou deux phrases |
| number | un nombre |
| year | une année |
| yesno | oui ou non (yes ou no) |
| enum | une des options |
| multi | une ou plusieurs des options |
| list | une liste séparée par des virgules |
| search | rien : Krinea le remplit |
| doi | rien : Krinea le remplit |

Un champ *search* est rempli par Krinea avec la requête de l'étude, c'est-à-dire le nom du fichier de sa notice gardée. Il n'est jamais demandé à l'IA. Ajoutez-le seulement si vous voulez cette colonne.

Un champ *doi* est rempli par Krinea avec le lien du DOI de la notice de l'étude, par exemple `https://doi.org/10.1016/...`, cliquable dans la vue d'extraction et dans l'export Excel. La notice est plus sûre que le PDF, qui n'imprime pas toujours son DOI. Une étude dont la notice n'a pas de DOI affiche une case pour le saisir : il va alors dans la notice, et dans tous les exports.

**Les champs de certaines requêtes.** Laissez **Requêtes** sur *Toutes* pour un champ demandé à toutes les études, ou cochez une ou plusieurs requêtes. Une étude n'affiche, ne fait extraire et ne contrôle alors que les champs généraux et ceux de sa propre requête.

**Ne renommez pas une clé une fois des études extraites :** leurs valeurs sont enregistrées sous cette clé. Changez plutôt le libellé.

### Extraire et vérifier

**Comment l'IA extrait.** L'IA lit le PDF de chaque étude une seule fois, avec tous ses champs ensemble, et renvoie chaque valeur avec une courte citation exacte du texte. Une consigne peut donc faire référence à un autre champ par sa clé, par exemple « Volets touchés autres que main_strand » ; placez le champ cité en premier.

**Lancer l'IA.** **Extraire avec l'IA** traite les études affichées qui ont un PDF et pas encore de brouillon ; filtrez la liste pour en traiter moins. Les filtres par fichier, étiquette et statut acceptent plusieurs valeurs, comme au tri. Dans une étude ouverte, **Relancer l'IA** ne refait que celle-ci.

**Vérifier.** Ouvrez une étude pour voir les valeurs à côté du PDF et de son texte extrait. Les erreurs et avertissements signalent ce qu'il faut regarder : un champ obligatoire vide, une valeur hors des options, une citation manquante. Une réponse de l'IA qui n'est pas une des options s'affiche en orange, marquée « hors liste », à garder ou à remplacer. Les options sont reconnues sans tenir compte des majuscules, des accents, des espaces, des tirets et des tirets bas. Si la réponse de l'IA s'arrête avant les derniers champs, l'étude l'indique : relancez l'IA. Corrigez ce qui doit l'être, puis cliquez sur **Enregistrer comme vérifiée**. Les valeurs de l'IA sont gardées à côté des valeurs vérifiées.

## 7. Exports (onglet Exports)

**Choisissez l'étape :**

- tri sur titre et résumé : toutes les notices restantes une fois les doublons retirés ;
- tri sur texte intégral : les notices retenues sur titre et résumé ;
- extraction des données : les études incluses au texte intégral.

**Filtres.** Décision, motif d'exclusion, PDF (au texte intégral), fichier importé et étiquette. Chaque filtre accepte plusieurs valeurs : une notice est gardée si elle correspond à l'une des valeurs cochées dans un filtre, et à chaque filtre utilisé. Le nombre de notices s'affiche avant le téléchargement.

**Formats.** RIS pour un gestionnaire de références, CSV, ou Excel.

- **Les exports du tri** donnent pour chaque notice sa décision et son motif aux deux étapes, son PDF, ses étiquettes et notes, le fichier de sa notice gardée (`file`) et tous les fichiers qui l'ont trouvée (`files`).
- **Les exports de l'extraction** contiennent les extractions vérifiées, ou toutes les études incluses avec l'état de leur extraction. Le fichier Excel a trois feuilles : les valeurs, les citations et la grille.

Dans les fichiers Excel, les DOI et les adresses web sont des liens cliquables.

**Autres exports.** Le journal des décisions, les comptages PRISMA, et les notices doublons compris (avec le fichier d'où vient chacune). Choisissez un ou plusieurs fichiers pour les limiter à ces recherches : les notices que ces fichiers ont importées, les décisions sur les études qui comptent pour eux, et leurs propres comptages PRISMA. Ceux-ci comptent comme identifiées les notices importées par ces fichiers, comme triées les études qui comptent pour eux, et la différence comme doublons retirés.

En mode aveugle, les relecteurs n'exportent que leurs propres décisions et motifs.

## 8. PRISMA 2020 (onglet PRISMA)

Les comptages et le diagramme de flux sont calculés à partir de vos décisions : rien à recopier. Choisissez l'un des quatre gabarits officiels (nouvelle revue ou revue mise à jour, bases de données seules ou avec d'autres méthodes), puis **Télécharger le SVG**. La page montre aussi les notices trouvées dans chaque source et les motifs d'exclusion au texte intégral.

## Bonnes pratiques

- Importez un fichier par recherche, et réglez l'ordre de vos fichiers avant de détecter les doublons.
- Rédigez la question de recherche et les critères avant de lancer l'IA. Vérifiez quelques suggestions avant un gros lancement.
- Exportez votre travail régulièrement et gardez vos propres copies.
