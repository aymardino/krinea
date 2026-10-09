*Version 0.1 — en cours de relecture juridique*

*Dernière mise à jour : 8 octobre 2026*

## En bref

- Krinea conserve ce que vous lui confiez : les informations de votre compte et le contenu de vos revues (références, PDF, décisions, extractions).
- Vos données sont hébergées à Francfort (Allemagne, Union européenne).
- Nous utilisons trois cookies, aucun pour la mesure d'audience ou la publicité. Pas de pistage, pas de bandeau.
- Rien n'est envoyé à un fournisseur d'IA tant qu'un relecteur de votre équipe ne demande pas une suggestion ou une extraction.
- Vous pouvez tout exporter à tout moment, supprimer vous-même une revue et demander la suppression de votre compte.
- L'édition hébergée est une bêta non commerciale, gérée par le mainteneur du projet, une personne physique établie en France. Cette page n'a pas encore été relue par un juriste.

## Qui est responsable

L'édition hébergée de Krinea (la bêta accessible à une adresse en .onrender.com) est exploitée par le mainteneur du projet, chercheur et développeur indépendant établi en France, en tant que personne physique. Au sens du RGPD, il est le responsable du traitement. Aucune personne morale n'existe à ce jour et aucune offre payante n'est vendue.

Si vous hébergez Krinea vous-même (code libre, licence AGPL-3.0), vous êtes responsable du traitement de votre instance ; la présente politique ne s'y applique pas.

Pour joindre le responsable du traitement, passez par la [page de contact](/contact).

## Ce que nous conservons

### Votre compte

- Votre nom et votre adresse e-mail. Les deux sont nécessaires pour créer un compte.
- Une empreinte de votre mot de passe (Argon2id). Le mot de passe lui-même n'est jamais conservé.
- Si vous vous connectez avec Google : l'identifiant de votre compte Google et l'adresse e-mail vérifiée par Google. Nous ne recevons pas votre mot de passe Google.
- Vos sessions de connexion : un jeton aléatoire conservé dans un cookie HttpOnly pendant 30 jours ; le serveur n'en stocke que l'empreinte SHA-256.
- Les liens de connexion à usage unique envoyés par e-mail : stockés sous forme d'empreinte, valables 20 minutes.
- La langue de l'interface et le nom de votre offre.

### Le contenu de vos revues

Tout ce que vous et votre équipe placez dans une revue :

- les références importées : titres, auteurs, résumés, DOI, mots-clés et autres champs bibliographiques ;
- les PDF téléversés ;
- les décisions de sélection et leurs motifs, les notes et les étiquettes, ainsi que le temps passé sur chaque référence ;
- les formulaires d'extraction et les valeurs saisies ou suggérées ;
- les effectifs PRISMA ;
- un journal d'activité : qui a fait quoi, et quand ;
- les invitations envoyées par e-mail aux membres de l'équipe ;
- des compteurs d'usage de l'IA (nombre de jetons), jamais les textes échangés.

Si vous enregistrez votre propre clé de fournisseur d'IA, elle est chiffrée au repos (Fernet : AES-128-CBC avec HMAC, clé dérivée du secret du serveur), jamais écrite dans les journaux, et vous pouvez la retirer à tout moment.

### Données techniques

Les journaux du serveur, qui contiennent les adresses IP, sont conservés 30 jours à des fins de sécurité (détection des abus, diagnostic des incidents).

## Pourquoi, et sur quelle base légale

