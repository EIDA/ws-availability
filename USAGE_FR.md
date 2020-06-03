# RESIF DC availability FDSN Web Service Documentation

## Description

Ce webservice donne la disponibilité des enregistrements sismiques du centre d'archivage du réseau RESIF. Il fournit des informations sous forme de plages temporelles détaillées.

Il y a deux méthodes de requêtes pour ce service :

/extent

Produit une liste des plages temporelles disponibles selon les canaux (network, station, location, channel, quality) et l'intervalle de temps demandés.

/query

Produit une liste des plages temporelles continues disponibles selon les canaux (network, station, location, channel, quality) et l'intervalle de temps demandés.


## Formats de sorties disponibles

  - text
  - json
  - geocsv

## Utilisation de la requête

Les paramètres de la requête sont joints par une esperluette "&", sans espace (voir les exemples de requêtes). Les valeurs par défaut sont indiquées en majuscules.
Au moins une station ou un réseau doit être précisé.

# /extent usage

    /extent? [channel-options] [date-range-options] [merge-options] [sort-options] [format-options]

    où :

    channel-options      ::  [net=<network>] & [sta=<station>] & [loc=<location>] & [cha=<channel>] & [quality=<quality>]
    date-range-options   ::  [starttime=<date|duration>] & [endtime=<date|duration>]
    merge-options        ::  [merge=<quality|samplerate|overlap>]
    sort-options         ::  [orderby=<NSLC_TIME_QUALITY_SAMPLERATE|timespancount|timespancount_desc|latestupdate|latestupdate_desc>]
    display-options      ::  [includerestricted=<true|FALSE>] & [limit=<number>]
    format-options       ::  [format=<TEXT|geocsv|json|request|sync|zip>]


# /query usage

    /query? [channel-options] [date-range-options] [merge-options] [sort-options] [display-options] [format-options]

    où :

    channel-options      ::  [net=<network>] & [sta=<station>] & [loc=<location>] & [cha=<channel>] & [quality=<quality>]
    date-range-options   ::  [starttime=<date|duration>] & [endtime=<date|duration>]
    merge-options        ::  [merge=<quality|samplerate|overlap>] & [mergegaps=<number>]
    sort-options         ::  [orderby=<NSLC_TIME_QUALITY_SAMPLERATE|latestupdate|latestupdate_desc>]
    display-options      ::  [show=<latestupdate>] & [includerestricted=<true|FALSE>] & [limit=<number>]
    format-options       ::  [format=<TEXT|geocsv|json|request|sync|zip>]


    les valeurs par défaut sont en majuscules


## Exemples de requêtes

### avec /extent
<a href="http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15">http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15</a>

<a href="http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&show=latestupdate&orderby=timespancount">http://ws.resif.fr/fdsnws/availability/1/extent?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&show=latestupdate&orderby=timespancount</a>


### avec /query

<a href="http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15">http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15</a>

<a href="http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&merge=samplerate&mergegaps=36000">http://ws.resif.fr/fdsnws/availability/1/query?net=FR&sta=CREF,OGCE&cha=EH?&start=2018-01-01&end=2018-11-15&merge=samplerate&mergegaps=36000</a>


## Descriptions détaillées de chaque paramètre de la requête

### Format autorisé pour la station
Les quatre paramètres (network, station, location, channel) déterminent les canaux d’intérêt.

| Paramètre  | Exemple | Discussion                                                                    | Valeur par défaut |
| :--------- | :------ | :---------------------------------------------------------------------------- | :----- |
| net[work]  | FR      | Nom du réseau sismique.                                                       | aucune |
| sta[tion]  | CIEL    | Nom de la station.                                                            | aucune |
| loc[ation] | 00      | Code de localisation. Utilisez loc=-- pour des codes de localisations vides.  | aucune |
| cha[nnel]  | HHZ     | Code de canal.                                                                | aucune |
| quality    | M       | Code de qualité SEED : D, M, Q, R.                                            | aucune |


#### Jokers et listes d'arguments

  - Jokers : le point d’interrogation __?__ représente n'importe quel caractère unique, alors que l'astérisque __*__ représente zéro caractère ou plus.

  - Listes : plusieurs éléments peuvent également être récupérés à l'aide d'une liste séparée par des virgules. Les jokers peuvent être inclus dans la liste.

Par exemple, pour le code des canaux : channel=EH?,BHZ

#### Détails sur la nomenclature des codes

  - NETWORK = 1 à 2 caractères alphanumériques. Un groupe de points de mesures.
  - STATION = 1 à 5 caractères alphanumériques. Un site de mesure dans un réseau.
  - CHANNEL = 3 caractères qui désignent : la fréquence d'échantillonnage et la bande de fréquence du capteur, le type de l'instrument, l'orientation physique de la composante.
  - LOCATION = 2 caractères qui permettent de distinguer plusieurs flux de données d'un même canal

### Formats autorisés pour l'intervalle de temps
La définition de l'intervalle de temps peut prendre différentes formes :

#### Avec une date de début et une date de fin

