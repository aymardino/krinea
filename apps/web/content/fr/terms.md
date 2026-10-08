*Version 0.1 — en cours de relecture juridique. Dernière mise à jour : 8 octobre 2026.*

## En bref

- Tamis est un logiciel libre. Ces conditions ne concernent que l'édition hébergée, en bêta. Si vous l'installez chez vous, c'est la licence AGPL-3.0 qui s'applique.
- L'édition hébergée est gratuite aujourd'hui et exploitée par le mainteneur, une personne physique. Elle est fournie en l'état, sans garantie de disponibilité.
- Vous restez propriétaire de tout ce que vous déposez dans Tamis. Nous ne l'utilisons que pour faire fonctionner le service. Vous pouvez tout exporter ou supprimer à tout moment.
- Les réponses de l'IA sont des suggestions. Vous restez responsable de votre revue.
- Il faut avoir au moins 16 ans, protéger ses identifiants et respecter les droits sur les PDF déposés.
- Le droit français s'applique. En cas de problème, on commence par en discuter.

## Le service

Tamis est un établi de travail libre pour les revues systématiques : import de références, dédoublonnage, sélection en équipe, extraction de données par une IA qui cite ses sources, rapport PRISMA 2020, export. Voir la page [à propos](/about).

L'application est publiée sous licence AGPL-3.0 ; son moteur, le paquet Python `tamis_core`, sous licence MIT. Le code source est sur [github.com/aymardino/systematic_review](https://github.com/aymardino/systematic_review).

Les présentes conditions régissent uniquement l'**édition hébergée** : l'instance bêta exploitée par le mainteneur, servie aujourd'hui depuis une adresse en .onrender.com et hébergée chez Render à Francfort (Allemagne, UE). « Nous » désigne le mainteneur, chercheur et développeur indépendant établi en France, qui exploite le service en tant que personne physique. Aucune personne morale n'existe à ce jour. Voir les [mentions légales](/legal).

Si vous auto-hébergez Tamis (Docker Compose, blueprint Render), ces conditions ne s'appliquent pas : les licences régissent votre usage, et vous répondez de votre instance et de ses utilisateurs.

En créant un compte ou en utilisant l'édition hébergée, vous acceptez ces conditions.

## Votre compte

- Vous devez avoir au moins 16 ans.
- Indiquez une adresse e-mail exacte : c'est par elle que vous vous connectez et que nous vous informons sur le service. Voir la [politique de confidentialité](/privacy).
- Protégez vos identifiants. Vous répondez de ce qui est fait depuis votre compte. Si vous pensez qu'il a été compromis, prévenez-nous via la [page de contact](/contact).
- Un compte par personne. Ne partagez pas un compte : invitez plutôt vos collaborateurs dans la revue.
- Vous pouvez vous connecter avec Google. Les conditions de Google s'appliquent à cette connexion ; nous ne recevons que l'identifiant de votre compte Google et votre adresse e-mail vérifiée.

## Usage acceptable

Utilisez le service pour un travail de recherche, de façon licite et loyale. Il est interdit de :

- déposer ou partager un contenu illicite, diffamatoire ou portant atteinte aux droits d'autrui ;
- déposer un PDF que vous n'avez pas le droit d'utiliser : les licences des éditeurs et les conditions d'accès ouvert en décident, et nous ne pouvons pas le vérifier à votre place ;
- aspirer, sonder ou attaquer le service, ou l'utiliser pour attaquer des tiers ;
- contourner les limites, quotas ou contrôles d'accès, ou accéder aux revues d'autres personnes sans y avoir été invité ;
- revendre l'édition hébergée ou la présenter comme votre propre service.

Le code est public : l'auditer et signaler une faille sur GitHub est bienvenu. Tester l'instance hébergée sans nous prévenir ne l'est pas.

## Vos contenus

Vous êtes propriétaire des références, PDF, décisions, notes, formulaires, extractions et autres contenus que vous placez dans Tamis. Nous ne revendiquons aucun droit sur eux.

Vous nous accordez une licence limitée au fonctionnement du service : stocker et sauvegarder vos contenus, les afficher aux personnes que vous invitez, les traiter quand vous le demandez (dédoublonnage, exports, fonctions IA). Elle prend fin quand vous supprimez les contenus ou votre compte, sous réserve du cycle de sauvegardes décrit dans la [politique de confidentialité](/privacy).

Vous pouvez tout exporter à tout moment (RIS, CSV, Excel, PRISMA). Le propriétaire d'une revue peut la supprimer depuis sa zone de danger ; cela efface ses références, PDF, décisions et extractions. La suppression du compte se demande via la [page de contact](/contact) et intervient sous 30 jours.

