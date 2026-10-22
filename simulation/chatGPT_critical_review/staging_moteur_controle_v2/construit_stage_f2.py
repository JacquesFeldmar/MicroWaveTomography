"""Assemble une copie COMPLETE autonome de F1 avec maillage10, sans l'importer."""
import ast
import hashlib
from pathlib import Path
import re

ICI=Path(__file__).resolve().parent
SIM=ICI.parents[1]
F1=SIM/'fdtd.py'
PROTO=SIM/'chatGPT_critical_review/diagnostic_grand_n34/prototype_maillage_controle/proposition_10_interpolations_sma_libres/construit_prototype_exact.py'
SORTIE=ICI/'modifies/fdtd_maille_controlee.py'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fonction(texte,nom):
    noeud=next(n for n in ast.parse(texte).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==nom)
    return ast.get_source_segment(texte,noeud)


def remplace_une(texte,a,b):
    if texte.count(a)!=1:raise ValueError('Remplacement non unique :'+a[:100])
    return texte.replace(a,b)


def main():
    assert sha(F1)=='3ef9e608e993e4adf3ca735e0f533c4e6927c30b57ba388bf639bb5b65e2ac34'
    assert sha(PROTO)=='6bcefc15238f1989948a43253a9e3cbb4660b260fe9b5cf54fdf314e82595252'
    if SORTIE.exists():raise FileExistsError(SORTIE)
    texte=F1.read_text(encoding='utf-8')
    prototype=PROTO.read_text(encoding='utf-8')
    texte=remplace_une(texte,'from dataclasses import asdict','from dataclasses import asdict, replace')
    texte=remplace_une(texte,'import json\n','import json\nimport math\n')
    constantes='''
NOM_MOTEUR = 'maillage_controle_v2'
NIVEAUX = {
    'base': dict(mailles_par_lambda=16, mailles_par_lambda_air=16, maille_min=.15),
    'fin': dict(mailles_par_lambda=24, mailles_par_lambda_air=16, maille_min=.10),
}


def _configuration_base(m):
    return all(getattr(m, k) == v for k, v in NIVEAUX['base'].items())


def _reglages_controles(montage, mod):
    m = montage.maillage
    if mod.NOM not in ('diamant_uwb', 'diamant_uwb_x18', 'vivaldi_tomographie'):
        raise ValueError('moteur controle reserve aux trois PCB de production')
    if (m.mailles_par_lambda < 16 or m.mailles_par_lambda_air != 16 or
            not 0 < m.maille_min <= .15 or m.rapport_max != 1.5 or m.marge_pml != 8):
        raise ValueError('resolution F2 inconnue ou plus grossiere ; air16, rapport1.5, PML8 imposes')
    h = float(mod.cotes()['h'])
    normale = int(math.ceil(h/m.maille_min))
    if normale % 2 == 0:
        normale += 1
    diametres = [float(d) for _, _, d in mod.vias_mm()]
    if not diametres or len(set(diametres)) != 1:
        raise ValueError('vias de diametre commun requis pour cette politique')
    via = 2*int(math.ceil((diametres[0]/(.8*m.maille_min))/2))
    return dict(lambda_substrat=m.mailles_par_lambda, normal=normale,
                via=via, sma_max_mm=m.maille_min)
'''
    auxiliaires='\n\n'+constantes
    renommages={'unique':'_unique_controle','ligne_exacte':'_ligne_exacte',
        'largeur_locale':'_largeur_locale','subdivisions':'_subdivisions_controle',
        'gradue_plancher':'_gradue_plancher','arêtes_rectilignes':'_aretes_rectilignes'}
    def adapte(s):
        s=s.replace('F._uniques','_uniques').replace('F._fusionne','_fusionne').replace('F.verifie_maillage','verifie_maillage').replace('F.marge_air','marge_air').replace('F._proprietes_matiere','_proprietes_matiere')
        for a,b in renommages.items():s=re.sub(r'\b'+re.escape(a)+r'\b',b,s)
        return s.replace('K.','connectique.')
    for nom in renommages:
        auxiliaires+='\n\n'+adapte(fonction(prototype,nom))
    corps=fonction(prototype,'construit')
    debut=corps.index('    interfaces, dielectriques, ports, definitions =')
    fin=corps.index('    F.verifie_maillage(csx, air, 1.5)')
    corps=corps[debut:fin]
    corps=corps.replace('    interfaces, dielectriques, ports, definitions = F._proprietes_matiere(csx)\n','')
    a=corps.index('    # Boite physique reelle,')
    b=corps.index('    droits_x, droits_u =')
    corps=corps[:a]+'''    boite = np.asarray(boite_pcb, dtype=float)
    interieurs = {axe: [float(boite_domaine[0,i]-garde), float(boite_domaine[1,i]+garde)]
                  for i,axe in enumerate('xyz')}
'''+corps[b:]
    corps=corps.replace("            k = int(np.ceil((h/3)/min(p['sma_max_mm'], h/p['normal'])))",
                         "            k = int(np.ceil((h/3)/p['sma_max_mm']))")
    corps=adapte(corps)
    applique='''def _applique_grille_controlee(montage, mod, csx, boite_pcb, boite_domaine,
                               interfaces, dielectriques, *, grille_base=None):
    from CSXCAD.SmoothMeshLines import SmoothMeshLines
    import connectique
    p = _reglages_controles(montage, mod)
    niveau = 'base' if _configuration_base(montage.maillage) else 'fin'
'''+corps+'''    verifie_maillage(csx, air, 1.5)
    if not _ligne_exacte(g['x'], 0.):
        raise ValueError('Ux0 primaire absent')
    dz = g[normal][(g[normal] >= 0.) & (g[normal] <= h)]
    if len(dz)-1 != p['normal'] or np.min(abs((dz[:-1]+dz[1:])/2-h/2)) > 1e-14:
        raise ValueError('I h/2 dual non respecte')
    return g
'''
    auxiliaires+='\n\n'+applique
    controles='''
def _boite_primitives(csx):
    boites = [np.asarray(pr.GetBoundBox(), dtype=float)
              for prop in csx.GetAllProperties()
              if not prop.GetName().startswith(('port_ut_', 'port_it_', 'port_excite_'))
              for pr in prop.GetAllPrimitives()]
    return np.array([np.min([b[0] for b in boites], axis=0),
                     np.max([b[1] for b in boites], axis=0)])


def _verifie_non_grossissement(grossier, fin, zones):
    for axe, intervalles in zones.items():
        a, b = grossier[axe], fin[axe]
        for lo, hi in intervalles:
            t = np.unique(np.r_[lo, hi, a[(a>lo)&(a<hi)], b[(b>lo)&(b<hi)]])
            milieux = (t[:-1]+t[1:])/2
            da = np.diff(a)[np.clip(np.searchsorted(a,milieux,side='right')-1,0,len(a)-2)]
            db = np.diff(b)[np.clip(np.searchsorted(b,milieux,side='right')-1,0,len(b)-2)]
            if np.any(db > da*(1+1e-8)):
                raise ValueError('grossissement local F2 sur PCB/bloc : '+axe)


def politique_maillage(montage, mod, csx):
    """Metadonnees quantitatives verifiables, derivees des vrais axes."""
    import connectique
    p = _reglages_controles(montage, mod)
    d = mod.cotes()
    verticale = mod.NOM == 'vivaldi_tomographie'
    normal, propagation = ('y','z') if verticale else ('z','y')
    h = float(d['h'])
    u0 = 0. if verticale else -float(d['carte_w'])/2
    grille = {a: np.asarray(csx.GetGrid().GetLines(a),dtype='<f8') for a in 'xyz'}
    faces = grille[normal][(grille[normal]>=0.)&(grille[normal]<=h)]
    return dict(nom=NOM_MOTEUR,configuration={k:getattr(montage.maillage,k) for k in NIVEAUX['base']},
        seed_base=NIVEAUX['base'].copy(),reglages=p,
        normales_mm=[0.,h],axe_normal=normal,axe_propagation=propagation,
        bloc_normal_mm=[-h/3,4*h/3],bloc_propagation_mm=[u0-h,u0+h],
        bloc_sma_x_mm=[-connectique.MASSE_EXTERIEUR_MM,connectique.MASSE_EXTERIEUR_MM],
        bloc_sma_u_mm=[u0-h,max(u+connectique.PASTILLE_DIAMETRE_MM/2 for _,u,_ in mod.vias_mm())],
        U_x0_primaire_exact=bool(np.any(grille['x']==0.)),
        I_dual_hsur2_ecart_mm=float(np.min(abs((faces[:-1]+faces[1:])/2-h/2))),
        cellules_normales=len(faces)-1,
        vias=[dict(x_mm=float(x),u_mm=float(u),diametre_mm=float(diam),
            cellules_transversales=int(sum((grille['x'][:-1]>=x-diam/2-1e-8)&(grille['x'][1:]<=x+diam/2+1e-8))),
            cellules_longitudinales=int(sum((grille[propagation][:-1]>=u-diam/2-1e-8)&(grille[propagation][1:]<=u+diam/2+1e-8))))
            for x,u,diam in mod.vias_mm()],
        garde_hors_pml_mm=marge_air(montage.acquisition,montage.maillage),
        pml8={a:dict(gauche_mm=grille[a][:9].tolist(),droite_mm=grille[a][-9:].tolist()) for a in 'xyz'},
        ancres='primaires BASE conservees dans projection PCB hors blocs SMA ; air libre',
        interpolation_sma='libre hors port uniforme et vias ; interfaces exactes',
        aretes='rectilignes primaires exactes ; pas de regle tiers generalisee',
        port='ideal50ohms au bord PCB ; connecteur coaxial3D non modelise')
'''
    auxiliaires+='\n\n'+controles
    ancien=fonction(texte,'construit')
    nouveau=ancien
    nouveau=nouveau.replace('    from CSXCAD.SmoothMeshLines import SmoothMeshLines\n','')
    nouveau=remplace_une(nouveau,'    verifie_emprise(csx, demi, lz)\n',
        '    verifie_emprise(csx, demi, lz)\n    _reglages_controles(montage, antenne_mod)\n    boite_pcb = _boite_primitives(csx)\n')
    a=nouveau.index('    air = C/a.f_max*1e3/m.mailles_par_lambda_air')
    b=nouveau.index('    # Les minima par axe rendent le CFL conservatif')
    nouveau=nouveau[:a]+'''    boite_domaine = boite_pcb.copy()
    if distances:
        boite_domaine[0,:2] = np.minimum(boite_domaine[0,:2],-pl.cote/2)
        boite_domaine[1,:2] = np.maximum(boite_domaine[1,:2],pl.cote/2)
        boite_domaine[1,2] = max(boite_domaine[1,2],distances[-1]*10+pl.epaisseur)
    commun = dict(interfaces=interfaces,dielectriques=dielectriques)
    base = None
    if not _configuration_base(m):
        montage_base = replace(montage,maillage=replace(m,**NIVEAUX['base']))
        base = _applique_grille_controlee(montage_base,antenne_mod,csx,
            boite_pcb,boite_domaine,**commun)
    grille_finale = _applique_grille_controlee(montage,antenne_mod,csx,
        boite_pcb,boite_domaine,grille_base=base,**commun)
    if base is not None:
        d = antenne_mod.cotes()
        normal, propagation = ('y','z') if antenne_mod.NOM == 'vivaldi_tomographie' else ('z','y')
        h = float(d['h'])
        u0 = 0. if propagation == 'z' else -float(d['carte_w'])/2
        import connectique
        zones = {a:[[float(boite_pcb[0,i]),float(boite_pcb[1,i])]] for i,a in enumerate('xyz')}
        zones['x'].append([-connectique.MASSE_EXTERIEUR_MM,connectique.MASSE_EXTERIEUR_MM])
        zones[normal].append([-h/3,4*h/3])
        zones[propagation].append([u0-h,max(u+connectique.PASTILLE_DIAMETRE_MM/2 for _,u,_ in antenne_mod.vias_mm())])
        _verifie_non_grossissement(base,grille_finale,zones)
        for axe in 'xyz':
            if not (np.array_equal(base[axe][:9],grille_finale[axe][:9]) and
                    np.array_equal(base[axe][-9:],grille_finale[axe][-9:])):
                raise ValueError('coordonnees PML F2 differentes de la base')
'''+nouveau[b:]
    texte=remplace_une(texte,ancien,nouveau)
    texte=remplace_une(texte,'def construit(',auxiliaires+'\n\n\ndef construit(')
    texte=remplace_une(texte,"def _sauve_manifeste(dossier, manifeste):\n",
        "def _sauve_manifeste(dossier, manifeste):\n    manifeste['moteur'] = NOM_MOTEUR\n")
    texte=remplace_une(texte,"    return {str(p.relative_to(ICI)).replace('\\\\', '/'): _sha256(p) for p in sources}",
        "    sources.append(Path(ICI)/'fdtd_maille_controlee.py')\n    return {str(p.relative_to(ICI)).replace('\\\\', '/'): _sha256(p) for p in sources}")
    texte=remplace_une(texte,'        execution=execution, materiaux=_proprietes_matiere(csx)[3],',
        '        execution=execution, materiaux=_proprietes_matiere(csx)[3],\n        politique_maillage=politique_maillage(montage, antenne_mod, csx),')
    texte=remplace_une(texte,'"""Scenes openEMS, maillages controles et executions archivables.',
        '"""Moteur separe maillage_controle_v2 ; copie de F1, physique/CAD identiques.\n\nScenes openEMS, maillages controles et executions archivables.')
    ast.parse(texte)
    SORTIE.parent.mkdir(parents=True,exist_ok=True)
    SORTIE.write_text(texte,encoding='utf-8',newline='\n')
    print(SORTIE,sha(SORTIE))


if __name__=='__main__':main()
