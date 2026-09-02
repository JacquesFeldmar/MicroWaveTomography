import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons, Slider
from skrf.vi.vna.nanovna import NanoVNAv2
import skrf as rf
from scipy.signal import find_peaks
import csv
import datetime
import sys
import time
import os
import glob
import calibration_sol

# ==========================================
# 1. PARAMÈTRES PHYSIQUES ET SYSTÈME
# ==========================================
PORT_VNA = "ASRL6::INSTR"
SERIAL_BAUD = None        # None = débit série par défaut. EXPÉRIENCE : mettre 921600 — si 'acq' chute, l'acquisition
                          #        était limitée par le débit série. Si le VNA ne répond plus, remettre None.
c = 3e8  # Vitesse de la lumière (m/s)

# --- Balayage fréquentiel du VNA ---
FREQ_START_GHZ = 1.4
FREQ_STOP_GHZ = 6.3
FREQ_NPOINTS = 101        # Acquisition ~linéaire en N. Résolution FIXÉE par la bande (30 mm), indépendante de N :
                          #     réduire N ne fait que raccourcir la portée non-ambiguë (101 pts -> ~3 m >> 150 mm).
                          #     La fenêtre 0-150 mm garde ~39 échantillons quel que soit N. 51 pts reste sûr.

# --- Traitement du signal ---
FACTEUR_ZOOM = 8          # Zero-padding de l'IFFT (interpolation, pas de vraie résolution)
FACTEUR_BRUIT = 5.0       # Présence de cible si max > FACTEUR_BRUIT × médiane (SNR) ; sinon scène vide -> rien détecté
PROMINENCE_BRUIT = 3.0    # Un pic est un écho si sa prominence > PROMINENCE_BRUIT × médiane (bruit) — relatif au
                          #     BRUIT, pas au max : un écho de fond faible n'est plus masqué par une surface forte.
ECART_MIN_ECHOS_MM = 15   # Écart min entre deux échos (mm) ; borné en pratique par la résolution (~30 mm air)
GAIN_REF_MM = 100.0       # Distance de référence pour la pente du TGC

# --- Suivi des deux échos (tracking) ---
ALPHA_EMA = 0.3           # Lissage EMA des positions (0 = figé, 1 = aucun lissage)
GATE_MM = 20.0            # Rejet d'une mesure qui s'écarte de plus de GATE_MM de sa piste
MAX_FRAMES_PERDUES = 15   # Coasting : au-delà de N frames sans mesure, la piste est abandonnée

# --- Affichage / fenêtre de détection ---
DISTANCE_ANTENNE_MM = 702.0 # Position du pic FIXE de l'antenne (son plan électrique) : l'origine des distances est
                          #     ramenée à l'antenne, les cibles se lisent alors en distance réelle.
                          #     MESURÉ le 21/08/2026 sur plaque métallique à deux distances (captures 03 et 04) :
                          #     offset constant de +31,7 mm sur l'ancienne valeur de 670. La pente valait 1,025,
                          #     donc l'échelle des distances est juste — seul le plan de référence était décalé.
                          #     À REFAIRE après tout changement d'antenne ou de câble (étapes 3 et 4 du protocole).
DISTANCE_MIN_MM = 20      # Zone aveugle près de l'antenne : le résidu de couplage (tare imparfaite) y vit -> ignoré
DISTANCE_MAX_MM = 1000    # (DIAGNOSTIC) élargi pour voir TOUTES les réflexions ; on resserrera après calibrage
YLIM_AVEC_GAIN = (0, 0.015)
YLIM_DEFAUT = (0, 0.05)
FRAMES_PAR_RAPPORT = 20   # (A) Fréquence du rapport de timing, en frames

# --- Modes d'affichage (les 3 boutons radio) ---
# Renommés pour lever la confusion avec la "calibration" VNA (que ce logiciel ne fait pas) :
MODE_BRUT = 'Brut'                 # signal cru, avec la réflexion de l'antenne
MODE_SANS_FOND = 'Fond retiré'     # signal moins le fond mémorisé par 'Tare (fond vide)'
MODE_GAIN = 'Fond retiré + Gain'   # idem + amplification croissante avec la distance (TGC)

# --- État global (modifié par les widgets et la boucle) ---
background_signal = None
s11_complex = None          # Défini à chaque frame ; reste None tant qu'aucune mesure n'a eu lieu
mode_affichage = MODE_GAIN
derniere_distance = []      # Pour la sauvegarde CSV
dernier_signal = []

