*Dernière mise à jour : 12 octobre 2026*

## En bref

- Vos clés API de fournisseurs d'IA sont chiffrées avant d'atteindre la base de données, jamais écrites dans les journaux, affichées masquées, et supprimables en un clic.
- La clé de chiffrement n'existe que dans la configuration du serveur, pas dans la base : une copie de la base seule ne révèle pas vos clés.
- Rien n'est envoyé à un fournisseur d'IA tant qu'un relecteur ne le déclenche pas, et alors seulement le texte nécessaire à cette tâche.
- Tout tourne à Francfort (UE). Les échanges entre votre navigateur et Krinea sont chiffrés par TLS ; l'application web joint l'API par le réseau privé de l'hébergeur.
- Le code est public. Chacun peut lire comment c'est fait, ligne par ligne.

## Comment vos clés API sont traitées

Quand vous collez une clé Anthropic, Google ou DeepSeek, l'API la chiffre avec un chiffrement symétrique authentifié (Fernet : AES-128 en mode CBC avec signature HMAC-SHA256) avant de la stocker. La clé de chiffrement est dérivée d'un secret qui n'existe que dans la configuration de l'hébergement ; le serveur refuse de démarrer si ce secret est absent, trop court ou laissé à une valeur d'exemple. La clé est déchiffrée en mémoire, le temps d'une requête vers le fournisseur, et seulement quand vous ou un relecteur de votre équipe demandez une suggestion ou une extraction.

Ce que nous ne faisons jamais avec votre clé : l'écrire dans les journaux, l'afficher à nouveau en entier (vous ne voyez que les premiers et derniers caractères), la partager entre comptes, ou l'utiliser pour autre chose que les appels que vous déclenchez. Vous pouvez la remplacer ou la retirer à tout moment depuis le panneau IA ou vos réglages. La retirer supprime la valeur chiffrée.

Si vous préférez ne stocker aucune clé, vous pourrez utiliser les crédits inclus dans les offres payantes quand elles ouvriront, ou héberger Krinea sur votre propre serveur.

## Ce qui parvient à un fournisseur d'IA

Seulement quand un relecteur le déclenche, et seulement pour la revue concernée :

- sélection sur titre et résumé : les champs bibliographiques de la référence (titre, auteurs, année, revue, mots-clés, résumé), avec la question de la revue et ses critères d'inclusion et d'exclusion ;
- sélection sur texte intégral : les mêmes éléments, plus le texte du PDF de la référence ;
- extraction : le texte du PDF, avec la question de la revue et le formulaire d'extraction.

Seul le fournisseur choisi pour cette revue est contacté. Krinea conserve la réponse du fournisseur (la suggestion et sa justification, ou les valeurs extraites et leurs citations) et, pour l'extraction, le texte du PDF transmis, afin que chaque valeur puisse être vérifiée à la source. Ces éléments sont stockés à part des décisions humaines ; une suggestion ne compte jamais comme une décision. L'usage est mesuré en comptant les jetons. La [politique de confidentialité](/privacy) donne le détail.

## Comptes et sessions

Les mots de passe sont hachés avec Argon2id et jamais stockés en clair. Les sessions reposent sur un jeton aléatoire conservé dans un cookie HttpOnly ; le serveur n'en garde que l'empreinte SHA-256, et les sessions expirées sont supprimées. Les liens de connexion envoyés par e-mail sont à usage unique, expirent après 20 minutes et sont supprimés au bout d'un jour. Avec la connexion Google, aucun mot de passe ne transite : nous conservons l'identifiant du compte Google et l'adresse e-mail vérifiée.

La première fois qu'une adresse e-mail est vérifiée, par un lien de connexion ou par Google, tout mot de passe défini auparavant sur ce compte est supprimé et ses autres sessions sont fermées. Une personne qui aurait inscrit votre adresse avant vous ne peut donc pas garder l'accès à votre compte.

## Où tout cela tourne

L'application web, l'API, le processus de tâches en arrière-plan et la base PostgreSQL tournent chez Render, région de Francfort (Allemagne, UE). Les échanges entre votre navigateur et Krinea sont chiffrés par TLS (HTTPS). Les navigateurs ne parlent qu'à l'application web, qui relaie les requêtes vers l'API par le réseau privé de l'hébergeur. Les liens contenus dans les e-mails sont construits à partir de l'adresse configurée du site, jamais à partir de celle qu'annonce une requête. Les liens de connexion et les invitations sont envoyés depuis une boîte aux lettres chez OVHcloud (France, UE). La base est sauvegardée régulièrement par l'hébergeur. Supprimer une revue supprime aussi ses PDF.

## Ce qui n'est pas encore en place

Krinea n'a pas fait l'objet d'un audit de sécurité externe ni d'une certification. L'authentification à deux facteurs n'est pas encore disponible. Nous le disons clairement plutôt que de laisser croire le contraire ; les deux sont prévus avant l'ouverture des offres payantes.

## Signaler une vulnérabilité

Si vous trouvez une faille, signalez-la en privé, jamais dans un ticket public :

- par e-mail à contact@krinea.org, ou
- par le signalement privé de vulnérabilités de GitHub : onglet Security de [github.com/aymardino/krinea](https://github.com/aymardino/krinea), puis « Report a vulnerability ».

Laissez-nous un délai raisonnable pour corriger avant toute divulgation. Nous accusons réception sous cinq jours ouvrés et vous créditerons si vous le souhaitez. Ne testez pas l'instance hébergée sans nous prévenir. Les versions prises en charge et la politique complète figurent dans le fichier `SECURITY.md` du dépôt.
