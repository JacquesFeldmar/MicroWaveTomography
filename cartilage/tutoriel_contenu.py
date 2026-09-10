"""
CONTENU DU TUTORIEL -- les six segments, texte de narration compris.

Ce fichier est le SCRIPT de la video. Il est versionne a cote du code : si une
commande change, c'est ici qu'on le voit, et le verificateur peut controler que
rien n'y cite un programme ou une option disparus.

    python tutoriel_contenu.py              image + sous-titres, sans voix
    python tutoriel_contenu.py --voix       avec ElevenLabs (cle dans
                                            ELEVENLABS_API_KEY)
    python tutoriel_contenu.py --segment 3  ne refaire qu'un segment
    python tutoriel_contenu.py --ecrans     recapturer les copies d'ecran
"""

import argparse
import hashlib
import os
import subprocess
import sys
import time

import tutoriel as T


# La console Windows est souvent en cp1252 : elle ne sait pas ecrire les
# accents du tutoriel et le programme mourait sur un UnicodeEncodeError au
# moment d afficher un titre de segment. On tolere la substitution plutot
# que d interdire les accents.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

PY = sys.executable
ICI = os.path.dirname(os.path.abspath(__file__))
EC = "docs/ecrans"

# ======================================================================
# LES SIX SEGMENTS
# ======================================================================
SEGMENTS = [

 # ------------------------------------------------------------------ 1
 dict(titre="Prise en main", plans=[
  dict(t="titre", titre="Radar cartilage",
       sous="Prise en main du banc, en simulation",
       n="Ce tutoriel montre comment se servir du banc de mesure d'épaisseur. "
         "Tout ce que vous allez voir se fait sans brancher le moindre "
         "matériel."),
  dict(t="tableau", titre="Trois programmes, et rien d'autre",
       entetes=["Programme", "Role", "Cadence"],
       lignes=[["*calibration.py", "produit les corrections", "chaque session"],
               ["*radar.py", "la mesure", "en permanence"],
               ["*qualification.py", "juge l'antenne", "par antenne"],
               ["noyau.py", "bibliotheque partagee", "jamais lancee"]],
       n="Le banc tient en trois programmes. Le premier produit des nombres qui "
         "corrigent chaque mesure. Le deuxième mesure. Le troisième rend un "
         "verdict sur l'antenne, et ne corrige rien."),
  dict(t="console", titre="La distinction qui compte",
       texte="  calibration.py    CORRIGE   -> calibration/*.npz\n"
             "                              applique a chaque mesure\n\n"
             "  qualification.py  JUGE      -> qualification/*.png\n"
             "                              lu une fois, ne corrige rien",
       n="On confond souvent calibration et qualification. La calibration "
         "produit des nombres appliqués en permanence. La qualification produit "
         "un jugement, qu'on lit une fois. Ni le même but, ni la même cadence."),
  dict(t="console", titre="Le mode simule",
       texte="  python radar.py --autotest\n\n"
             "  ... verifie toute la chaine de calcul\n"
             "      de 1 mm de cartilage a 80 mm de plastique\n\n"
             "  VERDICT : REUSSI",
       surligne=[("VERDICT", T.AQUA)],
       n="Commencez toujours par l'autotest. Il vérifie la chaîne de calcul sur "
         "des données synthétiques, sans aucun instrument. S'il échoue, rien "
         "d'autre n'a de sens."),
  dict(t="console", titre="Apprendre sans materiel",
       texte="  L'option --simu remplace le LiteVNA par un instrument simule :\n\n"
             "      directivite du pont        -30 dB\n"
             "      desadaptation source       -14 dB\n"
             "      cable                        2 ns\n"
             "      reflexion propre d'antenne\n"
             "      bruit                      -45 dB\n\n"
             "  Les verdicts sont vrais. Rien n'est branche.",
       n="L'option simu remplace l'instrument par un modèle réaliste. Les "
         "verdicts sont vrais, les modes d'échec aussi. C'est la bonne façon "
         "d'apprendre avant de manipuler des étalons à un demi newton-mètre."),
 ]),

 # ------------------------------------------------------------------ 2
 dict(titre="La calibration guidée", plans=[
  dict(t="titre", titre="Segment 2", sous="La calibration, pas à pas",
       n="La calibration produit les corrections appliquées à chaque mesure. "
         "Lancée sans argument, elle vous guide."),
  dict(t="console", titre="Une commande",
       texte="  python calibration.py --simu\n\n"
             "  ==========================================================\n"
             "    ASSISTANT DE MISE EN ROUTE DU BANC\n"
             "  ==========================================================\n\n"
             "    Cinq etapes. Chacune explique ce qu'elle fait et pourquoi,\n"
             "    puis verifie son propre resultat.",
       n="Sans aucun argument, le programme déroule la mise en route complète, "
         "une étape à la fois. C'est le mode à utiliser tant que la séquence "
         "n'est pas familière."),
  dict(t="console", titre="Une étape",
       texte="  ETAPE 2/5 -- CALIBRATION SOL\n"
             "  ==========================================================\n"
             "    POURQUOI : retire la directivite du pont, la desadaptation\n"
             "               source et la reponse du cable.\n\n"
             "    > Prepare les trois etalons : COURT-CIRCUIT, OUVERT, CHARGE.\n"
             "    > Ils se vissent AU BOUT DU CABLE.\n"
             "    > NE DEPLACE PAS LE CABLE de toute l'operation.\n\n"
             "    [Entree] faire  |  [s] sauter  |  [q] quitter :",
       surligne=[("POURQUOI", T.BLEU), ("NE DEPLACE PAS", T.ORANGE)],
       n="Chaque étape annonce d'abord pourquoi elle existe, ensuite ce qu'il "
         "faut faire. On ne suit correctement une procédure qu'en sachant ce "
         "qu'elle sert à obtenir. Le câble, lui, ne doit plus bouger."),
  dict(t="console", titre="Les trois termes d'erreur",
       texte="  e00      directivite\n"
             "           la fuite du pont vers le recepteur.\n"
             "           Cree le faux echo a distance nulle.\n\n"
             "  e11      desadaptation source\n"
             "           les allers-retours VNA <-> antenne mal adaptee.\n\n"
             "  e10.e01  suivi en reflexion\n"
             "           la reponse du cable et du pont.",
       n="Trois termes d'erreur. La directivité est la fuite interne du pont, "
         "celle qui crée un faux écho à distance nulle et qui fixe le plancher. "
         "La désadaptation produit des échos fantômes. Le suivi en réflexion "
         "fausse les amplitudes."),
  dict(t="console", titre="Le résultat",
       texte="  python calibration.py --sol --simu\n"
             "\n"
             "  TERMES D'ERREUR\n"
             "  ----------------------------------------------------------\n"
             "    directivite                -30.5 dB\n"
             "    desadaptation source       -14.0 dB\n"
             "    suivi en reflexion          -1.4 dB\n"
             "    conditionnement          median 3.5, max 3.5",
       surligne=[("directivite  ", T.BLEU), ("conditionnement", T.AQUA)],
       n="La directivité mesurée donne le niveau du faux écho qui polluait les "
         "mesures. Le conditionnement doit rester petit : au-delà de cinquante, "
         "les étalons ne sont pas assez distincts et l'un d'eux est "
         "probablement mal vissé."),
  dict(t="console", titre="La verification",
       texte="  python calibration.py --verifier --simu\n"
             "\n"
             "  Charge AVANT : median  -30.4 dB\n"
             "  Charge APRES : median  -53.9 dB\n"
             "  Gain de directivite : 23.5 dB\n"
             "\n"
             "  L'echo de fond de couche recherche se situe vers -17 dB.\n"
             "\n"
             "  VERDICT : BON (-45 dB au pire).",
       surligne=[("VERDICT", T.AQUA)],
       n="L'étape suivante revisse la charge et mesure ce que la calibration ne "
         "corrige pas. C'est le plancher réel du système. Il faut qu'il reste "
         "nettement sous l'écho de fond de couche, qui se situe vers moins dix- "
         "sept décibels."),
  dict(t="console", titre="Le plan de reference",
       texte="  python calibration.py --plan 100 200 --simu\n"
             "\n"
             "  Plaque metallique a 100 mm, puis a 200 mm\n"
             "\n"
             "  Pente ...... 0.9983   (doit valoir 1,000)\n"
             "  Offsets .... +702.2 et +702.0 mm\n"
             "  Plan de l'antenne : 702.1 mm",
       surligne=[("Pente", T.BLEU), ("Offsets", T.ORANGE)],
       n="La calibration place l'origine des distances au bout du câble, pas au "
         "plan rayonnant. Une plaque métallique vue à deux distances connues "
         "fait le report. La pente doit valoir un : elle vérifie l'échelle. "
         "L'offset doit être constant : c'est la position du plan de l'antenne."),
  dict(t="console", titre="Le piege",
       texte="  ATTENTION : pente a 2.051\n\n"
             "  Un ecart de plus de 5 % n'est PAS une erreur de plan de\n"
             "  reference. Verifie que les deux distances sont bien celles\n"
             "  que tu crois -- confondre 'a 200 mm' et 'de 200 mm' donne\n"
             "  exactement une pente double.",
       surligne=[("ATTENTION", T.ORANGE), ("pente double", T.ORANGE)],
       n="Un avertissement issu d'une vraie erreur. Reculer la plaque de deux "
         "cents millimètres n'est pas la placer à deux cents millimètres. "
         "Confondre les deux double exactement la pente, et fausse toute la "
         "campagne. Les positions sont donc toujours données en absolu."),
  dict(t="console", titre="La derniere etape",
       texte="  ETAPE 5/5 -- FOND D'ANTENNE\n\n"
             "    POURQUOI : la reflexion propre de l'antenne est ADDITIVE\n"
             "               et absente du modele. Non retiree, elle fausse\n"
             "               l'epaisseur de ~0,4 mm.\n\n"
             "    > Retire la plaque. RIEN devant l'antenne.\n\n"
             "  A tout moment :\n"
             "  python calibration.py --etat      ou en est la calibration\n"
             "  python calibration.py --rejouer   recalcule sans re-acquerir",
       surligne=[("ADDITIVE", T.ORANGE)],
       n="Dernière étape, et elle est distincte de la calibration. La réflexion "
         "propre de l'antenne s'ajoute au signal au lieu de le multiplier : la "
         "calibration ne peut pas la retirer. Il faut la mesurer séparément, "
         "antenne face au vide."),
 ]),

 # ------------------------------------------------------------------ 3
 dict(titre="La mesure", plans=[
  dict(t="titre", titre="Segment 3", sous="Mesurer une épaisseur",
       n="Le banc est calibré. On peut mesurer."),
  dict(t="console", titre="Une mesure",
       texte="  python radar.py --mesure --nom pmma12 --fond fond \\\n"
             "         --milieu pmma --substrat air --max-ep 20\n\n"
             "  --milieu    la couche mesuree\n"
             "  --substrat  ce qu'il y a DERRIERE\n"
             "  --fond      le balayage 'scene vide' a soustraire",
       n="Une mesure demande trois choses : le milieu de la couche, ce qu'il y "
         "a derrière elle, et le fond à soustraire. L'épaisseur maximale "
         "explorée se règle un peu au-dessus de l'attendu."),
  dict(t="console", titre="Deux estimateurs, toujours les deux",
       texte="  A. Deux pics .........   47.369 mm\n"
             "     ecart 76.4 mm (1.47 x la resolution de 52 mm)\n\n"
             "  B. Modele stratifie ..   12.001 mm   (residu 0.0000)\n"
             "     DISTANCE a la 1re surface :    149.9 mm\n\n"
             "  -> NON CONCLUANT. A 1.47 x la resolution, la detection\n"
             "     a deux pics est biaisee : son desaccord est ATTENDU.",
       surligne=[("B. Modele", T.AQUA), ("NON CONCLUANT", T.ORANGE)],
       n="Deux méthodes tournent sur le même balayage. La première cherche deux "
         "pics : elle se trompe ici d'un facteur quatre, et le programme le dit "
         "lui-même. La seconde ajuste le modèle physique et trouve douze "
         "millimètres au micron près."),
  dict(t="console", titre="Pourquoi la première échoue",
       texte="  Resolution = 52 mm dans l'air\n\n"
             "  PMMA de 12 mm  ->  ecart apparent 19 mm\n"
             "                     soit 0,37 x la resolution\n\n"
             "  La detection a deux pics n'est fiable qu'au-dela de\n"
             "  2,5 resolutions. En deca elle rend une valeur\n"
             "  FAUSSE MAIS PLAUSIBLE.",
       surligne=[("FAUSSE MAIS PLAUSIBLE", T.ORANGE)],
       n="La résolution vaut cinquante-deux millimètres. Une plaque de douze "
         "millimètres ne sépare ses deux échos que de dix-neuf. Sous ce seuil, "
         "la détection de pics n'échoue pas franchement : elle rend un nombre "
         "plausible et faux. C'est plus dangereux qu'une erreur visible."),
  dict(t="capture", titre="Le graphe de diagnostic", img=EC + "/radar_mesure.png",
       fleches=[(0.17, 0.55, "profil", "d"), (0.50, 0.30, "LE controle", "d"),
                (0.85, 0.55, "residu de phase", "g")],
       n="Chaque mesure produit ce graphe. À gauche le profil de distance. Au "
         "centre les franges mesurées et le modèle ajusté. À droite le résidu "
         "de phase."),
  dict(t="console", titre="Le seul juge",
       texte="  Si la courbe orange ne suit pas la bleue sur le panneau\n"
             "  central, le chiffre d'epaisseur n'a AUCUNE valeur,\n"
             "  quelle que soit sa vraisemblance.\n\n"
             "      residu < 0,2   ->  exploitable\n"
             "      residu > 0,2   ->  le programme avertit",
       surligne=[("AUCUNE valeur", T.ORANGE)],
       n="Le panneau central est le seul juge. Si le modèle ne se superpose pas "
         "à la mesure, le nombre affiché ne veut rien dire. Le résidu chiffre "
         "cet écart : au-delà de zéro virgule deux, le programme avertit de "
         "lui-même."),
  dict(t="console", titre="Le probleme inverse",
       texte="  python radar.py --mesure --nom eps12 \\\n"
             "         --epaisseur 12.0 --substrat air --fond fond\n\n"
             "  conductivite supposee : 0.0 S/m\n"
             "  eps_r mesure .........    2.600   (residu 0.0000)\n\n"
             "  Reperes : PMMA 2,6 | PTFE 2,1 | verre 6,9",
       surligne=[("eps_r mesure", T.AQUA)],
       n="On peut inverser le problème. Épaisseur connue au pied à coulisse, et "
         "c'est la permittivité que le programme cherche. Sur une plaque de "
         "douze millimètres il doit rendre deux virgule six. C'est la "
         "vérification qui valide toute la chaîne, sans aucune référence "
         "extérieure."),
 ]),

 # ------------------------------------------------------------------ 4
 dict(titre="La fenêtre temps réel", plans=[
  dict(t="titre", titre="Segment 4", sous="Viser, et surveiller",
       n="Le mode direct ne sert pas à produire un chiffre. Il sert à viser."),
  dict(t="film", titre="La fenêtre  —  radar.py --live", img=EC + "/film_live",
       fleches=[(0.53, 0.15, "cadre de lecture", "d"),
                (0.62, 0.03, "bandeau d etat", "d")],
       n="Sans retour visuel continu, on ne peut ni orienter une antenne, ni "
         "voir qu'un objet parasite est entré dans la scène, ni repérer une "
         "dérive. Le cadre de lecture donne l'épaisseur, la distance, le résidu "
         "et la cadence."),
  dict(t="tableau", titre="Les commandes",
       entetes=["Bouton", "Ce qu'il fait"],
       lignes=[["*Tare (fond vide)", "memorise la scene VIDE et l'enregistre"],
               ["Effacer la tare", "revient au signal non corrige"],
               ["*CAPTURER", "balayage brut + image + ligne de journal"],
               ["Pause", "fige l'affichage, l'acquisition continue"],
               ["*Curseur eps_r", "change la permittivite EN DIRECT"],
               ["*Enregistrer", "demarre / arrete une SEQUENCE brute"],
               ["*Rejouer", "rejoue la sequence ICI MEME, puis rend"]],
       n="La tare mémorise la scène vide et l'enregistre, donc elle devient "
         "réutilisable. Capturer garde le balayage brut, une image et une ligne "
         "de journal. Le curseur change la permittivité en direct."),
  dict(t="console", titre="Le curseur, et ce qu'il enseigne",
       texte="  python radar.py --live --milieu pmma --substrat air --max-ep 20\n"
             "\n"
             "  Deplacez le curseur eps_r et regardez l'epaisseur bouger.\n"
             "\n"
             "      d = c . dtau / (2 . racine(eps_r))\n"
             "\n"
             "  Une erreur relative sur eps_r se reporte pour moitie sur\n"
             "  l'epaisseur. Connaitre eps_r a 4 % pres, ou pas, fait un\n"
             "  facteur DIX sur la precision finale.",
       surligne=[("facteur DIX", T.ORANGE)],
       n="Le curseur a un mérite inattendu : il rend tangible la dégénérescence "
         "entre épaisseur et permittivité. Déplacez-le, l'épaisseur suit. C'est "
         "le poste dominant du budget d'erreur de tout le projet."),
  dict(t="console", titre="Le bandeau d'etat",
       texte="  pmma sur air   |   tare posee          <- tout va bien\n\n"
             "  RESIDU ELEVE -- le modele ne decrit pas la mesure\n\n"
             "  Le chiffre d'epaisseur ne s'affiche jamais sans son\n"
             "  indicateur de confiance :   residu   OK 0.0011\n"
             "                              residu   !! 0.4210",
       surligne=[("RESIDU ELEVE", T.ORANGE), ("!!", T.ORANGE)],
       n="Le bandeau supérieur passe en résidu élevé dès que le modèle "
         "décroche. Et le résidu porte toujours un préfixe, OK ou deux points "
         "d'exclamation. On ne lit jamais une épaisseur sans savoir si on peut "
         "y croire."),
 ]),

 # ------------------------------------------------------------------ 5
 dict(titre="Enregistrer et rejouer", plans=[
  dict(t="titre", titre="Segment 5", sous="Les donnees brutes",
       n="Tout ce que le banc mesure est conservé, et conservé brut."),
  dict(t="console", titre="Enregistrer une séquence",
       texte="  Depuis la fenetre : bouton Enregistrer, puis ARRETER.\n\n  En ligne de commande :\n\n  python radar.py --enregistre --nom essai --duree 20 \\\n"
             "         --milieu pmma --substrat air --max-ep 20\n\n"
             "  ... affichage en direct pendant l'enregistrement ...\n\n"
             "  240 balayages BRUTS enregistres : mesures/essai.npz",
       n="Le mode enregistrement capture une séquence de balayages avec leurs "
         "instants, tout en affichant en direct. Un format unique sert pour une "
         "mesure isolée comme pour une séquence."),
  dict(t="console", titre="Rejouer",
       texte="  Depuis la fenetre : bouton Rejouer -- la sequence repasse\n  dans la meme fenetre, puis le direct reprend.\n\n  Hors ligne :\n\n  python radar.py --rejeu --nom essai \\\n"
             "         --milieu pmma --substrat air --max-ep 20\n\n"
             "  --vitesse 1   temps reel\n"
             "  --vitesse 0   le plus vite possible\n\n"
             "  Rejoue comme si l'instrument etait la.",
       n="Le rejeu restitue la séquence à sa cadence d'origine, comme si "
         "l'instrument était branché. On peut ré-analyser, mettre au point sans "
         "matériel, et comparer deux traitements sur exactement les mêmes "
         "données."),
  dict(t="console", titre="Pourquoi brut",
       texte="  Les donnees enregistrees sont NON CALIBREES.\n\n"
             "  On peut donc les recalculer plus tard avec :\n"
             "      une meilleure calibration\n"
             "      un meilleur modele d'etalons\n"
             "      un meilleur traitement\n\n"
             "  C'est exactement ce que la calibration embarquee du\n"
             "  LiteVNA interdit : elle detruit l'information a\n"
             "  l'acquisition.",
       surligne=[("NON CALIBREES", T.AQUA), ("detruit l'information", T.ORANGE)],
       n="Les données sont enregistrées non calibrées, volontairement. On peut "
         "ainsi les recalculer des mois plus tard avec une meilleure "
         "calibration. La calibration embarquée de l'appareil, elle, détruit "
         "l'information au moment de l'acquisition."),
 ]),

 # ------------------------------------------------------------------ 6
 dict(titre="Qualifier l'antenne", plans=[
  dict(t="titre", titre="Segment 6", sous="Un verdict, pas une correction",
       n="Dernier programme. Il ne corrige rien : il juge si l'antenne "
         "convient."),
  dict(t="capture", titre="Le ringing", img=EC + "/qualif_ringing.png",
       fleches=[(0.30, 0.75, "plancher instrumental", "d")],
       n="Le signal mesuré est le produit de convolution de la réponse de "
         "l'antenne et de celle de la cible. Une antenne résonante sonne, et "
         "cette traînée se superpose à l'écho de fond de couche, déjà quatorze "
         "décibels plus bas."),
  dict(t="console", titre="Le verdict porte sur le ringing NET",
       texte="  python qualification.py --ringing --simu\n"
             "\n"
             "   standoff     mesure   echo ideal   ringing net\n"
             "     100 mm      -32.1        -38.4         6.3 dB\n"
             "     150 mm      -41.7        -52.0        10.3 dB\n"
             "\n"
             "  La zone grise du graphe est le PLANCHER INSTRUMENTAL :\n"
             "  les jupes de la fenetre d'apodisation.\n"
             "  Sans cette soustraction on confondrait un artefact de\n"
             "  traitement avec un defaut d'antenne.",
       surligne=[("PLANCHER INSTRUMENTAL", T.BLEU)],
       n="Le verdict porte sur le ringing net, c'est-à-dire la traînée mesurée "
         "moins le plancher instrumental. Ce plancher est dû à la fenêtre "
         "d'apodisation, pas à l'antenne. Sans cette soustraction on "
         "condamnerait une bonne antenne pour un artefact de calcul."),
  dict(t="capture", titre="Le centre de phase",
       img=EC + "/qualif_centre_phase.png",
       fleches=[(0.78, 0.45, "en mm de cartilage", "g")],
       n="Une plaque métallique est un réflecteur parfait connu. Le résidu de "
         "phase, après retrait d'une droite, est donc exactement la fonction de "
         "transfert de l'antenne. Le panneau de droite le convertit en "
         "épaisseur de cartilage équivalente."),
  dict(t="console", titre="Seule la courbure nuit",
       texte="  python qualification.py --centre-phase --simu\n"
             "\n"
             "  La partie LINEAIRE du residu est un simple retard :\n"
             "  elle est absorbee par le plan de reference.\n"
             "\n"
             "      excursion lineaire de 10 mm  ->  0,094 mm\n"
             "\n"
             "  Seule la COURBURE biaise la mesure.",
       surligne=[("LINEAIRE", T.AQUA), ("COURBURE", T.ORANGE)],
       n="Un point souvent mal compris : la partie linéaire du résidu n'est "
         "qu'un retard, absorbée par le réglage du plan de référence. Une "
         "excursion linéaire de dix millimètres ne coûte que neuf centièmes de "
         "millimètre. Seule la courbure biaise réellement la mesure."),
  dict(t="titre", titre="Pour commencer",
       sous="python radar.py --autotest   puis   python calibration.py --simu",
       n="Pour commencer, lancez l'autotest, puis la calibration en mode "
         "simulé. Toute la séquence est détaillée dans le guide d'utilisation, "
         "section prise en main."),
 ]),
]