# Pistes de suivi des deux échos (position lissée en mm, None si non acquise)
piste_surface = None
piste_fond = None
perdu_surface = 0
perdu_fond = 0

# État du blitting (affichage rapide)
fond_cache = None
redraw_complet = True
mode_precedent = None
diag_freq_affiche = False   # (DIAGNOSTIC) infos de sweep imprimées une seule fois

# --- Procédure guidée + captures (pour analyse à distance) ---
# Chaque etape donne une position ABSOLUE depuis le plan rayonnant de l'antenne,
# et rappelle le deplacement entre parentheses : l'ancienne formulation "recule a
# 100 mm" se lisait aussi "recule DE 100 mm", ce qui a fausse une campagne.
PROTOCOLE = [
    "0 - D'ABORD hors programme : calibration_sol.py, puis --verifier. Puis CAPTURER.",
    "1 - Clique le rond 'Fond retire'. RIEN devant l'antenne. Puis CAPTURER.",
    "2 - Clique 'Tare (fond vide)', attends 1 s, PUIS CAPTURER.",
    "3 - PLAQUE METAL a 100 mm du plan de l'antenne (au reglet). Puis CAPTURER.",
    "4 - Recule la plaque JUSQU'A 200 mm (soit +100 mm). Puis CAPTURER.",
    "5 - Retire la plaque. PMMA sur POLYSTYRENE a 150 mm, rien derriere. eps=2.6. CAPTURER.",
    "6 - Fini ! Note l'epaisseur du PMMA au pied a coulisse, dis a Claude : c'est fini.",
]
etape_protocole = 0
n_capture = 0
dernier_max_med = 0.0
dernier_npics = 0
dernier_pic_fort = 0.0
dossier_captures = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")
os.makedirs(dossier_captures, exist_ok=True)
for _vieux in glob.glob(os.path.join(dossier_captures, "capture_*")):
    try:
        os.remove(_vieux)
    except OSError:
        pass
with open(os.path.join(dossier_captures, "journal.txt"), 'w', encoding='utf-8') as _f:
    _f.write("# Journal des captures (session courante)\n")

# ==========================================
# 2. CONNEXION AU LITEVNA
# ==========================================
print(f"Connexion au LiteVNA sur {PORT_VNA}...")
try:
    vna = NanoVNAv2(PORT_VNA, backend='@py')
    print("Connexion réussie !")
    if SERIAL_BAUD is not None:
        vna._resource.baud_rate = SERIAL_BAUD
        print(f"Débit série forcé à {SERIAL_BAUD} bauds.")
    frequence_radar = rf.Frequency(start=FREQ_START_GHZ, stop=FREQ_STOP_GHZ,
                                    npoints=FREQ_NPOINTS, unit='GHz')
    vna.frequency = frequence_radar
except Exception as e:
    print(f"Erreur : {e}")
    sys.exit(1)

# --- Calibration SOL logicielle ---
# Le LiteVNA renvoie TOUJOURS des données brutes sur l'USB : la calibration
# faite dans son menu CAL ne corrige que son propre écran. La correction est
# donc appliquée ici, à partir des étalons mesurés par calibration_sol.py.
# Absente -> le programme fonctionne comme avant, sur données brutes.
calibration = calibration_sol.charger()

# ==========================================
# 3. INITIALISATION DE L'AFFICHAGE ET WIDGETS
# ==========================================
plt.ion()
fig, ax = plt.subplots(figsize=(13, 8))
plt.subplots_adjust(left=0.25, bottom=0.25)  # On fait plus de place en bas

# Les tracés
ligne_echo, = ax.plot([], [], color='blue', linewidth=2, label="Signal Radar")
points_pics, = ax.plot([], [], 'ro', markersize=8, label="Échos suivis")  # Points rouges = pistes filtrées
texte_epaisseur = ax.text(0.5, 0.85, '', transform=ax.transAxes, ha='center',
                          fontsize=12, color='red', weight='bold',
                          bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))

ax.set_xlabel("Distance dans l'air (mm)")
ax.set_ylabel("Amplitude")
ax.grid(True)
ax.set_xlim(0, DISTANCE_MAX_MM)
ax.set_ylim(*YLIM_DEFAUT)
ax.legend(loc="upper right")

