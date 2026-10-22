"""Preuve de non-regression hors sources gelees ; aucun FDTD ni selection."""
import ast
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ['OMP_NUM_THREADS'] = os.environ['OPENBLAS_NUM_THREADS'] = '1'
ICI = Path(__file__).resolve().parent
CONTROLE = ICI.parent
SIM = CONTROLE.parents[1]
BASE = SIM/'resultats/pcbway_r1'


def charge(nom, fichier):
    spec = importlib.util.spec_from_file_location(nom, fichier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ecrit(nom, contenu):
    with (ICI/nom).open('x', encoding='utf-8', newline='\n') as f:
        f.write(contenu)


def execute(module, args):
    sortie = io.StringIO()
    with redirect_stdout(sortie):
        code = module.main(args)
    return code, json.loads(sortie.getvalue()), sortie.getvalue()


def sans_provenance(d):
    return {k: v for k, v in d.items() if k != 'provenance'}


avant = json.loads((CONTROLE/'extension_n34_avant/empreintes_avant.json').read_text(encoding='utf-8'))
old = ast.parse((CONTROLE/'extension_n34_avant/analyse_extreme_fin.py').read_text(encoding='utf-8'))
new = ast.parse((CONTROLE/'analyse_extreme_fin.py').read_text(encoding='utf-8'))
fonctions = ['ecarts_independants', 'bandes', 'indicateurs_independants',
             'grille_identique', 'lit_manifeste_partage', 'manquants']
def arbre(module, nom):
    return ast.dump(next(x for x in module.body if isinstance(x, ast.FunctionDef) and x.name == nom),
                    include_attributes=False)
assert all(arbre(old, n) == arbre(new, n) for n in fonctions)

U = charge('controle_n34_preuve', CONTROLE/'analyse_extreme_fin.py')
V = charge('controle_vivaldi_preuve', SIM/'chatGPT_critical_review/controle_vivaldi/analyse_vivaldi.py')

# Queues HISTORIQUES closes, confirmees par le coordinateur :14137 et20307.
code_n30, n30, texte = execute(U, ['--n30', '--queue-sortie-zero-confirmee'])
initial_n30 = json.loads((CONTROLE/'controle_final_n30/rapport.json').read_text(encoding='utf-8'))
assert code_n30 == 2 and sans_provenance(n30) == sans_provenance(initial_n30)
ecrit('rejeu_n30.json', texte)

code_v, v, texte = execute(V, ['--queue-sortie-zero-confirmee'])
initial_v = json.loads((SIM/'chatGPT_critical_review/controle_vivaldi/controle_final_vivaldi/rapport.json').read_text(encoding='utf-8'))
assert code_v == 2 and sans_provenance(v) == sans_provenance(initial_v)
ecrit('rejeu_vivaldi_defaut5.json', texte)

# Aucune attestation de sortie0 pour les files77627(N34) et81046(Vultra) actives.
with patch.object(U.Q, 'charge_calcul', side_effect=AssertionError('lecture finale interdite')) as interdit:
    code_n34, n34, texte = execute(U, ['--n34'])
    assert code_n34 == 3 and not interdit.called
ecrit('preconditions_n34_sans_attestation.json', texte)
assert len(n34['profils_attendus']) == 13
assert n34['mode'] == 'n34'
assert n34['provenance']['scripts_sha256']['raffine_qualification_plus_pcbway.py'] == avant['sources_17_sha256']['raffine_qualification_plus_pcbway.py']
assert any(x['profil'] == 'coordination' for x in n34['manquants'])

stderr = io.StringIO()
with redirect_stderr(stderr), patch.object(U.Q, 'charge_calcul') as interdit:
    try:
        U.main(['--n34', '--n30'])
        raise AssertionError('options incompatibles acceptees')
    except SystemExit as erreur:
        assert erreur.code == 2 and not interdit.called
ecrit('refus_options_incompatibles.txt', stderr.getvalue())

sources_apres = {n: sha(SIM/n) for n in avant['sources_17_sha256']}
grand_apres = {n: sha(BASE/n) for n in avant['grand_11']}
v_apres = {n: sha(BASE/n) for n in avant['vivaldi_5']}
assert sources_apres == avant['sources_17_sha256']
assert grand_apres == avant['grand_11']
assert v_apres == avant['vivaldi_5']
preuve = dict(utc=datetime.now(timezone.utc).isoformat(),
    aucun_fdtd=True, aucune_selection=True,
    analyseur_sha256=sha(CONTROLE/'analyse_extreme_fin.py'),
    vivaldi_analyseur_sha256=sha(SIM/'chatGPT_critical_review/controle_vivaldi/analyse_vivaldi.py'),
    fonctions_ast_inchangees=fonctions,
    comparaison_n30_hors_provenance_exacte=True, code_n30=code_n30,
    comparaison_vivaldi5_hors_provenance_exacte=True, code_vivaldi5=code_v,
    code_n34_sans_attestation=code_n34, aucun_Q_charge_calcul_n34=True,
    ancienne_queue_n30_confirmee='14137', ancienne_queue_vivaldi_confirmee='20307',
    aucune_attestation_pour_queues_actives=['77627', '81046'],
    sources_17_sha256_apres=sources_apres,
    grand_305_sha256_apres=grand_apres, vivaldi_140_sha256_apres=v_apres)
ecrit('preuve.json', json.dumps(preuve, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: preuve[k] for k in ['analyseur_sha256',
    'comparaison_n30_hors_provenance_exacte', 'comparaison_vivaldi5_hors_provenance_exacte',
    'code_n34_sans_attestation', 'aucun_Q_charge_calcul_n34']}, ensure_ascii=False))