| Paramètre   | Exemple             | Discussion     | Valeur par défaut |
| :---------- | :------------------ | :--------------| :----- |
| start[time] | 2015-08-12T01:00:00 | Date de début. | aucune |
| end[time]   | 2015-08-13T01:00:00 | Date de fin.   | aucune |

**Exemple :**

...starttime=2015-08-12T01:00:00&endtime=2015-08-13T01:00:00...

#### Combinaison d'une date et d'une durée en secondes

| Paramètre   | Exemple             |                Discussion             | Valeur par défaut |
| :---------- | :------------------ | :-------------------------------------| :----- |
| start[time] | 2015-08-12T01:00:00 | Date de début.                        | aucune |
| end[time]   | 7200                | Durée du signal exprimée en secondes. | aucune |

**Exemple :**

...starttime=2015-08-12T01:00:00&endtime=7200...

L'exemple précédent spécifie une date pour le paramètre start[time] et 7200 secondes pour le paramètre end[time].

#### Combinaison du mot-clé "currentutcday" avec une date ou bien une durée en secondes

Le mot-clé "currentutcday" signifie exactement minuit de la date du jour (heure UTC). Il peut être utilisé avec les paramètres start[time] et end[time].

| Paramètre   | Exemple       |                 Discussion          | Valeur par défaut |
| :---------- | :------------ | :---------------------------------- | :----- |
| start[time] | 7200          | Date ou durée exprimée en secondes. | aucune |
| end[time]   | currentutcday | Minuit (UTC) de la date du jour.    | aucune |

**Exemples :**

1) ...starttime=currentutcday&endtime=7200...<br/>
2) ...starttime=7200&endtime=currentutcday...

Le premier exemple désigne les 2 heures après minuit (heure UTC) du jour actuel.
Le second exemple désigne les 2 dernières heures avant minuit (heure UTC) du jour actuel.

### Options de fusion

| Paramètre       | Exemples   | Discussion                                                                         |
| :-------------- | :--------- | :--------------------------------------------------------------------------------- |
| merge           |            | Liste de paramètres séparés par des virgules (exemple merge=quality,samplerate).   |
|                 | quality    | Les périodes de qualités différentes sont fusionnées.                              |
|                 | samplerate | Les périodes de fréquences d'échantillonnage différentes sont fusionnées.          |
|                 | overlap    | Non applicable.                                                                    |

###  Options de sortie

| Paramètre  | Exemples | Discussion                                                                                                |
| :--------- | :------- | :-------------------------------------------------------------------------------------------------------- |
| format     | json    | Format de sortie. Valeurs autorisées : text (par défaut, avec les entêtes), geocsv, json, sync, request et zip.  |
| includerestricted     | false | Affiche ou non les données restreintes.                                                                 |
| limit      | integer  | Limite le nombre de lignes en sortie.                                                                           |

### Options de tri

| Paramètre  | Exemples                     | Discussion                                                                      |
| :--------- | :--------------------------- | :------------------------------------------------------------------------------ |
| orderby    |                              | Range les lignes par :                                                          |
|            | nslc_time_quality_samplerate | network, station, location, channel, période de temps, quality, sample-rate (par défaut) |
|            | timespancount (avec extent)  | nombre de périodes de temps (du plus petit au plus grand), network, station, location, channel, période de temps, quality, sample-rate |
|            | timespancount_desc (avec extent)| nombre de périodes de temps (du plus grand au plus petit), network, station, location, channel, période de temps, quality, sample-rate |
|            | latestupdate                 | date de mise à jour (du plus ancien au plus récent), network, station, location, channel, période de temps, quality, sample-rate |
|            | latestupdate_desc            | date de mise à jour (du plus récent au plus ancien), network, station, location, channel, période de temps, quality, sample-rate |

<br/>

## Paramètres additionnels pour /query

### Options de fusion

| Paramètre       | Exemple  | Discussion                                                            |
| :-------------- | :------- | :-------------------------------------------------------------------- |
| mergegaps       | 86400.0 (1 jour) | Les périodes de temps qui sont séparées par des gaps plus petits ou égaux à la valeur donnée sont fusionnées. |

### Options d'affichage

| Paramètre     | Exemple       | Discussion                                                                |
| :------------ | :------------ | :------------------------------------------------------------------------ |
| show          |               | Liste de paramètres séparés par des virgules (exemple show=latestupdate). |
|               | latestupdate  | Affiche la date de mise à jour des données.                               |

<br/>

## Formats des dates et des heures

    YYYY-MM-DDThh:mm:ss[.ssssss] ex. 1997-01-31T12:04:32.123
    YYYY-MM-DD ex. 1997-01-31 (une heure de 00:00:00 est supposée)

    avec :

    YYYY    :: quatre chiffres de l'année
    MM      :: deux chiffres du mois (01=Janvier, etc.)
    DD      :: deux chiffres du jour du mois (01 à 31)
    T       :: séparateur date-heure
    hh      :: deux chiffres de l'heure (00 à 23)
    mm      :: deux chiffres des minutes (00 à 59)
    ss      :: deux chiffres des secondes (00 à 59)
    ssssss  :: un à six chiffres des microsecondes en base décimale (0 à 999999)