# --- WIDGETS ---
# Boutons
ax_btn_calib = plt.axes([0.02, 0.8, 0.15, 0.05])
btn_calib = Button(ax_btn_calib, 'Tare (fond vide)', color='lightgreen')

ax_btn_reset = plt.axes([0.02, 0.73, 0.15, 0.05])
btn_reset = Button(ax_btn_reset, 'Effacer la tare', color='tomato')

ax_btn_csv = plt.axes([0.02, 0.66, 0.15, 0.05])
btn_csv = Button(ax_btn_csv, 'Exporter CSV', color='lightblue')

# Radio Boutons
ax_radio = plt.axes([0.02, 0.45, 0.15, 0.15], facecolor='lightgoldenrodyellow')
radio_mode = RadioButtons(ax_radio, (MODE_BRUT, MODE_SANS_FOND, MODE_GAIN), active=2)

# Curseurs
ax_slider_gain = plt.axes([0.25, 0.12, 0.65, 0.03], facecolor='lightgray')
slider_gain = Slider(ax_slider_gain, 'Pente Gain (TGC)', 0.0, 5.0, valinit=1.5, valfmt='%1.1f')

ax_slider_eps = plt.axes([0.25, 0.06, 0.65, 0.03], facecolor='lightblue')
slider_eps = Slider(ax_slider_eps, 'Permittivité Gel. (εr)', 1.0, 80.0, valinit=45.0, valfmt='%1.1f')

# Bouton de capture (procédure guidée à distance)
ax_btn_capture = plt.axes([0.02, 0.34, 0.15, 0.07])
btn_capture = Button(ax_btn_capture, 'CAPTURER', color='gold')

# Bandeau d'instruction de la procédure, en haut de la fenêtre
texte_instruction = fig.text(0.58, 0.985, "PROCEDURE : " + PROTOCOLE[0], ha='center', va='top',
                             fontsize=11, weight='bold', color='darkblue',
                             bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='goldenrod'))

# --- FONCTIONS DES WIDGETS ---
def faire_calibration(event):
    global background_signal
    if s11_complex is None:
        print(">>> Pas encore de mesure : calibration ignorée.")
        return
    background_signal = s11_complex.copy()
btn_calib.on_clicked(faire_calibration)

def reset_calibration(event):
    global background_signal
    background_signal = None
btn_reset.on_clicked(reset_calibration)

def changer_mode(label):
    global mode_affichage
    mode_affichage = label
radio_mode.on_clicked(changer_mode)

def exporter_csv(event):
    if len(derniere_distance) == 0:
        print(">>> Aucune donnée à exporter pour l'instant.")
        return
    d_arr = np.asarray(derniere_distance)
    a_arr = np.asarray(dernier_signal)
    masque = d_arr <= DISTANCE_MAX_MM  # On n'exporte que la fenêtre affichée
    nom_fichier = f"scan_radar_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(nom_fichier, mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['Distance_Air_mm', 'Amplitude'])
        for d, a in zip(d_arr[masque], a_arr[masque]):
            writer.writerow([f"{d:.2f}", f"{a:.6f}"])
    print(f">>> Fichier {nom_fichier} sauvegardé avec succès !")
btn_csv.on_clicked(exporter_csv)

