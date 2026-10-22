"""Lecture scientifique des deux Setups clos ; aucune reconstruction ni simulation."""
import os
import sys
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[n] = '1'
os.environ['MPLBACKEND'] = 'Agg'
sys.dont_write_bytecode = True
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Rectangle
from lecture_vtk import exige, lit_vtr, lit_vtp

ICI = Path(__file__).resolve().parent
SIM = ICI.parents[1]
INSPECTION = SIM/'chatGPT_critical_review/preparation_operateur_PEC_F2_2026-10-21/preparation_03'
ORIGINE = SIM/'resultats/pcbway_maille_controlee_v2/diamant_uwb'
PROFILS = ('base_12ns','fin_16ns')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def lit(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def inventaire(racine):
    return {p.relative_to(racine).as_posix():sha(p) for p in sorted(racine.rglob('*')) if p.is_file()}


def dual(v, i):
    exige(0 < i < len(v)-1, 'Bord domaine non pris en charge ici')
    return (v[i-1:i+1].sum()/2, v[i:i+2].sum()/2)


def topologie(segments):
    parents = {}
    def racine(n):
        parents.setdefault(n,n)
        while parents[n] != n:
            parents[n] = parents[parents[n]]
            n = parents[n]
        return n
    for a,b in segments:
        a,b = tuple(map(int,a)),tuple(map(int,b))
        parents[racine(a)] = racine(b)
    return racine


def main():
    exige(not (ICI/'rapport_operateur.json').exists(), 'Rapport deja present')
    fin = lit(INSPECTION/'execution_terminee.json')
    exige(fin['code'] == 0 and fin['aucun_pas_temporel'] and len(fin['resultats']) == 2 and
          all(r['code_processus'] == 0 and r['arret_surveillance'] is None for r in fin['resultats']),
          'Deux Setups clos sans integration temporelle requis')
    plan = lit(INSPECTION/'plan.json')
    sources_avant = {n:sha(SIM/n) for n in plan['sources18_sha256']}
    exige(sources_avant == plan['sources18_sha256'], 'Source gelee changee')
    inspection_avant = inventaire(INSPECTION)
    originaux_avant = {p+'/'+n:h for p in PROFILS for n,h in inventaire(ORIGINE/p).items()}
    resultats = []
    figures = []
    fig1, ax1 = plt.subplots(2,2,figsize=(13,10),constrained_layout=True)
    fig2, ax2 = plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
    for col, profil in enumerate(PROFILS):
        chemin = INSPECTION/'sorties'/profil
        coord_m, data = lit_vtr(chemin/'operator_dump.vtr')
        points, lignes = lit_vtp(chemin/'PEC_dump.vtp')
        # Verifier les coordonnees reelles, en metres, contre les axes NPZ archives.
        coord = [coord_m[a]*1000 for a in 'xyz']
        with np.load(INSPECTION/'entrees'/profil/'maillage.npz',allow_pickle=False) as z:
            ecarts_axes = {a:float(np.max(abs(coord_m[a]-z[a]*1e-3))) for a in 'xyz'}
        exige(max(ecarts_axes.values()) <= 2e-17, 'Coordonnees VTR/NPZ incoherentes')
        exige(set(data) == {'exc_volt','vv','vi','iv','ii'} and
              all(np.isfinite(v).all() for v in data.values()), 'Tableaux operateur invalides')
        arbre = ET.parse(chemin/'operator_dump.vtr')
        validation_range = {}
        for da in arbre.findall('RectilinearGrid/Piece/PointData/DataArray'):
            v = data[da.get('Name')].astype(np.float64)
            norme = np.sqrt(np.sum(v*v,axis=3))
            mini,maxi = float(norme.min()),float(norme.max())
            exige(np.isclose(mini,float(da.get('RangeMin')),rtol=3e-6,atol=1e-12) and
                  np.isclose(maxi,float(da.get('RangeMax')),rtol=3e-6,atol=1e-12),
                  'Normes VTK decodees incoherentes')
            validation_range[da.get('Name')] = [mini,maxi]
            del v,norme
        # Chaque ligne VTP doit etre une arete primaire adjacente ; Float32 des points seulement.
        indices = []
        erreur_points = []
        for i in range(3):
            delta = abs(points[:,i,None].astype(float)*1000-coord[i])
            idx = np.argmin(delta,axis=1)
            erreur_points.append(float(delta[np.arange(len(idx)),idx].max()))
            indices.append(idx)
        exige(max(erreur_points) < 5e-6, 'Point VTP ne correspond pas a un axe archive')
        ijk = np.stack(indices,axis=1)
        segments = ijk[lignes]
        pas = abs(segments[:,1]-segments[:,0])
        exige(np.all(pas.sum(axis=1) == 1), 'Segment PEC non adjacent')
        directions = np.argmax(pas,axis=1)
        debuts = np.minimum(segments[:,0],segments[:,1])
        natifs = set((int(n),int(x),int(y),int(z)) for n,(x,y,z) in zip(directions,debuts))
        exige(len(natifs) == len(lignes), 'Aretes VTP dupliquees')
        zz,yy,xx,dd = np.where((data['vv']==0)&(data['vi']==0))
        interieur = (abs(coord[0][xx])<=16+1e-9)&(coord[1][yy]>=-20-1e-9)&(coord[1][yy]<=20+1e-9)&(coord[2][zz]>=-1e-9)&(coord[2][zz]<=1.6+1e-9)
        zeros = set((int(n),int(x),int(y),int(z)) for n,x,y,z in zip(dd[interieur],xx[interieur],yy[interieur],zz[interieur]))
        exige(natifs == zeros, 'Graphe VTP different des zeros vv/vi sur le PCB')
        racine = topologie(segments)
        def noeud(x,y,z):
            return tuple(int(np.argmin(abs(coord[i]-v))) for i,v in enumerate((x,y,z)))
        signal,masse = noeud(0,-20,1.6),noeud(0,-19,0)
        contacts = {n:bool(racine(noeud(x,y,z))==racine(masse)) for n,x,y,z in
                    (('masse_G',-4.318,-17,1.6),('masse_D',4.318,-17,1.6))}
        contacts['signal_relie_masse'] = bool(racine(signal)==racine(masse))
        # Source distribuee : arêtes E_z, non interpolation des PointData au centre des cellules.
        z,y,x = np.where(data['exc_volt'][...,2] != 0)
        ux,uy,uz = np.unique(x),np.unique(y),np.unique(z)
        exige(len(uy)==1 and np.count_nonzero(data['exc_volt'][...,:2])==0 and
              len(x)==len(ux)*len(uz), 'Support source non rectangulaire/oriente z')
        iy = int(uy[0])
        vv = data['vv'][uz[:,None],iy,ux[None,:],2].astype(float)
        vi = data['vi'][uz[:,None],iy,ux[None,:],2].astype(float)
        exige((vi>0).all() and (vv<1).all(), 'Source sur arête bloquee ou sans conductance')
        g = (1-vv)/vi
        dt = lit(INSPECTION/'entrees'/profil/'simulation_manifest.json')['execution']['dt_s']
        c = dt*(1+vv)/(2*vi)
        req = float(np.sum(1/np.sum(g,axis=1)))
        req_colonnes = float(1/np.sum(1/np.sum(1/g,axis=0)))
        ceq = float(1/np.sum(1/np.sum(c,axis=1)))
        excitation = data['exc_volt'][uz[:,None],iy,ux[None,:],2].astype(float)
        u_exc = np.sum(excitation,axis=0)
        bx0,bx1 = dual(coord[0],int(ux[0]))[0],dual(coord[0],int(ux[-1]))[1]
        by0,by1 = dual(coord[1],iy)
        contacts_port = {}
        for n,zindice,ref in (('bas',int(uz[0]),masse),('haut',int(uz[-1])+1,signal)):
            contacts_port[n] = bool(all(racine((int(ix),iy,zindice))==racine(ref) for ix in ux))
        # Boite duale I, fichier ASCII VTK : les huit sommets incluent des doublons de boite plate.
        boite = (chemin/'box_dump_.vtk').read_text(encoding='ascii')
        lignes_boite = boite.splitlines()
        l = next(i for i,t in enumerate(lignes_boite) if t.startswith('POINTS '))
        nombre = int(lignes_boite[l].split()[1])
        sommets = np.array([list(map(float,t.split())) for t in lignes_boite[l+1:l+1+nombre]])*1000
        borne_i = [sommets.min(axis=0).tolist(),sommets.max(axis=0).tolist()]
        # box_dump ASCII affiche six chiffres : y=-0.0200727 m est quantifie a 1e-7 m.
        erreur_boite = float(max(np.max(abs(sommets[:,:2].min(axis=0)-[bx0,by0])),
                                 np.max(abs(sommets[:,:2].max(axis=0)-[bx1,by1]))))
        exige(abs(sommets[:,2]-.8).max()<1e-9 and erreur_boite<1e-4,
              'Boite I incoherente avec support source dual, meme apres quantification ASCII')
        # Via : section de colonnes E_z reellement PEC traversant toute l'epaisseur.
        vias = []
        for signe in (-1,1):
            ix_v = np.flatnonzero(abs(coord[0]-signe*4.318)<=.2286+1e-8)
            iy_v = np.flatnonzero(abs(coord[1]+14.031)<=.2286+1e-8)
            iz_v = np.flatnonzero((coord[2]>=-1e-10)&(coord[2]<1.6-1e-10))
            positions = []
            for j in iy_v:
                for i in ix_v:
                    if ((data['vv'][iz_v,j,i,2]==0)&(data['vi'][iz_v,j,i,2]==0)).all():
                        dx = dual(coord[0],int(i)); dy=dual(coord[1],int(j))
                        positions.append(dict(x_mm=float(coord[0][i]),y_mm=float(coord[1][j]),
                            dual_x_mm=list(map(float,dx)),dual_y_mm=list(map(float,dy)),
                            aire_duale_mm2=float((dx[1]-dx[0])*(dy[1]-dy[0]))))
            vias.append(dict(cote=signe,colonnes_PEC=len(positions),
                section_duale_mm2=float(sum(p['aire_duale_mm2'] for p in positions)),
                aire_cercle_CAD_mm2=float(np.pi*(.4572/2)**2),positions=positions))
        resultats.append(dict(profil=profil,forme_zyx3=list(data['vv'].shape),
            validation_ranges=validation_range,ecart_axes_VTR_NPZ_m=ecarts_axes,
            erreur_float32_points_VTP_mm=erreur_points,
            graphe_PEC=dict(aretes=len(natifs),directions_xyz=np.bincount(directions,minlength=3).tolist(),
                identique_zeros_vv_vi_sur_PCB=True,contacts=contacts,contacts_port=contacts_port),
            source=dict(nombre_aretes=len(x),nombre_x=len(ux),nombre_z=len(uz),
                aucun_chevauchement_PEC=True,R_reconstruite_ohms=req,R_reseau_colonnes_ohms=req_colonnes,
                G_branches_S_minmax=[float(g.min()),float(g.max())],
                C_RC_base_equivalente_F=ceq,
                somme_exc_volt_par_colonne_minmax=u_exc[[int(np.argmin(u_exc)),int(np.argmax(u_exc))]].tolist(),
                domaine_dual_mm=[[float(bx0),float(by0),0.],[float(bx1),float(by1),1.6]],
                largeur_duale_x_mm=float(bx1-bx0),largeur_duale_y_mm=float(by1-by0),
                boite_I_mm=borne_i,erreur_boite_I_ASCII_mm=erreur_boite,centre_normal_I_mm=.8),vias=vias))
        # Vue de PEC terminal et du port, exclusivement depuis les aretes natives.
        xyz = np.stack([coord[k][segments[:,:,k]] for k in range(3)],axis=2)
        top = (abs(xyz[:,:,2]-1.6).max(axis=1)<1e-8)&(abs(xyz[:,:,0]).max(axis=1)<6.1)&(xyz[:,:,1].min(axis=1)>-20.3)&(xyz[:,:,1].max(axis=1)<-12.8)
        ax = ax1[0,col]
        ax.add_collection(LineCollection(xyz[top,:,:2],colors='#222222',linewidths=.55))
        for v in vias:
            ax.add_patch(Circle((v['cote']*4.318,-14.031),.2286,fill=False,color='#be3a34',lw=1.5))
        ax.plot([-1.143,1.143],[-20,-20],color='#1476b8',lw=3,label='source au bord')
        ax.set(xlim=(-6,6),ylim=(-20.3,-12.8),aspect='equal',xlabel='x (mm)',ylabel='y (mm)',title=profil+' — PEC à z=1,6 mm')
        ax.legend(loc='upper center',fontsize=8)
        ax = ax1[1,col]
        cut=(abs(xyz[:,:,1]+20).max(axis=1)<1e-8)&(abs(xyz[:,:,0]).max(axis=1)<1.5)&(xyz[:,:,2].min(axis=1)>-.01)&(xyz[:,:,2].max(axis=1)<1.61)
        ax.add_collection(LineCollection(xyz[cut][:,:,[0,2]],colors='#222222',linewidths=2.))
        for xx in coord[0][ux]:
            ax.plot([xx,xx],[0,1.6],color='#e59b24',lw=.6)
        ax.plot([0,0],[0,1.6],color='#008a7c',lw=2,label='ligne U')
        ax.plot([bx0,bx1],[.8,.8],color='#a03399',lw=2,label='surface I (projection)')
        ax.set(xlim=(-1.5,1.5),ylim=(-.1,1.7),xlabel='x (mm)',ylabel='z (mm)',title=f'Port : {len(ux)} × {len(uz)} branches ; R={req:.7f} Ω')
        ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper right')
        # Coefficient VV_z au plan x=0 : support dual longitudinal, pas une interpolation de champ.
        ax=ax2[0,col]
        ix0=int(np.argmin(abs(coord[0])))
        iyc=np.flatnonzero((coord[1]>=-21.6)&(coord[1]<=-18.4))
        izc=np.flatnonzero((coord[2]>=-1e-10)&(coord[2]<1.6-1e-10))
        yb=np.r_[[dual(coord[1],int(i))[0] for i in iyc],dual(coord[1],int(iyc[-1]))[1]]
        zb=coord[2][np.r_[izc,izc[-1]+1]]
        im=ax.pcolormesh(yb,zb,data['vv'][izc[:,None],iyc[None,:],ix0,2],vmin=0,vmax=1,cmap='viridis',shading='flat')
        ax.set(xlabel='y (mm), x=0',ylabel='z (mm)',title=profil+' — coefficient VV_z')
        fig2.colorbar(im,ax=ax,shrink=.8,label='VV_z sans unité')
        ax=ax2[1,col]
        v=vias[1]
        for p in v['positions']:
            x0,x1=p['dual_x_mm'];y0,y1=p['dual_y_mm']
            ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,color='#2c6c9f',alpha=.75,ec='white',lw=.5))
        ax.add_patch(Circle((4.318,-14.031),.2286,fill=False,color='#be3a34',lw=1.5,label='cylindre CAD'))
        ax.set(xlim=(3.96,4.68),ylim=(-14.39,-13.67),aspect='equal',xlabel='x (mm)',ylabel='y (mm)',
            title=f"Via droit : {v['colonnes_PEC']} colonnes, ΣA={v['section_duale_mm2']:.6f} mm²")
        ax.legend(fontsize=8)
        del data
    fig1.suptitle('Deux opérateurs Petit F2 clos — connexions PEC et source',fontsize=14)
    fig2.suptitle('Deux opérateurs Petit F2 clos — support du port et section Yee du via',fontsize=14)
    for fig,nom in ((fig1,'connexions_PEC_port.png'),(fig2,'coefficients_et_via.png')):
        fig.savefig(ICI/nom,dpi=180)
        figures.append(dict(fichier=nom,sha256=sha(ICI/nom)))
        plt.close(fig)
    inspection_apres=inventaire(INSPECTION)
    originaux_apres={p+'/'+n:h for p in PROFILS for n,h in inventaire(ORIGINE/p).items()}
    sources_apres={n:sha(SIM/n) for n in plan['sources18_sha256']}
    exige(inspection_avant==inspection_apres and originaux_avant==originaux_apres and
          sources_avant==sources_apres==plan['sources18_sha256'],'Source/preuve changee pendant lecture')
    rapport=dict(schema='lecture_scientifique_operateur_Petit_F2_v1',utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version,numpy=np.__version__,threads_analyse=1,
        scripts_sha256={p.name:sha(p) for p in (Path(__file__),ICI/'lecture_vtk.py')},
        execution_Setups_close_sha256=sha(INSPECTION/'execution_terminee.json'),
        plan_sha256=sha(INSPECTION/'plan.json'),sources18_avant=sources_avant,sources18_apres=sources_apres,
        inspection03_fichiers_avant=inspection_avant,inspection03_fichiers_apres=inspection_apres,
        deux_profils_originaux_avant=originaux_avant,deux_profils_originaux_apres=originaux_apres,
        cas=resultats,figures=figures,aucun_Setup_Run_ou_nouvelle_grille=True,aucune_qualification=True,
        definition_RC='G=(1-VV)/VI ; C=dt*(1+VV)/(2*VI) ; Rserie_plans=sum_z 1/sum_x G ; C_RC_inf=1/sum_z 1/sum_x C',
        limites=['L operateur inspecte est celui du CAD XML arrondi, avec axes NPZ/dt restitues : pas ancien CSX bitidentique garanti.',
            'C RC de base est une representation statique epsilon_inf, pas l impedance complete Debye ni la capacitance RF de toute antenne.',
            'R reconstituee audite la normalisation du reseau de branches ; elle ne mesure pas Zantenne.',
            'La section duale de colonnes PEC n est pas un diametre physique de via : les champs sont decales sur Yee.',
            'Le PEC terminal peut preexister dans le CAD ; les dumps finaux ne permettent pas d attribuer chaque arete aux caps seuls.',
            'Aucune causalite formelle de l ecart S11 n est demontree par cette seule inspection.'])
    with (ICI/'rapport_operateur.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(rapport,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(json.dumps(dict(rapport_sha256=sha(ICI/'rapport_operateur.json'),
        cas=[dict(profil=r['profil'],source=r['source'],graphe=r['graphe_PEC'],
                  vias=[{k:v for k,v in p.items() if k!='positions'} for p in r['vias']]) for r in resultats],
        sources18_et_preuves_inchangees=True),ensure_ascii=False))


if __name__=='__main__':
    main()
