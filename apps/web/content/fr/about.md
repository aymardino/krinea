## Pourquoi Tamis

Tamis est né d'un besoin concret. Le mainteneur menait une revue systématique sur les modèles de systèmes énergétiques à long terme en Afrique et devait extraire des données structurées de centaines de PDF, sans jamais perdre la trace du passage d'où venait chaque valeur. Le script d'extraction s'est doté d'un formulaire, puis d'un mécanisme pour citer la source à côté de chaque valeur extraite, puis d'une étape de sélection pour que l'équipe décide d'abord quels articles lire.

Un jour, il a fallu admettre que ce n'était plus un script. Une revue a besoin d'un lieu unique où les références, les décisions, les conflits, les extractions et les effectifs PRISMA vivent ensemble ; où deux personnes peuvent trier en aveugle puis comparer ; où le diagramme final se calcule au lieu de se recopier à la main. Tamis est ce lieu. Il est conçu par quelqu'un qui fait des revues, pour celles et ceux qui en font.

## Le nom

Un tamis sert à passer au crible. C'est exactement ce qu'est une revue systématique : des milliers de références entrent, une poignée d'études incluses ressort, et chaque référence écartée doit être comptée. Le logo est un tamis rond à maille diagonale.

## Ce que Tamis est, et ce qu'il n'est pas

Tamis est un établi de travail. Vous l'utilisez pour :

- importer des références (RIS, BibTeX, PubMed, Web of Science, CSV Scopus, Excel) ;
- supprimer les doublons ;
- sélectionner sur titre et résumé, puis sur texte intégral, seul ou en équipe : simple ou double lecture, mode aveugle, résolution des conflits ;
- extraire des données avec une IA qui remplit le formulaire que vous avez conçu et cite les passages sur lesquels elle s'appuie ;
- produire les effectifs et le diagramme de flux PRISMA 2020 ;
- exporter votre travail en RIS, CSV ou Excel, à tout moment.

Tamis n'est pas une autorité méthodologique. Il ne vous dit pas quels critères retenir, combien de lecteurs mobiliser, ni quand une étude est acceptable. Ces choix vous appartiennent, et vous en répondez.

L'IA propose ; elle ne décide jamais. Ses suggestions sont stockées à part des décisions humaines et n'en constituent jamais une. Une référence est incluse, exclue ou extraite parce qu'une personne l'a décidé.

Pour la restitution, Tamis suit la déclaration PRISMA 2020. Les gabarits sont reproduits sous licence CC BY 4.0 depuis prisma-statement.org (Page MJ et al., BMJ 2021;372:n71).

## Logiciel libre

L'application est publiée sous licence AGPL-3.0. Le moteur, c'est-à-dire le paquet Python `tamis_core` (analyseurs de fichiers, dédoublonnage, règles de sélection, schéma d'extraction), est publié sous licence MIT afin de pouvoir être réutilisé dans d'autres outils.

Le code source est disponible sur [github.com/aymardino/systematic_review](https://github.com/aymardino/systematic_review). Chacun peut héberger Tamis sur sa propre infrastructure, avec Docker Compose ou le blueprint Render. Signalements, contributions et discussions sont les bienvenus sur GitHub.

## L'édition hébergée

Une édition hébergée existe pour que vous puissiez essayer Tamis sans rien installer. Il s'agit d'une bêta, servie pour l'instant depuis une adresse en .onrender.com ; un vrai nom de domaine suivra. L'application web, l'API, le worker d'arrière-plan et la base de données tournent chez Render, à Francfort (Allemagne), dans l'Union européenne.

L'édition hébergée est exploitée par le mainteneur en tant que personne physique. Elle est non commerciale pour l'instant et fournie en l'état, au mieux des possibilités, sans garantie de disponibilité. Aucune offre payante n'est vendue à ce jour. Les offres Pro et Institution sont annoncées sur la page [tarifs](/pricing) et n'ouvriront qu'une fois la facturation et les documents juridiques prêts. Elles financeront alors l'hébergement et le temps du mainteneur. Quoi qu'il advienne de l'édition hébergée, le code reste libre sous AGPL-3.0.

Les pages [confidentialité](/privacy), [conditions d'utilisation](/terms) et [mentions légales](/legal) détaillent le traitement des données, les responsabilités et la publication du site.

## Qui est derrière Tamis

Tamis est un projet indépendant, porté par un développeur-chercheur basé en France, désigné sur ce site comme « le mainteneur ». Aucune société ni entité juridique n'existe encore. Tamis n'est affilié à aucune institution, entreprise ou autre outil de revue, et n'est financé ni soutenu par aucun d'eux. Les contributeurs sont les bienvenus sur GitHub et crédités dans le dépôt.

## Comment citer Tamis

Citez le numéro de version affiché dans l'application et l'adresse du dépôt. Un DOI accompagnera la première version taguée.

> Tamis, version X.Y.Z. https://github.com/aymardino/systematic_review

## Contact

Pour les bugs et les questions publiques, utilisez les issues et discussions GitHub. Pour les sujets privés, rendez-vous sur la page [contact](/contact).