# ======================================================================

def etat():
    """Dit, segment par segment, ce qui est a jour et ce qui ne l'est pas.

    Une generation interrompue laisse des segments d'une execution
    precedente. Sans ce controle on croit avoir une video a jour alors
    qu'elle melange deux epoques.
    """
    print("=" * 74)
    print("  ETAT DE LA VIDEO")
    print("=" * 74)
    ref = os.path.getmtime(__file__)
    perimes = []
    print(f"  {'segment':<28}{'duree':>8}{'voix':>7}  etat")
    print("  " + "-" * 60)
    for i, seg in enumerate(SEGMENTS, 1):
        f = SORTIE_SEG(i)
        if not os.path.exists(f):
            print(f"  {i}. {seg['titre']:<25}{'--':>8}{'--':>7}  ABSENT")
            perimes.append(i)
            continue
        d = T.duree_de(f)
        mt = os.path.getmtime(f)
        # un segment est a jour si tous ses plans sont plus anciens que lui
        # le segment est fait de plans muets OU commentes : on prend
        # le jeu qui existe reellement, sinon tout parait manquant
        plans = [_nom_plan(i, j, True) if os.path.exists(_nom_plan(i, j, True))
                 else _nom_plan(i, j, False)
                 for j in range(1, len(seg["plans"]) + 1)]
        manque = [p for p in plans if not os.path.exists(p)]
        vieux = [p for p in plans if os.path.exists(p)
                 and os.path.getmtime(p) > mt + 1]
        # voix : un plan est sonorise si son audio est en cache
        sonores = 0
        for p in seg["plans"]:
            h = hashlib.sha256(p["n"].encode("utf-8")).hexdigest()[:16]
            if os.path.exists(os.path.join(T.VOIX, f"voix_{h}.mp3")):
                sonores += 1
        marque = f"{sonores}/{len(seg['plans'])}"
        if manque or vieux:
            etiq = "A REFAIRE"
            perimes.append(i)
        elif mt < ref - 1:
            etiq = "anterieur au script"
            perimes.append(i)
        else:
            etiq = "a jour"
        print(f"  {i}. {seg['titre']:<25}{d:7.1f}s{marque:>7}  {etiq}")
    final = os.path.join(SORTIE, "tutoriel.mp4")
    if os.path.exists(final):
        plus_vieux = min(os.path.getmtime(SORTIE_SEG(i))
                         for i in range(1, len(SEGMENTS) + 1)
                         if os.path.exists(SORTIE_SEG(i)))
        plus_jeune = max(os.path.getmtime(SORTIE_SEG(i))
                         for i in range(1, len(SEGMENTS) + 1)
                         if os.path.exists(SORTIE_SEG(i)))
        fm = os.path.getmtime(final)
        print(f"\n  tutoriel.mp4 : {T.duree_de(final):.0f} s, "
              + ("A JOUR" if fm >= plus_jeune - 1 else
                 "PERIME (des segments sont plus recents que lui)"))
    else:
        print("\n  tutoriel.mp4 : ABSENT")
    if perimes:
        print(f"\n  A refaire : segments {', '.join(map(str, perimes))}")
        # toujours conseiller --tout : sans lui la generation s interrompt
        if len(perimes) == len(SEGMENTS):
            print("      python tutoriel_contenu.py --tout --voix")
        else:
            print("      python tutoriel_contenu.py --tout --voix --segment "
                  + " ".join(map(str, perimes)))
    else:
        print("\n  Tout est a jour.")
    return perimes


