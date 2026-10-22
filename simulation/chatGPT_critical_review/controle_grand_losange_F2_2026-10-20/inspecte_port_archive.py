"""Diagnostic CAD aux positions de grilles fermees ; aucun operateur FDTD construit.

La connectivite ci-dessous utilise seulement la presence du PEC au milieu
des aretes primaires archivees. Ce n'est PAS une extraction de l'operateur
openEMS (moyennage, end caps du port et coefficients exclus).
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
for n in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[n] = '1'
os.environ['MPLBACKEND'] = 'Agg'
sys.dont_write_bytecode = True
ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
# Meme installation locale que le moteur, uniquement pour charger CSXCAD.
os.environ.setdefault('CSXCAD_INSTALL_PATH', str(SIM.parent / 'outils/openEMS'))
import numpy as np
from CSXCAD import ContinuousStructure

BASE = SIM / 'resultats/pcbway_maille_controlee_v2'
CAS = tuple((a, p) for a in ('diamant_uwb', 'diamant_uwb_x18') for p in ('base_12ns', 'fin_16ns'))
GEL = SIM / 'chatGPT_critical_review/integration_finale_f2/gel_campagne_F2.json'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def exige(c, texte):
    if not c:
        raise ValueError(texte)


def canon_physique(xml):
    props = ET.fromstring(xml).find('ContinuousStructure/Properties')
    for p in props.iter():
        for enfant in list(p):
            if enfant.tag in ('FillColor', 'EdgeColor'):
                p.remove(enfant)
    return ET.tostring(props)


def main():
    sortie = ICI / 'inspection_port_archive.json'
    exige(not sortie.exists(), 'Sortie deja presente')
    gel = json.loads(GEL.read_text(encoding='utf-8'))
    attendus = {**gel['sources_physiques_sha256'], **gel['controles_sha256']}
    avant = {n: sha(SIM / n) for n in attendus}
    exige(len(avant) == 18 and avant == attendus, 'Sources gelees differentes')
    fichiers = {}
    cas = []
    for antenne, profil in CAS:
        dossier = BASE / antenne / profil
        # Liste blanche de quatre profils clos, sans parcours d'autres profils.
        for n in ('simulation_manifest.json', 'entree_openems.xml', 'maillage.npz',
                  'geometrie.json', 'port_ut_1', 'port_it_1', '_calibration_dt/calibration.json'):
            p = dossier / n
            fichiers[p.relative_to(SIM).as_posix()] = sha(p)
        manifeste = json.loads((dossier / 'simulation_manifest.json').read_text(encoding='utf-8'))
        exige(manifeste['etat'] == 'termine', 'Profil non termine')
        xml = (dossier / 'entree_openems.xml').read_bytes()
        arbre = ET.fromstring(xml)
        with np.load(dossier / 'maillage.npz', allow_pickle=False) as z:
            axes = {n: z[n].copy() for n in ('x', 'y', 'z')}
        port = arbre.find("ContinuousStructure/Properties/LumpedElement[@Name='port_resist_1']")
        boite = port.find('Primitives/Box')
        p1 = {n: float(boite.find('P1').get(n.upper())) for n in ('x', 'y', 'z')}
        p2 = {n: float(boite.find('P2').get(n.upper())) for n in ('x', 'y', 'z')}
        u0, h = p1['y'], p2['z']
        # ReadFromXML CSX attend le sous-arbre ContinuousStructure en racine.
        # Extraction exacte du XML ferme : aucun dessin/axe recalcule.
        xml_csx = ET.tostring(arbre.find('ContinuousStructure'), encoding='utf-8', xml_declaration=True)
        extrait = ICI / ('extrait_CSX_' + antenne + '_' + profil + '.xml')
        if extrait.exists():
            exige(extrait.read_bytes() == xml_csx, 'Extraction CSX existante differente')
        else:
            with extrait.open('xb') as f:
                f.write(xml_csx)
        csx = ContinuousStructure()
        erreur = csx.ReadFromXML(str(extrait))
        exige(erreur == '', 'CSX XML : ' + erreur)

        def nom_prop(point, masque):
            prop = csx.GetPropertyByCoordPriority(point, prop_type=masque, markFoundAsUsed=False)
            return None if prop is None else prop.GetName()

        def metal(point):
            return nom_prop(point, 0x004) is not None

        controles = []
        for signe in (-1, 1):
            x = signe * 4.318
            # Segments physiques explicites centre masse -> neck -> via -> B_Cu.
            chemins = (
                ('masse_vers_neck', [(x, u0 + u, h) for u in np.linspace(4.8, 5.5, 29)]),
                ('neck_vers_via', [(x, u0 + u, h) for u in np.linspace(5.3, 5.969, 29)]),
                ('fut_via', [(x, u0 + 5.969, z) for z in np.linspace(0, h, 35)]),
                ('contact_masse_B', [(x, u0 + u, 0) for u in np.linspace(5.6, 6.2, 29)]),
            )
            for nom, points in chemins:
                absents = [list(map(float, p)) for p in points if not metal(p)]
                controles.append(dict(cote=signe, chemin=nom, points=len(points),
                                      points_sans_PEC=absents, continu_aux_points_sondes=not absents))
        signal = [(0., u0 + u, h) for u in np.linspace(0, 7, 71)]
        controle_signal = dict(points=len(signal), points_sans_PEC=[list(p) for p in signal if not metal(p)])
        # Graphe diagnostique de PEC aux milieux d'aretes primaires du bloc SMA.
        xx = axes['x'][(axes['x'] >= -5.588 - 1e-10) & (axes['x'] <= 5.588 + 1e-10)]
        yy = axes['y'][(axes['y'] >= u0 - 1e-10) & (axes['y'] <= u0 + 6.4516 + 1e-10)]
        zz = axes['z'][(axes['z'] >= -1e-10) & (axes['z'] <= h + 1e-10)]
        parents = {}

        def racine(p):
            parents.setdefault(p, p)
            while parents[p] != p:
                parents[p] = parents[parents[p]]
                p = parents[p]
            return p

        def joindre(a, b):
            parents[racine(a)] = racine(b)

        nb_aretes = [0, 0, 0]
        # Les deux plans PEC seulement : aucune enumeration du volume d'air.
        for iz, hauteur in ((0, 0.), (len(zz) - 1, h)):
            for iy, y in enumerate(yy):
                for ix in range(len(xx) - 1):
                    if metal(((xx[ix] + xx[ix + 1]) / 2, y, hauteur)):
                        joindre((ix, iy, iz), (ix + 1, iy, iz)); nb_aretes[0] += 1
            for ix, x in enumerate(xx):
                for iy in range(len(yy) - 1):
                    if metal((x, (yy[iy] + yy[iy + 1]) / 2, hauteur)):
                        joindre((ix, iy, iz), (ix, iy + 1, iz)); nb_aretes[1] += 1
        # Seules les aretes verticales autour des deux vias peuvent etre PEC.
        for ix, x in enumerate(xx):
            for iy, y in enumerate(yy):
                if min(abs(x - 4.318), abs(x + 4.318)) <= .2286 + 1e-10 and abs(y - u0 - 5.969) <= .2286 + 1e-10:
                    for iz in range(len(zz) - 1):
                        if metal((x, y, (zz[iz] + zz[iz + 1]) / 2)):
                            joindre((ix, iy, iz), (ix, iy, iz + 1)); nb_aretes[2] += 1

        def noeud(x, u, z):
            return (int(np.argmin(abs(xx - x))), int(np.argmin(abs(yy - u0 - u))),
                    int(np.argmin(abs(zz - z))))

        references = dict(signal=noeud(0, 0, h), masse_B=noeud(0, 1, 0),
                          masse_G=noeud(-4.318, 3, h), masse_D=noeud(4.318, 3, h))
        connexions = {a + '__' + b: bool(racine(na) == racine(nb))
                      for a, na in references.items() for b, nb in references.items() if a < b}
        # Presence de PEC / resistance sur toutes les aretes verticales du port.
        source_pec = []
        source_R_absente = []
        source_aretes = 0
        for x in axes['x'][(axes['x'] >= p1['x'] - 1e-10) & (axes['x'] <= p2['x'] + 1e-10)]:
            for z in (zz[:-1] + zz[1:]) / 2:
                point = [float(x), u0, float(z)]
                source_aretes += 1
                if metal(point): source_pec.append(point)
                if nom_prop(point, 0x2000) != 'port_resist_1': source_R_absente.append(point)
        sondes = {}
        for nom in ('port_ut_1', 'port_it_1'):
            lignes = []
            with (dossier / nom).open(encoding='utf-8') as flux:
                for _ in range(4): lignes.append(next(flux).rstrip())
            sondes[nom] = lignes
        iz = int(np.searchsorted(axes['z'], h / 2) - 1)
        cas.append(dict(antenne=antenne, profil=profil,
            extraction_CSX=dict(fichier=extrait.name, sha256=sha(extrait),
                usage='Sous-arbre XML existant uniquement ; aucune construction de scene ou de grille'),
            physique_Properties_sans_couleurs_sha256=hashlib.sha256(canon_physique(xml)).hexdigest(),
            port=dict(attributs=port.attrib, P1=p1, P2=p2, priorite=boite.get('Priority'),
                      aretes_verticales_examinees=source_aretes, PEC_interieur_source=source_pec,
                      aretes_source_sans_resistance=source_R_absente),
            controles_chemins_CAD=controles, signal_central_CAD=controle_signal,
            graphe_echantillonne=dict(definition='Presence METAL au milieu des aretes primaires : diagnostic seulement, PAS operateur solveur',
                dimensions_bloc=[len(xx), len(yy), len(zz)], aretes_PEC_xyz=nb_aretes,
                connexions=connexions, points_references={k:list(v) for k,v in references.items()}),
            sondes_entetes=sondes, z_primaire_inferieur_I_mm=float(axes['z'][iz]),
            z_primaire_superieur_I_mm=float(axes['z'][iz+1]),
            z_centre_dual_I_mm=float((axes['z'][iz]+axes['z'][iz+1])/2),
            dt_s=manifeste['execution']['dt_s']))
    apres = {n: sha(SIM / n) for n in attendus}
    exige(avant == apres == attendus, 'Source changee pendant lecture')
    exige(all(sha(SIM / p) == h for p, h in fichiers.items()), 'Preuve changee pendant lecture')
    rapport = dict(schema='inspection_port_CAD_grilles_archivees_v1', script_sha256=sha(__file__),
        python=sys.version, numpy=np.__version__, aucun_Run_Setup_construit=True,
        aucune_lecture_Vivaldi=True, sources18_avant=avant, sources18_apres=apres,
        fichiers_clos_sha256=fichiers, cas=cas,
        limites=['Interrogation de la geometrie CSX et graphe aux milieux des aretes seulement.',
                 'Pas de coefficients ou PEC discret natif openEMS extraits.',
                 'Le graphe ne comprend pas les plaques PEC end caps creees par operateur LumpedElement Caps1.',
                 'Un resultat de connectivite identique ne demontre pas une impedance ou une adaptation identiques.'])
    with sortie.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False, allow_nan=False); f.write('\n')
    print(json.dumps(dict(rapport=str(sortie), sha256=sha(sortie),
        connexions=[dict(antenne=c['antenne'], profil=c['profil'],
            graphe=c['graphe_echantillonne']['connexions'],
            R_absente=len(c['port']['aretes_source_sans_resistance']),
            PEC_dans_source=len(c['port']['PEC_interieur_source'])) for c in cas]), ensure_ascii=False))


if __name__ == '__main__':
    main()