def capturer(event):
    """Enregistre l'état courant (image + profil CSV + journal) et avance dans la procédure."""
    global n_capture, etape_protocole, redraw_complet
    if len(derniere_distance) == 0:
        print(">>> Rien a capturer (pas encore de mesure).")
        return
    label = PROTOCOLE[etape_protocole]
    n_capture += 1
    base = os.path.join(dossier_captures, f"capture_{n_capture:02d}")

    # Image du graphe : on desactive l'animation le temps du savefig (sinon artistes absents)
    for art in (ligne_echo, points_pics, texte_epaisseur):
        art.set_animated(False)
    fig.canvas.draw()
    fig.savefig(base + ".png", dpi=90)
    for art in (ligne_echo, points_pics, texte_epaisseur):
        art.set_animated(True)

    # Profil courant complet en CSV
    d_arr = np.asarray(derniere_distance)
    a_arr = np.asarray(dernier_signal)
    with open(base + ".csv", 'w', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Distance_mm', 'Amplitude'])
        for d, a in zip(d_arr, a_arr):
            w.writerow([f"{d:.2f}", f"{a:.6f}"])

    # Journal : etat complet de l'interface a cet instant
    with open(os.path.join(dossier_captures, "journal.txt"), 'a', encoding='utf-8') as f:
        f.write(f"capture_{n_capture:02d} | etape={etape_protocole + 1} \"{label}\" | "
                f"mode={mode_affichage} | gain={slider_gain.val:.1f} | eps={slider_eps.val:.1f} | "
                f"tare={'oui' if background_signal is not None else 'non'} | "
                f"max/med={dernier_max_med:.1f} | npics={dernier_npics} | pic_fort@{dernier_pic_fort:.0f}mm | "
                f"pisteS={piste_surface} pisteF={piste_fond} | "
                f"offset_ant={DISTANCE_ANTENNE_MM:.0f} | fenetre=[{DISTANCE_MIN_MM},{DISTANCE_MAX_MM}]\n")

    print(f">>> CAPTURE {n_capture:02d} enregistree -> {label}")

    if etape_protocole < len(PROTOCOLE) - 1:
        etape_protocole += 1
    texte_instruction.set_text("PROCEDURE : " + PROTOCOLE[etape_protocole])
    redraw_complet = True  # force le redraw complet (met a jour le bandeau + reconstruit le cache blit)
btn_capture.on_clicked(capturer)


# --- OUTILS DE DÉTECTION ET DE SUIVI (C) ---
def offset_parabolique(y, i):
    """Décalage sous-échantillon (∈ [-0.5, 0.5]) du sommet du pic d'indice i, par interpolation parabolique.
    Supprime la quantification de position à ~un pas d'échantillon (~3.8 mm)."""
    if i <= 0 or i >= len(y) - 1:
        return 0.0
    denom = y[i - 1] - 2.0 * y[i] + y[i + 1]
    if denom == 0.0:
        return 0.0
    return max(-0.5, min(0.5, 0.5 * (y[i - 1] - y[i + 1]) / denom))

def suivre_pistes(mesures_mm):
    """Associe les échos détectés aux deux pistes (surface, fond) : plus proche voisin + gating + EMA + coasting.
    L'association est triviale grâce à l'a priori d'ordre (surface la plus proche, fond ensuite)."""
    global piste_surface, piste_fond, perdu_surface, perdu_fond

    # Démarrage à froid : il faut deux échos pour initialiser les deux pistes
    if piste_surface is None or piste_fond is None:
        if len(mesures_mm) >= 2:
            piste_surface, piste_fond = mesures_mm[0], mesures_mm[1]
            perdu_surface = perdu_fond = 0
        return

    dispo = list(mesures_mm)
    for nom in ('surface', 'fond'):
        estime = piste_surface if nom == 'surface' else piste_fond
        associe = None
        if dispo:
            j = min(range(len(dispo)), key=lambda k, e=estime: abs(dispo[k] - e))
            if abs(dispo[j] - estime) <= GATE_MM:
                associe = dispo.pop(j)
        if associe is not None:  # mise à jour EMA
            lisse = ALPHA_EMA * associe + (1.0 - ALPHA_EMA) * estime
            if nom == 'surface':
                piste_surface, perdu_surface = lisse, 0
            else:
                piste_fond, perdu_fond = lisse, 0
        else:                    # aucune mesure associée -> coasting
            if nom == 'surface':
                perdu_surface += 1
            else:
                perdu_fond += 1

    # Abandon d'une piste perdue trop longtemps (ré-acquisition à froid ensuite)
    if perdu_surface > MAX_FRAMES_PERDUES:
        piste_surface = None
    if perdu_fond > MAX_FRAMES_PERDUES:
        piste_fond = None


# --- PRÉPARATION DE L'AFFICHAGE RAPIDE / BLITTING (B) ---
# Le titre est constant (la bande passante ne change pas) -> il fait partie du fond statique.
bande_ghz = FREQ_STOP_GHZ - FREQ_START_GHZ
ax.set_title(f"Radar UWB - Bande passante : {bande_ghz:.2f} GHz")
# Les artistes dynamiques sont marqués 'animated' : exclus du redraw complet, redessinés à la main.
for artiste in (ligne_echo, points_pics, texte_epaisseur):
    artiste.set_animated(True)

def _forcer_redraw(event):
    global redraw_complet
    redraw_complet = True
fig.canvas.mpl_connect('resize_event', _forcer_redraw)  # un resize invalide le fond en cache

plt.pause(0.1)  # laisse la fenêtre se matérialiser avant la première capture de fond


# ==========================================
# 4. BOUCLE PRINCIPALE DE TRAITEMENT
# ==========================================
print("\nRadar actif. Prêt pour l'antenne !")

# (A) Accumulateurs de timing, rapport toutes les FRAMES_PAR_RAPPORT frames
acc_acq = acc_proc = acc_draw = acc_loop = 0.0
n_frames = 0

try:
    while True:
        t0 = time.perf_counter()

        # --- ACQUISITION ---
        try:
            s11, _ = vna.get_s11_s21()
        except Exception as e:
            print(f"Lecture VNA échouée ({e}), nouvelle tentative...")
            plt.pause(0.1)
            continue
        t1 = time.perf_counter()

        # --- TRAITEMENT ---
        freqs = s11.f
        s11_complex = s11.s[:, 0, 0]
        if calibration is not None:  # retire directivité, désadaptation, câble
            s11_complex = calibration_sol.applique(calibration, freqs, s11_complex)

        signal_travail = s11_complex.copy()
        if mode_affichage in (MODE_SANS_FOND, MODE_GAIN) and background_signal is not None:
            signal_travail = signal_travail - background_signal

        window = np.hanning(len(signal_travail))
        s11_windowed = signal_travail * window

        n_fft = len(s11_windowed) * FACTEUR_ZOOM
        profil_distance = np.abs(np.fft.ifft(s11_windowed, n=n_fft)) * FACTEUR_ZOOM

        # Le pas de la TF inverse est 1/(n_fft·Δf) avec Δf = BW/(N-1), et NON
        # 1/(BW·ZOOM) : le second surestime toutes les distances de N/(N-1),
        # soit 1 % à 101 points (6,7 mm sur le pic d'antenne à 670 mm).
        bandwidth = freqs[-1] - freqs[0]
        delta_f = bandwidth / (len(freqs) - 1)
        pas_temps = 1.0 / (n_fft * delta_f)
        time_axis = np.arange(len(profil_distance)) * pas_temps
        distance_mm = ((time_axis * c) / 2.0) * 1000  # Distance depuis le plan de référence du VNA
        distance_mm = distance_mm - DISTANCE_ANTENNE_MM  # Port extension : origine ramenée au plan de l'antenne

        if not diag_freq_affiche:  # (DIAGNOSTIC) une seule fois : le sweep est-il bien 1.4-6.3 GHz ?
            d_ech = pas_temps * c / 2.0 * 1000
            print(f"[freq] sweep {freqs[0] / 1e9:.3f}-{freqs[-1] / 1e9:.3f} GHz | {len(freqs)} pts | "
                  f"BW={bandwidth / 1e9:.3f} GHz | {d_ech:.2f} mm/echantillon | "
                  f"portee max {d_ech * len(profil_distance):.0f} mm")
            diag_freq_affiche = True

        # Fenêtre de détection : hors zone aveugle (couplage d'antenne) et sous la portée max.
        masque_fenetre = (distance_mm >= DISTANCE_MIN_MM) & (distance_mm <= DISTANCE_MAX_MM)

        # Présence de cible jugée sur le profil BRUT (avant TGC) : max/médiane = SNR.
        # Scène vide après tare -> rapport faible -> aucune détection (plus de faux objet à ~1 cm).
        profil_brut_fen = profil_distance[masque_fenetre]
        cible_presente = np.max(profil_brut_fen) > FACTEUR_BRUIT * np.median(profil_brut_fen)
        # Diagnostic : distance du réflecteur le plus fort sur TOUT le profil brut (avant gain)
        d_pic_fort = distance_mm[int(np.argmax(profil_distance))]
        dernier_max_med = np.max(profil_brut_fen) / np.median(profil_brut_fen)
        dernier_pic_fort = d_pic_fort

        if mode_affichage == MODE_GAIN:
            gain_vector = 1.0 + (slider_gain.val * (distance_mm / GAIN_REF_MM))
            profil_distance = profil_distance * gain_vector

        # --- DÉTECTION DES PICS ---
        dist_fenetre = distance_mm[masque_fenetre]
        profil_fenetre = profil_distance[masque_fenetre]
        pas_mm = dist_fenetre[1] - dist_fenetre[0]
        ecart_min = max(1, int(round(ECART_MIN_ECHOS_MM / pas_mm)))

        if cible_presente:
            # Seuil relatif au BRUIT (médiane), pas au max : les deux échos passent même si le fond est faible.
            seuil = PROMINENCE_BRUIT * np.median(profil_fenetre)
            indices_pics, props = find_peaks(profil_fenetre, prominence=seuil, distance=ecart_min)
            # On ne garde que les deux échos les plus saillants (surface + fond).
            if len(indices_pics) > 2:
                deux_plus_saillants = np.argsort(props['prominences'])[-2:]
                indices_pics = np.sort(indices_pics[deux_plus_saillants])
        else:
            indices_pics = np.array([], dtype=int)

        # (C) Position sous-échantillon de chaque pic
        positions_mesurees = [dist_fenetre[i] + offset_parabolique(profil_fenetre, i) * pas_mm
                              for i in indices_pics]
        dernier_npics = len(indices_pics)

        # --- SUIVI DES DEUX PISTES (EMA + gating + coasting) ---
        suivre_pistes(positions_mesurees)

        # --- CALCUL DE L'ÉPAISSEUR (à partir des pistes filtrées) ---
        if piste_surface is not None and piste_fond is not None and mode_affichage != MODE_BRUT:
            delta_air = piste_fond - piste_surface            # Épaisseur apparente (air)
            epsilon = slider_eps.val
            epaisseur_reelle = delta_air / np.sqrt(epsilon)   # Correction vitesse-milieu
            texte_epaisseur.set_text(f"Épaisseur cible détectée : {epaisseur_reelle:.1f} mm\n(εr = {epsilon})")
        else:
            texte_epaisseur.set_text("En attente de cible (2 échos requis)")

        # Mise à jour des données des tracés
        ligne_echo.set_data(distance_mm, profil_distance)
        xs = [p for p in (piste_surface, piste_fond) if p is not None]
        ys = np.interp(xs, dist_fenetre, profil_fenetre) if xs else []
        points_pics.set_data(xs, ys)

        # Sauvegarde pour l'export CSV
        derniere_distance = distance_mm
        dernier_signal = profil_distance
        t2 = time.perf_counter()

        # --- AFFICHAGE (blitting) ---
        if redraw_complet or mode_affichage != mode_precedent:
            # Redraw complet nécessaire (1re frame, resize, ou changement d'échelle Y)
            ax.set_ylim(*(YLIM_AVEC_GAIN if mode_affichage == MODE_GAIN else YLIM_DEFAUT))
            fig.canvas.draw()
            fond_cache = fig.canvas.copy_from_bbox(ax.bbox)
            redraw_complet = False
        else:
            fig.canvas.restore_region(fond_cache)  # on repose le fond depuis le cache
        ax.draw_artist(ligne_echo)
        ax.draw_artist(points_pics)
        ax.draw_artist(texte_epaisseur)
        fig.canvas.blit(ax.bbox)
        fig.canvas.flush_events()
        mode_precedent = mode_affichage
        t3 = time.perf_counter()

        # --- (A) RAPPORT DE TIMING ---
        acc_acq += t1 - t0
        acc_proc += t2 - t1
        acc_draw += t3 - t2
        acc_loop += t3 - t0
        n_frames += 1
        if n_frames >= FRAMES_PAR_RAPPORT:
            fps = n_frames / acc_loop if acc_loop > 0 else 0.0
            snr = np.max(profil_brut_fen) / np.median(profil_brut_fen)
            etat_pistes = ('S' if piste_surface is not None else '-') + ('F' if piste_fond is not None else '-')
            print(f"[timing] acq={1000 * acc_acq / n_frames:5.1f} ms | "
                  f"proc={1000 * acc_proc / n_frames:4.1f} ms | "
                  f"draw={1000 * acc_draw / n_frames:4.1f} ms | ~{fps:4.1f} fps")
            print(f"[detect] cible={'oui' if cible_presente else 'non'} (max/med={snr:.1f}) | "
                  f"npics={len(indices_pics)} | pistes={etat_pistes} | pic_fort@{d_pic_fort:.0f}mm")
            acc_acq = acc_proc = acc_draw = acc_loop = 0.0
            n_frames = 0

except KeyboardInterrupt:
    print("\nArrêt manuel.")
finally:
    plt.ioff()
    try:
        vna.close()  # Libère le port série si le driver le supporte
    except Exception:
        pass
    plt.show()