def capture_ecrans():
    """Recapture les QUATRE copies d'ecran depuis les programmes reels.

    Le fond d'antenne est refait en premier, sur la scene vide : sans lui,
    le direct affiche un residu eleve et une epaisseur nulle -- une image
    de panne, qui donnerait du tutoriel une idee fausse.

    Les figures de qualification ne s'ecrivent pas ou l'on veut : les
    programmes les deposent dans qualification/, on les recopie ensuite.
    """
    import shutil

    print("  Recapture des copies d'ecran...")
    dossier = os.path.join(ICI, EC)
    os.makedirs(dossier, exist_ok=True)
    env = dict(os.environ, MPLBACKEND="Agg")

    def lance(argv, quoi):
        # Plusieurs modes attendent une validation au clavier a chaque
        # etape du montage : sans entree, ils meurent sur un EOFError.
        r = subprocess.run([PY] + argv, cwd=ICI, env=env,
                           capture_output=True, text=True,
                           input=chr(10) * 12)
        if r.returncode != 0:
            print("  ECHEC (%s) : %s" % (quoi, (r.stderr or "")[-200:]))
        return r.returncode == 0

    # 1. le fond, indispensable a tout le reste
    lance(["radar.py", "--mesure", "--nom", "fond", "--simu", "vide",
           "--sans-graphe"], "fond d'antenne")

    # 2. le direct, AVEC le fond
    lance(["radar.py", "--live", "--simu", "pmma12@150",
           "--milieu", "pmma", "--substrat", "air", "--max-ep", "20",
           "--fond", "fond", "--portee", "400",
           "--capture-ecran", EC + "/radar_live.png"], "fenetre temps reel")

    # 3. la mesure quantitative : le graphe a trois panneaux
    if lance(["radar.py", "--mesure", "--nom", "pmma12", "--simu",
              "pmma12@150", "--milieu", "pmma", "--substrat", "air",
              "--max-ep", "20", "--fond", "fond"], "mesure"):
        src = os.path.join(ICI, "mesures", "pmma12.png")
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dossier, "radar_mesure.png"))

    # 4. les deux verdicts de qualification
    for mode, nom, cible in (("--ringing", "ringing_antenne1",
                              "qualif_ringing.png"),
                             ("--centre-phase", "centre_phase_antenne1",
                              "qualif_centre_phase.png")):
        if lance(["qualification.py", mode, "--nom", "antenne1", "--simu"],
                 mode):
            src = os.path.join(ICI, "qualification", nom + ".png")
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(dossier, cible))

    # 5. la sequence animee du direct : la plaque va et vient, ce qui fait
    #    bouger la courbe et les deux pics tandis que l epaisseur, elle, ne
    #    bouge pas -- c est la demonstration la plus parlante du banc.
    import math
    scenes = ",".join("pmma12@%.0f" % (152.5 + 32.5 * math.sin(
        2 * math.pi * k / 120)) for k in range(120))
    lance(["radar.py", "--live", "--simu", scenes,
           "--milieu", "pmma", "--substrat", "air", "--max-ep", "20",
           "--fond", "fond", "--portee", "400",
           "--film", EC + "/film_live", "--images", "120"], "film du direct")

    manquantes = [f for f in ("radar_live.png", "radar_mesure.png",
                              "qualif_ringing.png", "qualif_centre_phase.png")
                  if not os.path.exists(os.path.join(dossier, f))]
    if manquantes:
        print("  ATTENTION : manquent encore " + ", ".join(manquantes))
    else:
        print("  fait : les quatre copies d'ecran sont a jour.")