Les suggestions de l'IA sont conservées à part des décisions humaines et ne valent jamais décision. Vous êtes responsable de votre revue : critères, nombre de lecteurs, résolution des conflits, données extraites, résultats rapportés. Tamis est un outil, pas une autorité méthodologique.

## Fonctions IA

Rien n'est envoyé à un fournisseur d'IA tant qu'un utilisateur disposant des droits de relecteur ne déclenche pas une suggestion ou une extraction dans une revue. Le titre et le résumé (sélection) ou le texte du PDF (extraction), avec les critères ou le formulaire de la revue, sont alors transmis au fournisseur configuré pour cette revue : Anthropic (Claude), Google (Gemini) ou DeepSeek.

Aujourd'hui, les fonctions IA utilisent votre propre clé d'API. Elle est chiffrée au repos, jamais écrite dans les journaux, et vous pouvez la retirer à tout moment. Vous êtes responsable de cette clé, des coûts que le fournisseur vous facture et du respect de ses conditions. Nous conservons des compteurs d'usage (nombre de jetons, jamais les textes). Sur les offres payantes, lorsqu'elles ouvriront, des clés détenues par le service pourront être utilisées à la place.

Une réponse d'IA peut être fausse. Vérifiez-la ; n'incluez, n'excluez et n'extrayez jamais sur la seule foi d'une suggestion.

## Offres et paiement

L'édition hébergée est gratuite aujourd'hui. Les offres Pro et Institution sont annoncées sur la [page des tarifs](/pricing), mais ne sont pas commercialisées tant que la facturation et les documents juridiques correspondants ne sont pas publiés. À leur ouverture, les prix seront affichés sur [/pricing](/pricing) avant toute souscription. Aucun paiement ne vous sera jamais demandé sans une souscription explicite de votre part à une offre payante.

## Disponibilité et évolutions

L'édition hébergée est une bêta, fournie en l'état et dans la mesure du possible, sans garantie de disponibilité. Nous pouvons effectuer des maintenances, modifier ou retirer des fonctions, fixer des limites et déplacer le service vers une autre adresse (un vrai nom de domaine viendra).

Si nous arrêtons l'édition hébergée, ou la modifions au point d'en retirer un élément essentiel, nous vous en informerons au moins 60 jours à l'avance, par e-mail ou dans l'application, et une fenêtre d'export restera ouverte pendant toute cette période. Le logiciel restant disponible sous AGPL-3.0, vous pourrez l'auto-héberger et y réimporter vos exports.

## Responsabilité

L'édition hébergée est fournie « en l'état » et « selon disponibilité », sans garantie d'aucune sorte, dans les limites permises par la loi. C'est une bêta non commerciale exploitée par un particulier. Nous ne garantissons ni l'absence d'erreurs, ni l'absence de perte de données, ni l'adéquation à un usage particulier. Conservez vos propres exports.

Dans les limites permises par la loi, nous ne répondons pas des dommages indirects, des pertes de données ou de temps de recherche, ni des conséquences de vos choix méthodologiques ou des réponses de l'IA. Rien ici n'exclut la responsabilité qui ne peut l'être en droit français, notamment en cas de faute lourde, de dol ou de dommage corporel.

Aucun audit de sécurité externe ni aucune certification n'a encore été réalisé. Les mesures de sécurité sont décrites dans la [politique de confidentialité](/privacy), et le code est public : chacun peut l'auditer.

## Résiliation

Vous pouvez arrêter à tout moment : exportez vos données, supprimez vos revues et demandez la suppression de votre compte via la [page de contact](/contact).

Nous pouvons suspendre ou fermer un compte qui enfreint ces conditions, notamment en cas d'abus, de contenu illicite ou d'attaque contre le service. Dans la mesure du possible, nous vous préviendrons d'abord et vous laisserons le temps d'exporter. En cas d'urgence, par exemple une attaque en cours, nous pouvons agir immédiatement et nous expliquer ensuite. Après la fermeture, vos données sont supprimées comme indiqué dans la [politique de confidentialité](/privacy).

## Droit applicable et litiges

Ces conditions sont régies par le droit français. Le service hébergé est publié depuis la France.

En cas de réclamation, contactez-nous d'abord via la [page de contact](/contact) : la plupart des problèmes se règlent à l'amiable. À défaut d'accord, le litige relève des tribunaux français compétents, sans préjudice des règles impératives de protection des consommateurs de votre pays de résidence.

## Modification des conditions

Nous pourrons mettre à jour ces conditions, en particulier à l'ouverture des offres payantes ou à la création d'une personne morale. Toute modification substantielle sera annoncée par e-mail ou dans l'application avant son entrée en vigueur ; si vous ne l'acceptez pas, exportez vos données et fermez votre compte. La version en vigueur est toujours disponible sur [/terms](/terms), avec la [politique de confidentialité](/privacy) et les [mentions légales](/legal).
