import numpy as np
import matplotlib.pyplot as plt
import skrf as rf

# ==========================================
# 1. PARAMÈTRES PHYSIQUES
# ==========================================
c = 3e8              # Vitesse de la lumière dans le vide (m/s)
epsilon_r = 45.0     # Permittivité relative de la gélatine (à ajuster)

# ==========================================
# 2. CHARGEMENT DES DONNÉES DU LITEVNA
# ==========================================
# scikit-rf lit automatiquement le fichier Touchstone
vna_data = rf.Network('mesure_gelatine.s1p')

freqs = vna_data.f                 # Tableau des fréquences (en Hz)
s11_complex = vna_data.s[:, 0, 0]  # Extraction des données S11 (nombres complexes)

# ==========================================
# 3. TRAITEMENT DU SIGNAL (iFFT)
# ==========================================
# Astuce de laboratoire : On applique une "Fenêtre de Hanning" sur les fréquences.
# Cela adoucit les bords du signal et élimine les faux échos (lobes secondaires).
window = np.hanning(len(s11_complex))
s11_windowed = s11_complex * window

# Transformée de Fourier Rapide Inverse (iFFT)
# On prend la valeur absolue (abs) pour obtenir l'enveloppe du signal (les pics)
time_signal = np.abs(np.fft.ifft(s11_windowed))

# ==========================================
# 4. CONVERSION EN DISTANCE
# ==========================================
# Calcul du pas de temps basé sur la bande passante du VNA
bandwidth = freqs[-1] - freqs[0]
time_step = 1.0 / bandwidth

# Création de l'axe du temps
time_axis = np.arange(len(time_signal)) * time_step

# Calcul de la vitesse de l'onde dans la gélatine
vitesse_onde = c / np.sqrt(epsilon_r)

# Formule du radar aller-retour : d = (t * v) / 2
distance_axis_metres = (time_axis * vitesse_onde) / 2.0

# Conversion en millimètres pour une lecture facile
distance_mm = distance_axis_metres * 1000

# ==========================================
# 5. AFFICHAGE DU GRAPHIQUE
# ==========================================
plt.figure(figsize=(10, 6))
plt.plot(distance_mm, time_signal, color='blue', linewidth=2)

plt.title("Profil d'épaisseur du fantôme (Cartilage/Os)")
plt.xlabel("Distance (mm)")
plt.ylabel("Amplitude de l'écho (Unité arbitraire)")
plt.grid(True)

# On limite l'affichage aux 50 premiers millimètres 
# (car l'onde ne va pas plus loin dans le corps de toute façon)
plt.xlim(0, 50) 

plt.tight_layout()
plt.show()