def _a_jour(mp4):
    """Un plan deja encode est-il reutilisable tel quel ?

    Il l est si son mp4 existe et est plus recent que les deux modules
    qui definissent le contenu et sa mise en images. Sans
    ce controle, chaque relance refaisait les trente-six plans depuis zero,
    ce qui interdit toute reprise apres interruption.
    """
    if not os.path.exists(mp4):
        return False
    t = os.path.getmtime(mp4)
    for dep in (__file__, T.__file__):
        if os.path.exists(dep) and os.path.getmtime(dep) > t:
            return False
    return True


def _duree_estimee(texte):
    """Sans voix : ~15 caracteres par seconde, minimum 4 s."""
    return max(4.0, len(texte) / 15.0)


def _nom_plan(i, j, avec_voix):
    """Le fichier d un plan porte son mode dans son nom.

    Un plan encode muet et le meme plan commente sont deux fichiers
    differents. Sans cette distinction, la reprise jugeait "deja fait" un
    plan muet alors que l on demandait la version sonore : la synthese
    n etait jamais appelee et la video restait silencieuse. Les deux
    versions coexistent, donc repasser d un mode a l autre ne rejette
    jamais le travail deja fait.
    """
    return os.path.join(T.TRAVAIL, "s%02dp%02d%s.mp4"
                        % (i, j, "v" if avec_voix else ""))


