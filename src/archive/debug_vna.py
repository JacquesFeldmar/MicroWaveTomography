from skrf.vi.vna.nanovna import NanoVNAv2

PORT_VNA = "ASRL6::INSTR"  # Syntaxe VISA pour le COM5

try:
    print(f"Tentative de connexion binaire sur {PORT_VNA}...")
    # backend='@py' force Python à utiliser la librairie pyvisa-py que nous venons d'installer
    vna = NanoVNAv2(PORT_VNA, backend='@py')
    
    print("\n--- SUCCÈS ---")
    print("Appareil reconnu :")
    print(vna.id)  # Va afficher la version exacte de votre firmware !
    
    print("\nDemande d'un balayage S11 au LiteVNA...")
    # La librairie s'occupe de toutes les requêtes binaires complexes
    s11, s21 = vna.get_s11_s21()
    
    print(f"Génial ! {len(s11.f)} points récupérés.")
    print(f"Fréquence de départ : {s11.f[0] / 1e9} GHz")
    print(f"Fréquence de fin : {s11.f[-1] / 1e9} GHz")

except Exception as e:
    print(f"\nErreur : {e}")