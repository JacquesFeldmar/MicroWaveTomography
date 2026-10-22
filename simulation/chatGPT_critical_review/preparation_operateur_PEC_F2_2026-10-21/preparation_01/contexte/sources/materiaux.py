"""Modeles FR4 causaux, fixes et independants de la bande d'acquisition.

Un seul point de fiche technique ne determine pas la dispersion reelle.
Le modele nominal ci-dessous est une hypothese de pertes dielectriques
presque constantes, realisee par une somme passive de relaxations de Debye.
Il reproduit exactement epsilon' et tan(delta) au point de reference.
Les poles sont fixes entre 1 MHz et 100 GHz, quelle que soit l'acquisition.
Ce modele doit etre confronte a un coupon/aux antennes fabriquees.

API verifiee dans l'environnement openEMS local : CSPropDebyeMaterial,
SetDispersiveMaterialProperty(order, eps_delta, eps_relax), AddProperty.
Documentation : https://docs.openems.de/en/latest/concepts/dispersive.html
"""
from dataclasses import asdict, dataclass
import json

import numpy as np

EPSILON_0 = 8.8541878128e-12
ATTRIBUT_MODELE = "simulation_material_model_json"


@dataclass(frozen=True)
class DebyeFR4:
    epsilon_reference: float
    tan_delta_reference: float
    frequence_reference_hz: float
    epsilon_inf: float
    delta_epsilon: tuple
    relaxation_s: tuple
    hypothese: str = ("FR4 nominal, pertes approximativement constantes; "
                     "non identifie sur le lot fabrique")

    def reponse_complexe(self, frequences_hz):
        f = np.asarray(frequences_hz, dtype=float)
        if np.any(~np.isfinite(f)) or np.any(f <= 0):
            raise ValueError("les frequences doivent etre finies et positives")
        return self.epsilon_inf + np.sum(
            np.asarray(self.delta_epsilon) /
            (1 + 2j * np.pi * f[..., None] * np.asarray(self.relaxation_s)),
            axis=-1)

    @property
    def epsilon_statique(self):
        return self.epsilon_inf + sum(self.delta_epsilon)

    def dictionnaire(self):
        return {"type": "debye_passif_13_poles", **asdict(self),
                "epsilon_statique": self.epsilon_statique,
                "poles_fixes_hz": [float(1 / (2 * np.pi * t))
                                    for t in self.relaxation_s]}


def modele_debye(eps_r=4.6, tan_delta=0.011,
                 frequence_reference_hz=1e9):
    """Somme de 13 poles positifs, calibree au seul point disponible.

    La quasi-constance de epsilon'' sur une large bande vient de poles
    uniformes en log(f), et implique la dispersion de epsilon' par causalite.
    Il ne s'agit pas d'une identification large bande du S1000H.
    """
    if not (np.isfinite(eps_r) and eps_r > 1 and
            np.isfinite(tan_delta) and tan_delta >= 0 and
            np.isfinite(frequence_reference_hz) and
            1e6 < frequence_reference_hz < 1e11):
        raise ValueError("parametres FR4 invalides ou reference hors 1 MHz–100 GHz")
    tau = 1 / (2 * np.pi * np.logspace(6, 11, 13))
    base = np.sum(1 / (1 + 2j * np.pi * frequence_reference_hz * tau))
    amplitude = eps_r * tan_delta / -base.imag
    eps_inf = eps_r - amplitude * base.real
    if eps_inf <= 1:
        raise ValueError("epsilon_inf <= 1 : pertes trop grandes pour ce modele")
    return DebyeFR4(float(eps_r), float(tan_delta),
                    float(frequence_reference_hz), float(eps_inf),
                    tuple(float(amplitude) for _ in tau),
                    tuple(float(t) for t in tau))


def conductivite_tan_delta(eps_r, tan_delta, frequence_reference_hz=1e9):
    """Conductivite constante en S/m : seulement tan(delta) a f_reference.

    Cette alternative historique fait varier tan(delta) comme 1/f. Elle est
    explicite et ne depend jamais du centre de la bande d'acquisition.
    """
    return 2 * np.pi * frequence_reference_hz * EPSILON_0 * eps_r * tan_delta


def ajoute_fr4(csx, nom, eps_r=4.6, tan_delta=0.011,
               frequence_reference_hz=1e9, modele="debye"):
    """Ajoute le materiau; retourne la propriete sur laquelle poser le PCB."""
    if modele == "debye":
        from CSXCAD.CSProperties import CSPropDebyeMaterial
        definition = modele_debye(eps_r, tan_delta, frequence_reference_hz)
        prop = CSPropDebyeMaterial(csx.GetParameterSet(), name=nom,
                                  order=len(definition.delta_epsilon))
        prop.SetMaterialProperty(epsilon=definition.epsilon_inf)
        for i, (de, tau) in enumerate(zip(definition.delta_epsilon,
                                         definition.relaxation_s)):
            prop.SetDispersiveMaterialProperty(order=i, eps_delta=de,
                                               eps_relax=tau)
        csx.AddProperty(prop)
        details = definition.dictionnaire()
    elif modele == "constant":
        kappa = conductivite_tan_delta(eps_r, tan_delta,
                                       frequence_reference_hz)
        prop = csx.AddMaterial(nom, epsilon=eps_r, kappa=kappa)
        details = dict(type="epsilon_kappa_constants", epsilon=eps_r,
                       kappa_s_m=kappa, tan_delta_reference=tan_delta,
                       frequence_reference_hz=frequence_reference_hz,
                       avertissement="tan(delta) effectif varie comme 1/f")
    else:
        raise ValueError("modele de materiau inconnu : " + modele)
    prop.SetAttributeValue(ATTRIBUT_MODELE, json.dumps(details, sort_keys=True))
    return prop