def _plans_manquants(avec_voix=False, voulus=None):
    """Les plans qui restent a encoder, sous forme (segment, plan).

    voulus restreint le decompte aux segments demandes : sans cela, un
    --tout --segment 6 attendrait indefiniment les cinq autres.
    """
    reste = []
    for i, seg in enumerate(SEGMENTS, 1):
        if voulus and i not in voulus:
            continue
        for j in range(1, len(seg["plans"]) + 1):
            mp4 = _nom_plan(i, j, avec_voix)
            if not _a_jour(mp4):
                reste.append((i, j))
    return reste


def _lance_detache(args_enfant):
    """Lance une tentative dans un groupe de processus separe.

    Ce qui interrompt la generation emporte tout le groupe attache a la
    console : lors du premier essai, le superviseur est mort en meme temps
    que son enfant, ce qui lui interdisait de relancer. En placant l enfant
    dans son propre groupe, le superviseur survit et peut enchainer.
    """
    drapeaux = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    journal = os.path.join(T.TRAVAIL, "generation.log")
    with open(journal, "w", encoding="utf-8", errors="replace") as f:
        proc = subprocess.Popen([sys.executable, "-u", __file__] + args_enfant,
                                stdout=f, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL,
                                creationflags=drapeaux)
        # L enfant ecrit dans un fichier, pas sur le terminal : sans ce
        # suivi, l utilisateur ne voit rien pendant plusieurs minutes et
        # croit le programme bloque. On relit le journal au fil de l eau.
        with open(journal, encoding="utf-8", errors="replace") as lecture:
            reste = ""
            while True:
                fini = proc.poll() is not None
                reste += lecture.read()
                *lignes, reste = reste.replace(chr(13), chr(10)).split(chr(10))
                for ligne in lignes:
                    if ligne.strip():
                        print("   " + ligne.strip(), flush=True)
                if fini:
                    break
                time.sleep(0.4)
            if reste.strip():
                print("   " + reste.strip(), flush=True)
    return proc.returncode


