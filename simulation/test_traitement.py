"""Controles de la chaine de traitement, sur des signaux dont on connait la verite.

Aucun de ces tests n'a besoin d'openEMS. Ils doivent passer AVANT toute
simulation : si la chaine ne retrouve pas une distance qu'on y a injectee, il
est inutile de discuter des resultats d'un calcul de champ.

    python test_traitement.py
"""
import numpy as np

from banc import C, Acquisition, Montage, MESURES_9_OCT
import traitement as tr
from modele import ModeleAntenne, simule, verite_terrain

ACQ = Acquisition()
FREQS = np.linspace(ACQ.f_min, ACQ.f_max, ACQ.points)
ECHECS = []


def verifie(nom, condition, detail=""):
    etat = "OK  " if condition else "ECHEC"
    print(f"  [{etat}] {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        ECHECS.append(nom)


print("\n1. Reglages identiques a ceux du rapport")
verifie("IFFT sur 3216 points", ACQ.n_fft == 3216, f"{ACQ.n_fft}")
verifie("pas de frequence 25 MHz", abs(ACQ.df - 25e6) < 1e3,
        f"{ACQ.df/1e6:.2f} MHz")
verifie("pas d'axe 1,86 mm", abs(ACQ.pas_distance * 1e3 - 1.86) < 0.01,
        f"{ACQ.pas_distance*1e3:.3f} mm")
verifie("resolution c/2B environ 3 cm", abs(ACQ.resolution * 100 - 3.0) < 0.1,
        f"{ACQ.resolution*100:.2f} cm")
verifie("fenetre de Hann symetrique",
        abs(tr.fenetre(201)[0]) < 1e-12 and abs(tr.fenetre(201)[100] - 1) < 1e-12)

print("\n2. Un echo pur doit se retrouver la ou on l'a mis")
for d_vrai in (0.30, 0.50, 0.65, 1.00):
    s = np.exp(-2j * np.pi * FREQS * 2 * d_vrai / C)
    d, p = tr.profil(s, ACQ)
    pic = d[np.argmax(p)] + tr._parabole(p, int(np.argmax(p))) * ACQ.pas_distance
    verifie(f"echo a {d_vrai*100:.0f} cm", abs(pic - d_vrai) * 100 < 0.2,
            f"trouve {pic*100:.2f} cm")

print("\n3. La pente de phase doit rendre le meme retard")
d_vrai, tau_sup = 0.50, 1.2e-9          # 1,2 ns aller-retour ajoutes
s = np.exp(-2j * np.pi * FREQS * (2 * d_vrai / C + tau_sup))
ph, _ = tr.phase_sans_trajet(FREQS, s, d_vrai)
tau, dec_cm, _ = tr.pente_ponderee(FREQS, ph)
verifie("retard supplementaire retrouve", abs(tau - tau_sup) < 1e-12,
        f"{tau*1e9:.4f} ns pour {tau_sup*1e9:.4f} attendus")
verifie("decalage equivalent", abs(dec_cm - C * tau_sup / 2 * 100) < 0.01,
        f"{dec_cm:.2f} cm")

print("\n4. Le modele : un retard d'antenne donne un decalage CONSTANT")
ant = ModeleAntenne(a2=0.0)              # un seul trajet interne
ecarts = []
for x_cm in (50.0, 60.0, 70.0):
    fond, plaque = simule(FREQS, x_cm, ant, echos_fixes=())
    d, p = tr.profil(plaque, ACQ, fond=fond)
    pics = tr.maxima_locaux(d, p, (40.0, 120.0), combien=1)
    ecarts.append(pics[0][0] - x_cm)
attendu = C * ant.tau1_ns * 1e-9 * 100
verifie("decalage egal a c.tau1", all(abs(e - attendu) < 0.5 for e in ecarts),
        f"{', '.join(f'{e:.2f}' for e in ecarts)} cm pour {attendu:.2f} attendus")
verifie("decalage constant d'une distance a l'autre",
        max(ecarts) - min(ecarts) < 0.2,
        f"etendue {max(ecarts)-min(ecarts):.3f} cm")

print("\n5. Deux trajets internes -> deux branches, comme dans le rapport")
ant2 = ModeleAntenne()                   # tau1 et tau2
res = {x: simule(FREQS, x, ant2, echos_fixes=())[1] for x in (50.0, 60.0, 70.0)}
bil = tr.bilan(FREQS, simule(FREQS, 50.0, ant2, echos_fixes=())[0], res, ACQ)
v = verite_terrain(50.0, ant2)
verifie("branche proche a c.tau1",
        abs(bil[50.0]["pic_proche"] - v["proche"]) < 1.0,
        f"{bil[50.0]['pic_proche']:.2f} cm pour {v['proche']:.2f} attendus")
verifie("branche lointaine a c.(tau1+tau2)/2",
        abs(bil[50.0]["pic_lointain"] - v["milieu"]) < 1.0,
        f"{bil[50.0]['pic_lointain']:.2f} cm pour {v['milieu']:.2f} attendus")
verifie("ecarts proches de ceux du rapport (20,0 et 26,3 cm)",
        all(abs(bil[d]["ecart_proche_cm"] - 20.0) < 1.5 and
            abs(bil[d]["ecart_lointain_cm"] - 26.3) < 1.5 for d in bil),
        ", ".join(f"{bil[d]['ecart_proche_cm']:.1f}/"
                  f"{bil[d]['ecart_lointain_cm']:.1f}" for d in sorted(bil)))

print("\n6. Dispersion : echo elargi et decalage constant avec la distance")


def largeur_et_ecart(antenne, x_cm, cote=0.60):
    fond, plaque = simule(FREQS, x_cm, antenne, cote_plaque_m=cote,
                          echos_fixes=())
    d, p = tr.profil(plaque, ACQ, fond=fond)
    pic = tr.maxima_locaux(d, p, (30.0, 140.0), combien=1)[0][0]
    dans = d[p > p.max() / 2] * 100
    return dans.max() - dans.min(), pic - x_cm


ant_pur = ModeleAntenne(a2=0.0)
ant_disp = ModeleAntenne(a2=0.0, derive_ns=-0.25)
l_pur, _ = largeur_et_ecart(ant_pur, 50.0)
l_disp, _ = largeur_et_ecart(ant_disp, 50.0)
verifie("l'echo s'elargit", l_disp > 1.4 * l_pur,
        f"{l_pur:.1f} cm -> {l_disp:.1f} cm a mi-hauteur")
ecarts_d = [largeur_et_ecart(ant_disp, x)[1] for x in (50.0, 60.0, 70.0)]
verifie("mais le decalage reste constant sur une GRANDE plaque",
        max(ecarts_d) - min(ecarts_d) < 0.05,
        f"etendue {max(ecarts_d)-min(ecarts_d):.3f} cm")

print("\n6b. Dispersion + plaque trop petite -> le decalage derive")
ecarts_p = [largeur_et_ecart(ant_disp, x, cote=0.30)[1] for x in (50.0, 60.0, 70.0)]
verifie("une plaque de 30 cm suffit a creer une derive",
        max(ecarts_p) - min(ecarts_p) > 0.1,
        f"{', '.join(f'{e:.2f}' for e in ecarts_p)} cm, "
        f"etendue {max(ecarts_p)-min(ecarts_p):.2f} cm")
verifie("la derive va dans le sens des mesures (ecart qui diminue)",
        ecarts_p[-1] < ecarts_p[0],
        f"{ecarts_p[0]:.2f} -> {ecarts_p[-1]:.2f} cm")

print("\n7. Regressions audit : pas de fausse deuxieme branche Hann")
mono = ModeleAntenne(a2=0.)
fond_mono = simule(FREQS, 50., mono, echos_fixes=())[0]
mesures_mono = {x: simule(FREQS, x, mono, echos_fixes=())[1] for x in (50., 60., 70.)}
bmono = tr.bilan(FREQS, fond_mono, mesures_mono, ACQ)
for x, r in bmono.items():
    verifie(f"mono {x:.0f} cm : principal sans derive",
            abs(r["ecart_principal_cm"] - 20.) < .02,
            f"{r['ecart_principal_cm']:.4f} cm")
    verifie(f"mono {x:.0f} cm : aucun second candidat",
            len(r["pics"]) == 1 and np.isnan(r["pic_lointain"]))
verifie("meme identifiant de suivi principal aux trois distances",
        len({r["candidats"][0]["suivi_id"] for r in bmono.values()}) == 1)
verifie("candidats exposes avec rang, niveau et proeminence",
        all({"rang_amplitude", "niveau_db", "relatif_db", "prominence_db", "qualifie"} <= set(c)
            for r in bmono.values() for c in r["candidats"]))
verifie("lobes Hann visibles mais disqualifies",
        all(any(not c["qualifie"] and c["relatif_db"] < -30. for c in r["candidats"])
            for r in bmono.values()))
historique = tr.bilan(FREQS, fond_mono, mesures_mono, ACQ, mode_pics="rapport")
verifie("mode rapport explicite reproduit l'artefact historique a 70 cm",
        historique[70.]["ecart_proche_cm"] < 15. and len(historique[70.]["pics"]) == 2)
verifie("mode rapport conserve pourtant un principal stable",
        all(abs(r["ecart_principal_cm"] - 20.) < .02 for r in historique.values()))
bruit_lointain = tr.bilan(FREQS, fond_mono, mesures_mono, ACQ, seuil_relatif_db=-35.)
verifie("seuil relatif configurable (revele volontairement les lobes)",
        len(bruit_lointain[50.]["pics"]) == 2)
sans = tr.bilan(FREQS, np.zeros_like(FREQS), {50.: np.zeros_like(FREQS)}, ACQ)[50.]
verifie("sans signal : aucun pic, aucune phase arbitraire",
        not sans["pics"] and not sans["candidats"] and np.isnan(sans["pic_principal"])
        and np.isnan(sans["decalage_phase_cm"]))
verifie("bimodal : deux candidats qualifies sans attribution physique",
        all(len(r["pics"]) == 2 and all(c["qualifie"] for c in r["candidats"][:2]) for r in bil.values()))
mesures_croisees = {
    x: a1 * np.exp(-4j * np.pi * FREQS * (x + 10.) / 100 / C)
       + a2 * np.exp(-4j * np.pi * FREQS * (x + 30.) / 100 / C)
    for x, a1, a2 in ((50., .9, .3), (60., .3, .9))}
croisees = tr.bilan(FREQS, np.zeros_like(FREQS), mesures_croisees, ACQ)
verifie("bimodal : principal suit le rang d'amplitude, sans forcer une branche",
        abs(croisees[50.]["ecart_principal_cm"] - 10.) < .1 and
        abs(croisees[60.]["ecart_principal_cm"] - 30.) < .1)
suivis = [[min((c for c in r["candidats"] if c["qualifie"]),
               key=lambda c: abs(c["ecart_cm"] - ecart))["suivi_id"]
           for r in croisees.values()] for ecart in (10., 30.)]
verifie("bimodal : suivi conserve les deux candidats quand les rangs s'inversent",
        all(len(set(identifiants)) == 1 for identifiants in suivis))
epaule = tr.candidats_maxima(np.arange(5) * .01 + .4, [0., 1., .9, 1.01, 0.])
verifie("proeminence filtre une epaule pourtant proche en amplitude",
        len([c for c in epaule if c["qualifie"]]) == 1)
frequences_test = np.linspace(1e9, 2e9, 7)
adapte = np.array([.1, .1, .8, .8, .1, .1, .8], dtype=complex)
bandes = tr.bandes_adaptees(frequences_test, adapte)
verifie("resume S11 : deux segments interrompus, pas une enveloppe",
        bandes["segments_hz"] == [(frequences_test[0], frequences_test[1]),
                                   (frequences_test[4], frequences_test[5])])
verifie("resume S11 : aucune adaptation est un resultat normal",
        tr.bandes_adaptees(frequences_test, np.full(7, .9))["segments_hz"] == [])

print("\n8. Rappel des mesures a reproduire (rapport du 9 octobre)")
for d_cm, (proche, lointain) in sorted(MESURES_9_OCT.items()):
    print(f"       plaque {d_cm:.0f} cm : pics {proche:.2f} et {lointain:.2f} cm"
          f"  ->  ecarts {proche-d_cm:.2f} et {lointain-d_cm:.2f} cm")

print()
print(Montage().resume())
print()
if ECHECS:
    print(f"  {len(ECHECS)} CONTROLE(S) EN ECHEC : " + ", ".join(ECHECS))
    raise SystemExit(1)
print("  TOUS LES CONTROLES SONT PASSES")
