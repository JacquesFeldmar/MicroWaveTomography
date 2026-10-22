"""Lecteur strict des seuls VTK XML zlib little-endian emis par ces deux Setups.

Le format est decrit par VTK XML File Formats et vtkXMLWriterBase.
Aucun paquet installe et aucun code natif de simulation appele.
"""
import base64
from pathlib import Path
import xml.etree.ElementTree as ET
import zlib
import numpy as np

TYPES = {'Float32':'<f4', 'Float64':'<f8', 'Int64':'<i8', 'Int32':'<i4', 'UInt32':'<u4'}


def exige(c, texte):
    if not c:
        raise ValueError(texte)


def bloc_compresse(texte):
    texte = ''.join(texte.split())
    prefixe = np.frombuffer(base64.b64decode(texte[:16], validate=True), dtype='<u4')
    exige(len(prefixe) == 3, 'Entete VTK invalide')
    blocs, taille_bloc, taille_finale = map(int, prefixe)
    n_entete = 4 * ((4 * (3 + blocs) + 2) // 3)
    entete = np.frombuffer(base64.b64decode(texte[:n_entete], validate=True), dtype='<u4')
    exige(len(entete) == 3 + blocs, 'Tailles entete VTK incoherentes')
    tailles = list(map(int, entete[3:]))
    n_compresse = sum(tailles)
    n_base64 = 4 * ((n_compresse + 2) // 3)
    compresse = base64.b64decode(texte[n_entete:n_entete + n_base64], validate=True)
    exige(len(compresse) == n_compresse, 'Charge VTK tronquee')
    morceaux = []
    pos = 0
    for k, n in enumerate(tailles):
        b = zlib.decompress(compresse[pos:pos+n])
        attendu = taille_finale if k == blocs-1 else taille_bloc
        exige(len(b) == attendu, 'Bloc VTK decompresse de mauvaise longueur')
        morceaux.append(b)
        pos += n
    return b''.join(morceaux)


def lit_xml(chemin):
    root = ET.parse(Path(chemin)).getroot()
    exige(root.get('byte_order') == 'LittleEndian' and root.get('header_type') == 'UInt32'
          and root.get('compressor') == 'vtkZLibDataCompressor', 'Format VTK non pris en charge')
    app = root.find('AppendedData')
    texte_app = None
    if app is not None:
        exige(app.get('encoding') == 'base64', 'Appended VTK non base64')
        texte_app = ''.join(app.text.split())
        exige(texte_app.startswith('_'), 'Appended VTK sans marqueur')
        texte_app = texte_app[1:]

    def lit_array(da):
        if da.get('format') == 'binary':
            b = bloc_compresse(da.text)
        elif da.get('format') == 'appended':
            b = bloc_compresse(texte_app[int(da.get('offset')):])
        else:
            raise ValueError('Encodage DataArray inconnu')
        v = np.frombuffer(b, dtype=TYPES[da.get('type')])
        nc = int(da.get('NumberOfComponents', '1'))
        exige(len(v) % nc == 0, 'Taille DataArray non divisible')
        return v.reshape(-1, nc) if nc > 1 else v

    return root, lit_array


def lit_vtr(chemin):
    root, lire = lit_xml(chemin)
    exige(root.get('type') == 'RectilinearGrid', 'Type non RectilinearGrid')
    p = root.find('RectilinearGrid/Piece')
    e = list(map(int, p.get('Extent').split()))
    nx, ny, nz = (e[1]-e[0]+1, e[3]-e[2]+1, e[5]-e[4]+1)
    coord = [lire(a) for a in p.find('Coordinates')]
    exige([len(a) for a in coord] == [nx, ny, nz], 'Coordonnees VTR incoherentes')
    data = {}
    for a in p.find('PointData'):
        v = lire(a)
        exige(v.shape == (nx*ny*nz, 3), 'Tableau VTR non vectoriel attendu')
        data[a.get('Name')] = v.reshape(nz, ny, nx, 3)
    return dict(x=coord[0], y=coord[1], z=coord[2]), data


def lit_vtp(chemin):
    root, lire = lit_xml(chemin)
    exige(root.get('type') == 'PolyData', 'Type non PolyData')
    p = root.find('PolyData/Piece')
    points = lire(p.find('Points/DataArray'))
    con = lire(p.find("Lines/DataArray[@Name='connectivity']"))
    offsets = lire(p.find("Lines/DataArray[@Name='offsets']"))
    exige(points.shape == (int(p.get('NumberOfPoints')), 3), 'Points VTP incoherents')
    exige(len(offsets) == int(p.get('NumberOfLines')) and
          np.array_equal(offsets, 2*np.arange(1, len(offsets)+1)), 'Segments VTP non binaires')
    exige(len(con) == 2*len(offsets), 'Connectivite VTP incoherente')
    return points, con.reshape(-1, 2)