def superviseur(args_enfant, essais=12):
    """Relance la generation jusqu a ce qu elle soit complete.

    Le processus de generation s interrompt parfois sans message, sans trace
    et avec un code de sortie nul : ni ffmpeg, ni Pillow, ni la memoire ne
    sont en cause -- chacun tient des centaines d iterations isole, seul le
    melange meurt, au hasard, apres quinze a trente plans. Plutot que de
    laisser l utilisateur relancer a la main, on supervise : chaque tentative
    conserve les plans deja encodes, donc chacune avance, et l ensemble
    aboutit en trois ou quatre passages. Les commentaires deja synthetises
    sont en cache : une relance ne refacture rien.
    """
    sonore = "--voix" in args_enfant
    voulus = None
    if "--segment" in args_enfant:
        k = args_enfant.index("--segment") + 1
        voulus = []
        while k < len(args_enfant) and args_enfant[k].isdigit():
            voulus.append(int(args_enfant[k]))
            k += 1
    depart = len(_plans_manquants(sonore, voulus))
    for k in range(1, essais + 1):
        reste = _plans_manquants(sonore, voulus)
        if not reste:
            break
        print(chr(10) + "  === tentative %d/%d -- %d plan(s) restant(s) sur %d ==="
              % (k, essais, len(reste), depart))
        _lance_detache(args_enfant)
    reste = _plans_manquants(sonore, voulus)
    if reste:
        print(chr(10) + "  ECHEC : %d plan(s) toujours absent(s) apres %d tentatives."
              % (len(reste), essais))
        print("  Relancer la meme commande : chaque passage avance.")
        return 1
    # dernier passage : tous les plans sont la, il ne reste que l assemblage
    print(chr(10) + "  === tous les plans sont encodes -- assemblage ===")
    _lance_detache(args_enfant)
    return 0


def _tout_en_cache(voulus=None):
    """Tous les commentaires necessaires sont-ils deja sur le disque ?"""
    for i, sg in enumerate(SEGMENTS, 1):
        if voulus and i not in voulus:
            continue
        for pl in sg["plans"]:
            h = hashlib.sha256(pl["n"].encode("utf-8")).hexdigest()[:16]
            f = os.path.join(T.VOIX, "voix_%s.mp3" % h)
            if not (os.path.exists(f) and os.path.getsize(f) > 1000):
                return False
    return True