| Finalité | Données | Base légale |
|---|---|---|
| Fournir le service (compte, revues, équipe, exports) | Compte et contenu des revues | Exécution du contrat : les [conditions d'utilisation](/terms) |
| Envoyer les liens de connexion et les invitations | Adresse e-mail | Exécution du contrat |
| Sécurité, prévention des abus, diagnostic des incidents | Journaux du serveur, adresses IP, journal d'activité | Intérêt légitime |
| Suggestions et extractions par IA | Titre et résumé, ou texte du PDF, avec les critères ou le formulaire de la revue | Votre consentement, donné à chaque déclenchement par un relecteur |

Le consentement au traitement par IA est donné action par action ; vous le retirez en ne déclenchant plus la fonction ou en supprimant votre clé.

Nous n'utilisons pas vos données à des fins publicitaires, de profilage ou de revente, et nous n'entraînons aucun modèle d'IA avec elles.

## Cookies

Krinea dépose trois cookies, tous nécessaires au fonctionnement du service :

- `krinea_session` : vous maintient connecté (HttpOnly, 30 jours) ;
- un cookie d'état de courte durée pendant la connexion avec Google, qui sécurise cette étape (10 minutes) ;
- un cookie qui mémorise la langue d'interface choisie.

Aucun cookie de mesure d'audience, de publicité ou de pistage. Ces cookies étant strictement nécessaires, aucun bandeau de consentement n'est requis.

## Où vos données sont hébergées et qui les traite

L'application web, l'API, le processus de tâches en arrière-plan et la base de données PostgreSQL tournent chez Render, Inc., dans la région de Francfort (Allemagne, UE). Render effectue des sauvegardes régulières de la base de données. Les PDF téléversés sont stockés avec les données de l'application, dans l'UE ; un espace de stockage objet situé dans l'UE pourra être utilisé plus tard.

Quelques prestataires traitent des données pour notre compte :

| Prestataire | Finalité | Localisation |
|---|---|---|
| Render, Inc. | Hébergement (application, API, tâches, base de données, sauvegardes) | Société américaine ; serveurs à Francfort (UE) |
| Resend | E-mails transactionnels (liens de connexion, invitations) | États-Unis |
| Google | Connexion facultative avec un compte Google | États-Unis |
| Anthropic, Google ou DeepSeek | Suggestions et extractions par IA, uniquement lorsqu'un relecteur les déclenche | Selon le fournisseur, possiblement hors UE |

Certaines de ces sociétés sont établies aux États-Unis. Lorsque des données quittent l'UE, le transfert s'appuie sur les clauses contractuelles types de la Commission européenne ou, le cas échéant, sur le cadre de protection des données UE–États-Unis (Data Privacy Framework).

## Fournisseurs d'IA

Des données ne partent vers un fournisseur d'IA que lorsqu'un utilisateur disposant des droits de relecteur déclenche, dans une revue, une suggestion (sélection) ou une extraction. Krinea transmet alors au fournisseur configuré pour cette revue :

- pour la sélection : le titre et le résumé de la référence, avec les critères de la revue ;
- pour l'extraction : le texte du PDF et le formulaire d'extraction conçu par les auteurs.

Le fournisseur est Anthropic (Claude), Google (Gemini) ou DeepSeek, selon le réglage de la revue. La requête utilise votre propre clé d'API ou, pour les offres payantes lorsqu'elles ouvriront, des clés détenues par le service. Chaque fournisseur applique ses propres conditions : consultez-les avant d'utiliser l'IA sur des documents sensibles.

Les résultats de l'IA sont stockés à part des décisions humaines et ne valent jamais décision. Nous ne conservons que des compteurs de jetons, jamais les textes.

## Combien de temps nous conservons vos données

| Données | Durée |
|---|---|
| Données du compte | Durée de vie du compte |
| Revues et leur contenu | Jusqu'à leur suppression par leur propriétaire |
| Liens de connexion | 20 minutes |
| Sessions | 30 jours |
| Journal d'activité | Avec la revue |
| Journaux du serveur (adresses IP) | 30 jours |
| Sauvegardes | Une période limitée après suppression, selon le cycle de sauvegarde de l'hébergeur |

## Vos droits

Le RGPD vous donne le droit :

- d'accéder aux données que nous détenons sur vous ;
- de les faire rectifier ;
- de les faire effacer ;
- de les recevoir dans un format portable ;
- de vous opposer aux traitements fondés sur l'intérêt légitime ;
- d'introduire une réclamation auprès de la CNIL (France) ou de l'autorité de contrôle de votre pays.

Une grande partie se fait sans nous :

- exportez tout, à tout moment, depuis l'application : RIS, CSV, Excel, PRISMA ;
- le propriétaire d'une revue peut la supprimer depuis sa zone de danger, ce qui efface ses références, PDF, décisions et extractions ;
- retirez votre clé de fournisseur d'IA à tout moment ;
- pour supprimer votre compte, faites-en la demande via la [page de contact](/contact) ; elle est traitée sous 30 jours.

Pour toute autre demande, utilisez la page de contact. Nous pourrons vous demander de confirmer votre identité.

## Sécurité

- TLS chiffre tous les échanges en transit.
- Une seule origine publique : les navigateurs ne parlent jamais directement à l'API.
- Mots de passe hachés avec Argon2id ; jetons de session et de connexion stockés sous forme d'empreinte.
- Clés de fournisseurs d'IA chiffrées au repos.
- Aucun secret n'est jamais écrit dans les journaux.
- Le code est public : chacun peut l'auditer.

Krinea n'a fait l'objet d'aucun audit de sécurité externe et ne détient aucune certification. Nous le disons clairement pour que vous décidiez en connaissance de cause de ce que vous téléversez.

## Mineurs

Krinea s'adresse aux personnes âgées d'au moins 16 ans. Nous ne collectons pas sciemment de données auprès de personnes plus jeunes. Si vous pensez qu'un mineur a créé un compte, signalez-le via la page de contact et nous le supprimerons.

## Modifications de cette politique

Il s'agit de la version 0.1, encore en cours de relecture juridique. Elle évoluera avec le service (nom de domaine définitif, offres payantes, structure juridique). Tout changement important vous sera annoncé dans l'application avant son entrée en vigueur. La date en haut de cette page indique la version en vigueur ; les versions précédentes restent dans l'historique public du code source.
