*Dernière mise à jour : 9 octobre 2026*

## En bref

- Vos clés API de fournisseurs d'IA sont chiffrées avant d'atteindre la base de données, jamais écrites dans les journaux, affichées masquées, et supprimables en un clic.
- La clé de chiffrement n'existe que dans la configuration du serveur, pas dans la base : une copie de la base seule ne révèle pas vos clés.
- Rien n'est envoyé à un fournisseur d'IA tant qu'un relecteur ne le déclenche pas, et alors seulement le texte nécessaire à cette tâche.
- Tout tourne à Francfort (UE), en HTTPS, derrière une seule origine publique.
- Le code est public. Chacun peut lire comment c'est fait, ligne par ligne.

## Comment vos clés API sont traitées

Quand vous collez une clé Anthropic, Google ou DeepSeek, l'API la chiffre avec un chiffrement symétrique authentifié (Fernet : AES-128 en mode CBC avec signature HMAC-SHA256) avant de la stocker. La clé de chiffrement est dérivée d'un secret qui n'existe que dans la configuration de l'hébergement. La clé est déchiffrée en mémoire, le temps d'une requête vers le fournisseur, et seulement quand vous ou un relecteur de votre équipe demandez une suggestion ou une extraction.

Ce que nous ne faisons jamais avec votre clé : l'écrire dans les journaux, l'afficher à nouveau en entier (vous ne voyez que les premiers et derniers caractères), la partager entre comptes, ou l'utiliser pour autre chose que les appels que vous déclenchez. Vous pouvez la remplacer ou la retirer à tout moment depuis le panneau IA ou vos réglages. La retirer supprime la valeur chiffrée.

Si vous préférez ne stocker aucune clé, vous pourrez utiliser les crédits inclus dans les offres payantes quand elles ouvriront, ou héberger Krinea sur votre propre serveur.

## Ce qui parvient à un fournisseur d'IA

Seulement quand un relecteur le déclenche, et seulement pour la revue concernée : le titre et le résumé d'une référence (tri) ou le texte d'un PDF (extraction), avec les critères ou le formulaire d'extraction de la revue. Seul le fournisseur choisi pour cette revue est contacté. Krinea stocke la réponse du fournisseur à part des décisions humaines ; une suggestion ne compte jamais comme une décision. L'usage est mesuré en jetons, jamais en conservant les textes envoyés.

## Comptes et sessions

Les mots de passe sont hachés avec Argon2id et jamais stockés en clair. Les sessions reposent sur un jeton aléatoire conservé dans un cookie HttpOnly ; le serveur n'en garde que l'empreinte SHA-256. Les liens de connexion envoyés par e-mail sont à usage unique et expirent après 20 minutes. Avec la connexion Google, aucun mot de passe ne transite : nous conservons l'identifiant du compte Google et l'adresse e-mail vérifiée.

## Où tout cela tourne

L'application web, l'API, le processus de tâches en arrière-plan et la base PostgreSQL tournent chez Render, région de Francfort (Allemagne, UE). Tout le trafic est chiffré en transit (TLS). Les navigateurs ne parlent qu'à l'application web, qui relaie les requêtes vers l'API sur un réseau privé. La base est sauvegardée régulièrement par l'hébergeur.

## Ce qui n'est pas encore en place

Krinea n'a pas fait l'objet d'un audit de sécurité externe ni d'une certification. L'authentification à deux facteurs n'est pas encore disponible. Nous le disons clairement plutôt que de laisser croire le contraire ; les deux sont prévus avant l'ouverture des offres payantes.

## Signaler une vulnérabilité

Si vous trouvez une faille, dites-le-nous en privé via la [page de contact](/contact) plutôt que dans un ticket public, et laissez-nous un délai raisonnable pour corriger avant toute divulgation. Nous accuserons réception et vous créditerons si vous le souhaitez.