def achete_les_voix(voix_nom=None):
    """Synthetise les trente-six commentaires, et rien d autre.

    Separer l achat de l audio de la fabrication de la video repond a un
    probleme concret : la generation s interrompt, et si le cache audio ne
    survit pas, chaque relance refacture ce qui a deja ete paye. Ici les
    appels sont faits une fois, verifies un par un, et le bilan dit
    exactement ce qui est sur le disque. La video se fabrique ensuite sans
    aucun appel reseau.
    """
    os.makedirs(T.VOIX, exist_ok=True)
    cle = T.nettoie_cle(os.environ.get("ELEVENLABS_API_KEY"))
    if not cle:
        print("  ELEVENLABS_API_KEY absente de l environnement.")
        return 1
    ok, msg = T.controle_cle(cle)
    print("  Cle : " + msg)
    if not ok:
        return 1
    voix_id, nom = T.choisir_voix(cle, voix_nom)
    print("  Voix : %s  (%s)" % (nom, voix_id))
    ok, msg = T.essai_synthese(cle, voix_id)
    print("  Essai : " + msg)
    if not ok:
        return 1
    total = sum(len(sg["plans"]) for sg in SEGMENTS)
    faits, achetes, echecs = 0, 0, []
    for i, sg in enumerate(SEGMENTS, 1):
        for j, pl in enumerate(sg["plans"], 1):
            h = hashlib.sha256(pl["n"].encode("utf-8")).hexdigest()[:16]
            f = os.path.join(T.VOIX, "voix_%s.mp3" % h)
            faits += 1
            if os.path.exists(f) and os.path.getsize(f) > 1000:
                print("  %2d/%d  s%02dp%02d  en cache   %6.1f Ko"
                      % (faits, total, i, j, os.path.getsize(f) / 1024),
                      flush=True)
                continue
            try:
                T.voix(pl["n"], f, voix_id, cle)
                achetes += 1
                print("  %2d/%d  s%02dp%02d  SYNTHETISE %6.1f Ko"
                      % (faits, total, i, j, os.path.getsize(f) / 1024),
                      flush=True)
            except Exception as e:
                echecs.append((i, j, str(e)[:200]))
                print("  %2d/%d  s%02dp%02d  ECHEC : %s"
                      % (faits, total, i, j, str(e)[:120]), flush=True)
    # On compte les commentaires NECESSAIRES, pas les fichiers presents :
    # une reformulation du texte change son empreinte et laisse derriere
    # elle des mp3 orphelins, qui feraient croire a tort que tout est la.
    besoins = set()
    for sg in SEGMENTS:
        for pl in sg["plans"]:
            besoins.add(hashlib.sha256(pl["n"].encode("utf-8")).hexdigest()[:16])
    presents = {x[5:-4] for x in os.listdir(T.VOIX) if x.startswith("voix_")}
    sur_disque = len(besoins & presents)
    orphelins = presents - besoins
    print()
    print("  %d commentaire(s) achete(s) cette fois, %d fichier(s) sur le disque"
          % (achetes, sur_disque))
    if sur_disque < total:
        print("  ATTENTION : %d manquant(s) -- le cache ne retient pas tout,"
              % (total - sur_disque))
        print("  la video sera partiellement muette et une relance refacturera.")
        return 1
    if orphelins:
        print("  %d commentaire(s) devenu(s) inutile(s) apres une reformulation,"
              % len(orphelins))
        print("  conserve(s) dans %s au cas ou le texte reviendrait en arriere."
              % T.VOIX)
    print("  Tout est paye et conserve. La video se fait maintenant hors ligne :")
    print("      python tutoriel_contenu.py --tout --voix")
    return 0


def construis(segments_voulus=None, avec_voix=False, voix_nom=None):
    os.makedirs(T.TRAVAIL, exist_ok=True)
    os.makedirs(T.VOIX, exist_ok=True)
    cle = T.nettoie_cle(os.environ.get("ELEVENLABS_API_KEY"))
    voix_id = None
    if avec_voix and _tout_en_cache(segments_voulus):
        # Tous les commentaires sont deja payes et sur le disque : aucun
        # appel reseau n est necessaire, donc aucune cle non plus. La video
        # se fabrique hors ligne, et une interruption ne coute rien.
        print("  Commentaires : tous en cache, aucun appel reseau.")
        avec_cle = False
    elif avec_voix:
        avec_cle = True
        if not cle:
            print("  ELEVENLABS_API_KEY absente de l'environnement.")
            print()
            print("  Dans CETTE fenetre (disparait a la fermeture) :")
            print('      PowerShell :  $env:ELEVENLABS_API_KEY = "sk_..."')
            print('      Git Bash   :  export ELEVENLABS_API_KEY="sk_..."')
            print()
            print("  De facon permanente -- il faut alors ouvrir une NOUVELLE")
            print("  fenetre, un processus ne relit jamais son environnement")
            print("  une fois demarre :")
            print('      setx ELEVENLABS_API_KEY "sk_..."')
            sys.exit(1)
        ok, msg = T.controle_cle(cle)
        print(f"  Cle : {msg}")
        if not ok:
            print()
            print("  Rien n'a ete lance : mieux vaut echouer maintenant qu'au")
            print("  trente-septieme appel. Verifie la valeur, puis :")
            print('      $env:ELEVENLABS_API_KEY = "sk_..."')
            sys.exit(1)
        voix_id, nom = T.choisir_voix(cle, voix_nom)
        print(f"  Voix : {nom}  ({voix_id})")
        ok, msg = T.essai_synthese(cle, voix_id)
        print(f"  Essai : {msg}")
        if not ok:
            print()
            print("  Rien n'a ete lance. Les plans deja synthetises sont")
            print("  conserves : rien ne sera refacture au prochain essai.")
            sys.exit(1)
        deja = len([x for x in os.listdir(T.VOIX)
                    if x.startswith("voix_")]) if os.path.isdir(T.VOIX) else 0
        if deja:
            print(f"  Cache : {deja} plan(s) deja synthetise(s), non refactures.")

    total = len(SEGMENTS)
    fichiers_seg = []
    for i, seg in enumerate(SEGMENTS, 1):
        if segments_voulus and i not in segments_voulus:
            f = os.path.join(SORTIE_SEG(i))
            if os.path.exists(f):
                fichiers_seg.append(f)
            continue
        print(f"\n  --- segment {i}/{total} : {seg['titre']} ---")
        plans = []
        for j, p in enumerate(seg["plans"], 1):
            base = os.path.join(T.TRAVAIL, f"s{i:02d}p{j:02d}")
            img = base + ".png"
            mp4 = _nom_plan(i, j, avec_voix)
            if _a_jour(mp4):
                plans.append(mp4)
                print("      plan %d/%d (deja fait)"
                      % (j, len(seg["plans"])),
                      end=chr(13), flush=True)
                continue
            if p["t"] == "film":
                # plan anime : on habille la sequence, puis on l encode
                dossier = os.path.join(T.TRAVAIL, f"film_s{i:02d}p{j:02d}")
                n_img = T.film_habille(p["titre"],
                                       os.path.join(ICI, p["img"]),
                                       p["n"], i, total, dossier,
                                       p.get("fleches", ()))
                audio = None
                if avec_voix:
                    h = hashlib.sha256(p["n"].encode("utf-8")).hexdigest()[:16]
                    audio = os.path.join(T.VOIX, f"voix_{h}.mp3")
                    if not avec_cle and not os.path.exists(audio):
                        raise RuntimeError(
                            "commentaire absent du cache : " + audio)
                    T.voix(p["n"], audio, voix_id, cle)
                T.plan_film_vers_mp4(dossier, audio, _duree_estimee(p["n"]),
                                     mp4)
                plans.append(mp4)
                print("      plan %d/%d (%d images)"
                      % (j, len(seg["plans"]), n_img), end=chr(13), flush=True)
                continue
            if p["t"] == "titre":
                im = T.image_titre(p["titre"], p["sous"], p["n"], i, total)
            elif p["t"] == "console":
                im = T.image_console(p["titre"], p["texte"], p["n"], i, total,
                                     p.get("surligne", ()))
            elif p["t"] == "capture":
                im = T.image_capture(p["titre"], os.path.join(ICI, p["img"]),
                                     p["n"], i, total, p.get("fleches", ()))
            else:
                im = T.image_tableau(p["titre"], p["entetes"], p["lignes"],
                                     p["n"], i, total)
            im.save(img)

            audio = None
            if avec_voix:
                h = hashlib.sha256(p["n"].encode("utf-8")).hexdigest()[:16]
                audio = os.path.join(T.VOIX, f"voix_{h}.mp3")
                if not avec_cle and not os.path.exists(audio):
                    raise RuntimeError(
                        "commentaire absent du cache alors que le mode hors "
                        "ligne a ete choisi : " + audio + chr(10)
                        + "  Relancer : python tutoriel_contenu.py --audio")
                T.voix(p["n"], audio, voix_id, cle)
            try:
                T.plan_vers_mp4(img, audio, _duree_estimee(p["n"]), mp4)
            except Exception as e:
                print("")
                print("  ECHEC au plan {} du segment {} :".format(j, i))
                print(str(e)[:900])
                raise
            plans.append(mp4)
            print(f"      plan {j}/{len(seg['plans'])}", end="\r", flush=True)
        seg_mp4 = SORTIE_SEG(i)
        T.concatene(plans, seg_mp4)
        d = T.duree_de(seg_mp4)
        print(f"      {len(plans)} plans, {d:5.1f} s -> "
              f"{os.path.basename(seg_mp4)}")
        fichiers_seg.append(seg_mp4)

    # Toujours reconstruire le final a partir des segments PRESENTS, meme si
    # la generation a ete partielle -- et le dire.
    fichiers_seg = [SORTIE_SEG(i) for i in range(1, len(SEGMENTS) + 1)
                    if os.path.exists(SORTIE_SEG(i))]
    if len(fichiers_seg) < len(SEGMENTS):
        manquants = [i for i in range(1, len(SEGMENTS) + 1)
                     if not os.path.exists(SORTIE_SEG(i))]
        print(f"\n  ATTENTION : segments absents {manquants} -- la video sera"
              " incomplete.")
    final = os.path.join(SORTIE, "tutoriel.mp4")
    T.concatene(fichiers_seg, final)
    d = T.duree_de(final)
    print(f"\n  VIDEO : {final}")
    print(f"  Duree : {int(d // 60)} min {int(d % 60):02d} s"
          + ("" if avec_voix else "   (sans voix -- relancer avec --voix)"))


def SORTIE_SEG(i):
    return os.path.join(SORTIE, f"segment_{i}.mp4")


SORTIE = T.SORTIE


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voix", action="store_true")
    ap.add_argument("--nom-voix", default=None,
                    help="nom ou identifiant de voix ElevenLabs")
    ap.add_argument("--segment", type=int, nargs="+", default=None)
    ap.add_argument("--audio", action="store_true",
                    help="synthetiser les commentaires, sans faire la video")
    ap.add_argument("--tout", action="store_true",
                    help="relance jusqu a ce que la video soit complete")
    ap.add_argument("--etat", action="store_true",
                    help="dit quels segments sont a jour")
    ap.add_argument("--diag", action="store_true",
                    help="teste la cle et dit ce qu elle permet")
    ap.add_argument("--ecrans", action="store_true",
                    help="recapturer les copies d'ecran d'abord")
    a = ap.parse_args()
    if a.etat:
        sys.exit(1 if etat() else 0)
    if a.diag:
        cle = os.environ.get('ELEVENLABS_API_KEY', '').strip()
        if not cle:
            print('  ELEVENLABS_API_KEY absente de l environnement.')
            sys.exit(1)
        sys.exit(0 if T.diagnostic(cle) else 1)
    if a.audio:
        sys.exit(achete_les_voix(a.nom_voix))
    if a.ecrans:
        capture_ecrans()
    if a.tout:
        # on repasse a l enfant les memes options, sans --tout ni --ecrans
        enfant = []
        if a.voix:
            enfant.append("--voix")
        if a.nom_voix:
            enfant += ["--nom-voix", a.nom_voix]
        if a.segment:
            enfant += ["--segment"] + [str(x) for x in a.segment]
        sys.exit(superviseur(enfant))
    construis(a.segment, a.voix, a.nom_voix)
