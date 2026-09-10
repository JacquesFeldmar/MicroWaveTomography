"""
TUTORIEL VIDEO -- genere, et REGENERE, la video de prise en main.

POURQUOI UN GENERATEUR PLUTOT QU'UNE VIDEO
    Une video montee a la main est un bloc fige que rien ne verifie. Ce projet a
    deja vu deux fois la documentation deriver sans que rien ne previenne. Ici
    tout est reconstruit a la demande : les copies d'ecran proviennent des
    programmes reellement executes en mode simule, et le texte de narration est
    versionne a cote du code.

        python tutoriel.py            image + sous-titres, sans voix
        python tutoriel.py --voix     avec synthese vocale ElevenLabs
        python tutoriel.py --segment 3   ne refaire qu'un segment

LA CLE API
    Jamais dans un fichier du depot ni sur une ligne de commande : le programme
    la lit dans la variable d'environnement ELEVENLABS_API_KEY.

        setx ELEVENLABS_API_KEY "..."

SORTIE
    docs/tutoriel/tutoriel.mp4  et les segments individuels a cote.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request


# La console Windows est souvent en cp1252 : elle ne sait pas ecrire les
# accents du tutoriel et le programme mourait sur un UnicodeEncodeError au
# moment d afficher un titre de segment. On tolere la substitution plutot
# que d interdire les accents.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

_ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(_ICI, "docs", "tutoriel")
TRAVAIL = os.path.join(SORTIE, "travail")

L, H = 1920, 1080
MARGE = 60
FOND = (252, 252, 251)
ENCRE = (11, 11, 11)
ENCRE2 = (82, 81, 78)
BLEU = (42, 120, 214)
ORANGE = (235, 104, 52)
AQUA = (27, 175, 122)
BANDE = (238, 243, 250)

POLICES = {
    "titre": ("C:/Windows/Fonts/segoeuib.ttf", 54),
    "soustitre": ("C:/Windows/Fonts/segoeui.ttf", 34),
    "legende": ("C:/Windows/Fonts/segoeui.ttf", 30),
    "mono": ("C:/Windows/Fonts/consola.ttf", 24),
    "mono_gros": ("C:/Windows/Fonts/consola.ttf", 30),
    "petit": ("C:/Windows/Fonts/segoeui.ttf", 24),
}


_CACHE_POLICES = {}


def _police(nom):
    """Charge une police UNE SEULE FOIS.

    Sans ce cache, chaque image rouvrait le fichier TTF quatre a cinq fois,
    soit pres de deux cents ouvertures sur l ensemble du tutoriel. Les objets
    FreeType gardent le descripteur ouvert : au bout d un certain nombre, le
    processus est tue sans message ni trace.
    """
    if nom not in _CACHE_POLICES:
        from PIL import ImageFont
        ch, taille = POLICES[nom]
        try:
            _CACHE_POLICES[nom] = ImageFont.truetype(ch, taille)
        except OSError:
            _CACHE_POLICES[nom] = ImageFont.load_default()
    return _CACHE_POLICES[nom]


# ======================================================================
# FABRIQUE D'IMAGES
# ======================================================================
def _cadre(titre, segment=None, total=None):
    """Image vierge avec le bandeau de titre et l'avancement."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (L, H), FOND)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, L, 110], fill=BANDE)
    d.line([0, 110, L, 110], fill=(201, 207, 214), width=2)
    d.text((MARGE, 30), titre, font=_police("titre"), fill=ENCRE)
    if segment is not None:
        t = f"{segment}/{total}"
        f = _police("soustitre")
        larg = d.textlength(t, font=f)
        d.text((L - MARGE - larg, 42), t, font=f, fill=ENCRE2)
    return im, d


def _legende(im, d, texte):
    """Bande de sous-titre en bas : la video reste utile en sourdine."""
    f = _police("legende")
    lignes = textwrap.wrap(texte, width=110)[:3]
    haut = H - 40 - 46 * len(lignes)
    d.rectangle([0, haut - 26, L, H], fill=(245, 246, 248))
    d.line([0, haut - 26, L, haut - 26], fill=(220, 224, 228), width=2)
    for i, ln in enumerate(lignes):
        larg = d.textlength(ln, font=f)
        d.text(((L - larg) / 2, haut + 46 * i), ln, font=f, fill=ENCRE)
    return haut - 40


def image_titre(titre, sous, legende, segment, total):
    from PIL import ImageDraw
    im, d = _cadre("", segment, total)
    d.rectangle([0, 0, L, 110], fill=FOND)
    f1, f2 = _police("titre"), _police("soustitre")
    larg = d.textlength(titre, font=f1)
    d.text(((L - larg) / 2, 380), titre, font=f1, fill=BLEU)
    for i, ln in enumerate(textwrap.wrap(sous, width=70)):
        lg = d.textlength(ln, font=f2)
        d.text(((L - lg) / 2, 480 + 46 * i), ln, font=f2, fill=ENCRE2)
    _legende(im, d, legende)
    return im


def image_console(titre, texte, legende, segment, total, surligne=()):
    """Rend un extrait de console. Les lignes contenant un motif de `surligne`
    sont mises en evidence : c'est la ou il faut regarder."""
    from PIL import ImageDraw
    im, d = _cadre(titre, segment, total)
    bas = _legende(im, d, legende)
    f = _police("mono")
    y = 150
    x = MARGE + 24
    d.rectangle([MARGE, 140, L - MARGE, bas], fill=(248, 249, 250),
                outline=(223, 227, 232), width=2)
    for ligne in texte.split("\n"):
        if y > bas - 34:
            break
        couleur = ENCRE
        for motif, col in surligne:
            if motif in ligne:
                couleur = col
                d.rectangle([MARGE + 8, y - 4, L - MARGE - 8, y + 30],
                            fill=(255, 248, 225))
                break
        d.text((x, y), ligne[:120], font=f, fill=couleur)
        y += 32
    return im


def image_capture(titre, chemin, legende, segment, total, fleches=()):
    """Insere une copie d'ecran reelle, avec des fleches d'annotation."""
    from PIL import Image, ImageDraw
    im, d = _cadre(titre, segment, total)
    bas = _legende(im, d, legende)
    src = Image.open(chemin).convert("RGB")
    dispo_l, dispo_h = L - 2 * MARGE, bas - 150
    k = min(dispo_l / src.width, dispo_h / src.height)
    src = src.resize((int(src.width * k), int(src.height * k)),
                     Image.LANCZOS)
    ox, oy = (L - src.width) // 2, 140 + (dispo_h - src.height) // 2
    im.paste(src, (ox, oy))
    d.rectangle([ox - 2, oy - 2, ox + src.width + 2, oy + src.height + 2],
                outline=(201, 207, 214), width=2)
    f = _police("petit")
    for (fx, fy, texte, cote) in fleches:
        px, py = ox + int(fx * src.width), oy + int(fy * src.height)
        d.ellipse([px - 13, py - 13, px + 13, py + 13], outline=ORANGE, width=4)
        larg = d.textlength(texte, font=f)
        tx = px + 24 if cote == "d" else px - 24 - larg
        d.rectangle([tx - 8, py - 20, tx + larg + 8, py + 18],
                    fill=(255, 255, 255), outline=ORANGE, width=2)
        d.text((tx, py - 16), texte, font=f, fill=ORANGE)
    return im


def image_tableau(titre, entetes, lignes, legende, segment, total):
    from PIL import ImageDraw
    im, d = _cadre(titre, segment, total)
    bas = _legende(im, d, legende)
    f, fg = _police("legende"), _police("soustitre")
    n = len(entetes)
    larg = (L - 2 * MARGE) / n
    y = 200
    d.rectangle([MARGE, y - 14, L - MARGE, y + 52], fill=BANDE)
    for i, e in enumerate(entetes):
        d.text((MARGE + 24 + i * larg, y), e, font=fg, fill=ENCRE)
    y += 70
    for k, ligne in enumerate(lignes):
        if y > bas - 60:
            break
        if k % 2:
            d.rectangle([MARGE, y - 10, L - MARGE, y + 48],
                        fill=(250, 251, 252))
        for i, cel in enumerate(ligne):
            col = BLEU if cel.startswith("*") else ENCRE
            d.text((MARGE + 24 + i * larg, y), cel.lstrip("*"), font=f,
                   fill=col)
        y += 58
    return im


# ======================================================================
# SYNTHESE VOCALE
# ======================================================================
# Voix "premade" d'ElevenLabs : identifiants stables, disponibles sur tous les
# comptes. Sert de repli quand la cle n'a pas la permission voices_read.
VOIX_CONNUES = {
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "rachel":    "21m00Tcm4TlvDq8ikWAM",
    "antoni":    "ErXwobaYiN019PkySvjV",
    "bella":     "EXAVITQu4vr4xnSDxMaL",
    "adam":      "pNInz6obpgDQGcFmaJgB",
}
VOIX_DEFAUT = VOIX_CONNUES["charlotte"]     # timbre feminin, bon en francais


def _appel(url, cle, corps=None, accept=None, timeout=120):
    """Appel HTTP qui remonte le MESSAGE de l'API, pas seulement le code.

    Un '401 Unauthorized' nu n'apprend rien ; le corps de la reponse dit
    precisement s'il s'agit d'une cle invalide, d'une permission manquante ou
    d'un quota epuise.
    """
    entetes = {"xi-api-key": cle}
    if corps is not None:
        entetes["Content-Type"] = "application/json"
    if accept:
        entetes["Accept"] = accept
    req = urllib.request.Request(url, data=corps, headers=entetes)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        brut = e.read().decode("utf-8", "replace")
        try:
            d = json.loads(brut).get("detail", {})
            msg = d.get("message", brut) if isinstance(d, dict) else str(d)
            code = d.get("status", d.get("code", "")) if isinstance(d, dict) else ""
        except Exception:
            msg, code = brut[:300], ""
        raise ErreurAPI(e.code, code, msg) from None


class ErreurAPI(Exception):
    def __init__(self, http, code, message):
        self.http, self.code, self.message = http, code, message
        super().__init__(f"HTTP {http} [{code}] {message}")


def nettoie_cle(brut):
    """Retire les scories de collage : espaces, guillemets, retours ligne.

    Coller une cle en PowerShell laisse regulierement les guillemets dans la
    VALEUR, ou un retour a la ligne invisible. Mieux vaut le corriger que de
    laisser echouer le 37e appel.
    """
    c = (brut or "").strip().strip('"').strip("'").strip()
    return "".join(c.split())          # supprime tout blanc interne


def controle_cle(cle):
    """Rend (ok, message). Une cle ElevenLabs fait 51 caracteres et commence
    par 'sk_'."""
    if not cle:
        return False, "cle vide"
    if not cle.startswith("sk_"):
        return False, (f"prefixe {cle[:3]!r} : une cle commence par 'sk_'. "
                       "Tu as peut-etre copie l'IDENTIFIANT de la cle, "
                       "visible dans le tableau de bord, au lieu de la cle "
                       "elle-meme, affichee une seule fois a sa creation.")
    if len(cle) != 51:
        return False, (f"longueur {len(cle)} au lieu de 51. "
                       + ("Il y a probablement deux valeurs collees bout a "
                          "bout." if len(cle) > 51 else "La valeur est "
                          "tronquee."))
    return True, "51 caracteres, prefixe 'sk_'"


def voix(texte, chemin, voix_id, cle):
    """ElevenLabs. Met en cache : un texte inchange n'est pas resynthetise."""
    if os.path.exists(chemin):
        return chemin
    corps = json.dumps({
        "text": texte,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75,
                           "style": 0.0, "use_speaker_boost": True},
    }).encode("utf-8")
    data = _appel(f"https://api.elevenlabs.io/v1/text-to-speech/{voix_id}",
                  cle, corps, accept="audio/mpeg")
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    # Un commentaire se paie a l appel : on verifie qu il est bien sur le
    # disque avant de continuer. Sans ce controle, un cache qui ne se
    # remplit pas se traduit par une refacturation silencieuse a chaque
    # relance, sans que rien ne le signale.
    if not os.path.exists(chemin) or os.path.getsize(chemin) < 1000:
        raise RuntimeError(
            "commentaire synthetise mais absent du disque : " + chemin
            + " (" + str(len(data)) + " octets recus)")
    return chemin


def choisir_voix(cle, demandee=None):
    """Rend (voix_id, nom).

    Si la cle n'a pas le droit de lister les voix -- ce qui est frequent, la
    permission voices_read etant separee de text_to_speech -- on se rabat sur
    un identifiant connu au lieu d'echouer.
    """
    if demandee and len(demandee) == 20 and " " not in demandee:
        return demandee, demandee                      # deja un identifiant
    if demandee and demandee.lower() in VOIX_CONNUES:
        return VOIX_CONNUES[demandee.lower()], demandee
    try:
        dispo = json.loads(_appel("https://api.elevenlabs.io/v1/voices", cle,
                                  timeout=60))["voices"]
    except ErreurAPI as e:
        print(f"  [voix] impossible de lister les voix : {e.message[:110]}")
        print(f"  [voix] repli sur une voix standard "
              f"({'Charlotte' if demandee is None else demandee}).")
        vid = VOIX_CONNUES.get((demandee or "charlotte").lower(), VOIX_DEFAUT)
        return vid, (demandee or "Charlotte") + " (repli)"
    if demandee:
        for v in dispo:
            if demandee.lower() in v["name"].lower():
                return v["voice_id"], v["name"]
    for v in dispo:
        if "multilingual" in json.dumps(v.get("labels", {})).lower():
            return v["voice_id"], v["name"]
    return dispo[0]["voice_id"], dispo[0]["name"]


def essai_synthese(cle, voix_id):
    """Un appel minimal, pour verifier les DROITS avant de tout lancer.

    Le controle de longueur ne dit rien des permissions : une cle bien formee
    peut n'avoir aucun droit. Quatre caracteres de synthese coutent une
    fraction de centime et evitent d'echouer au milieu d'une generation.
    """
    corps = json.dumps({"text": "test",
                        "model_id": "eleven_multilingual_v2"}).encode("utf-8")
    try:
        _appel(f"https://api.elevenlabs.io/v1/text-to-speech/{voix_id}",
               cle, corps, accept="audio/mpeg", timeout=60)
        return True, "synthese autorisee"
    except ErreurAPI as e:
        if e.code == "missing_permissions":
            return False, ("il manque a la cle la permission "
                           "'text_to_speech'. Sur elevenlabs.io > My Account "
                           "> API Keys, modifie la cle et coche Text to "
                           "Speech, ou cree-en une avec ce droit.")
        if "credit" in e.message.lower() or "quota" in e.message.lower():
            return False, "credits epuises : " + e.message[:90]
        return False, f"HTTP {e.http} -- {e.message[:110]}"


def diagnostic(cle):
    """Dit precisement ce que la cle permet ou non."""
    print("=" * 74)
    print("  DIAGNOSTIC DE LA CLE ELEVENLABS")
    print("=" * 74)
    print(f"  longueur {len(cle)}, prefixe {cle[:3]!r}"
          + ("" if cle.startswith("sk_") else
             "   <-- une vraie cle commence par 'sk_'"))
    ok_synthese = False
    for libelle, essai in (
            ("lire le compte      ",
             lambda: _appel("https://api.elevenlabs.io/v1/user", cle, timeout=30)),
            ("lister les voix     ",
             lambda: _appel("https://api.elevenlabs.io/v1/voices", cle, timeout=30)),
            ("SYNTHETISER (le seul droit indispensable)",
             lambda: _appel(
                 f"https://api.elevenlabs.io/v1/text-to-speech/{VOIX_DEFAUT}",
                 cle,
                 json.dumps({"text": "test", "model_id": "eleven_multilingual_v2"}
                            ).encode("utf-8"),
                 accept="audio/mpeg", timeout=60))):
        try:
            essai()
            print(f"  {libelle} : OK")
            if libelle.startswith("SYNTH"):
                ok_synthese = True
        except ErreurAPI as e:
            print(f"  {libelle} : HTTP {e.http} -- {e.message[:90]}")
    print()
    if ok_synthese:
        print("  -> La synthese fonctionne. Le tutoriel peut etre genere :")
        print("     python tutoriel_contenu.py --voix")
    else:
        print("  -> La synthese ne fonctionne pas. Verifie, sur")
        print("     elevenlabs.io > My Account > API Keys, que la cle a bien")
        print("     la permission 'text_to_speech', et qu'il reste des credits.")
    return ok_synthese


# ======================================================================
# ASSEMBLAGE
# ======================================================================
def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# Sous Windows, un sous-processus lance sans precaution s attache a la
# console du parent et y installe son propre gestionnaire d evenements. La
# generation mourait alors par grappes -- parent et enfant ensemble, sans
# message, sans trace et avec un code de sortie nul. CREATE_NO_WINDOW
# detache completement ffmpeg de la console : il ne peut plus rien y
# envoyer. Sur les autres systemes l indicateur n existe pas et vaut zero.
SANS_CONSOLE = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# Les commentaires synthetises sont les seuls artefacts couteux : ils se
# paient a l appel. Le dossier de travail, lui, est massivement reecrit a
# chaque passage. On les separe donc, pour qu un menage -- le notre ou
# celui d un tiers -- sur les fichiers jetables ne detruise pas ce qui a
# ete facture.
VOIX = os.path.join(SORTIE, "voix")


def _run(args):
    """Lance ffmpeg sans jamais lui donner l'entree standard.

    Par defaut ffmpeg LIT stdin, pour ses commandes interactives. Appele
    plusieurs dizaines de fois dans une boucle, il consomme l'entree du
    processus parent -- ce qui interrompt silencieusement le programme,
    et sous PowerShell peut emporter la console. '-nostdin' et un stdin
    explicitement vide suppriment les deux effets.
    """
    args = [args[0], "-nostdin"] + list(args[1:])
    r = subprocess.run(args, capture_output=True, text=True,
                       stdin=subprocess.DEVNULL,
                       creationflags=SANS_CONSOLE)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg a echoue :" + chr(10) + r.stderr[-1200:])


def film_habille(titre, dossier_src, legende, segment, total, dossier_dst,
                fleches=()):
    """Habille chaque image d'une sequence comme une copie d'ecran unique.

    Rend le nombre d'images produites. L'habillage est identique d'une
    image a l'autre : seul le contenu de la fenetre change, ce qui evite
    tout scintillement du titre ou du sous-titre.
    """
    import glob
    import shutil

    sources = sorted(glob.glob(os.path.join(dossier_src, "*.png")))
    if not sources:
        raise RuntimeError("aucune image dans " + dossier_src)
    if os.path.isdir(dossier_dst):
        shutil.rmtree(dossier_dst)
    os.makedirs(dossier_dst)
    for k, src in enumerate(sources, 1):
        im = image_capture(titre, src, legende, segment, total, fleches)
        im.save(os.path.join(dossier_dst, "%04d.png" % k))
    return len(sources)


def plan_film_vers_mp4(dossier, audio, duree, sortie, fps=12):
    """Un plan anime : une suite d'images, bouclee jusqu'a la fin du son.

    -stream_loop repete la sequence autant de fois qu'il faut ; -t fixe la
    duree, comme pour un plan fixe, faute de quoi x264 depasse la fin du
    commentaire de plusieurs secondes.
    """
    exe = ffmpeg()
    motif = os.path.join(dossier, "%04d.png")
    if audio:
        d = duree_de(audio)
        _run([exe, "-y", "-stream_loop", "-1", "-framerate", str(fps),
              "-i", motif, "-i", audio,
              "-c:v", "libx264", "-preset", "medium", "-crf", "23",
              "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
              "-t", "%.3f" % d, "-shortest", "-r", str(fps), sortie])
    else:
        _run([exe, "-y", "-stream_loop", "-1", "-framerate", str(fps),
              "-i", motif, "-f", "lavfi",
              "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
              "-c:v", "libx264", "-preset", "medium", "-crf", "23",
              "-c:a", "aac", "-b:a", "64k", "-pix_fmt", "yuv420p",
              "-t", "%.3f" % duree, "-shortest", "-r", str(fps), sortie])


def plan_vers_mp4(image, audio, duree, sortie):
    """Un plan = une image fixe + son commentaire.

    Avec audio, la duree du plan est celle du commentaire ('-shortest').
    Sans audio, elle est estimee d'apres la longueur du texte, et une
    piste silencieuse est ajoutee pour que tous les plans se concatenent
    sans rupture de flux.
    """
    exe = ffmpeg()
    if audio:
        # -shortest ne suffit pas : l image bouclee est un flux infini, et
        # x264 vide son tampon d anticipation avant de s arreter. Le plan
        # depassait ainsi son commentaire de six secondes, soit plus de
        # trois minutes de silence mort sur les trente-six plans. On impose
        # donc la duree mesuree du commentaire.
        d = duree_de(audio)
        _run([exe, "-y", "-loop", "1", "-i", image, "-i", audio,
              "-c:v", "libx264", "-tune", "stillimage", "-preset", "medium",
              "-crf", "23", "-c:a", "aac", "-b:a", "160k",
              "-pix_fmt", "yuv420p", "-t", "%.3f" % d,
              "-shortest", "-r", "12", sortie])
    else:
        _run([exe, "-y", "-loop", "1", "-i", image, "-t", str(duree),
              "-f", "lavfi",
              "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
              "-c:v", "libx264", "-tune", "stillimage", "-preset", "medium",
              "-crf", "23", "-c:a", "aac", "-b:a", "64k",
              "-pix_fmt", "yuv420p", "-shortest", "-r", "12", sortie])


def concatene(fichiers, sortie):
    """Assemble des mp4 deja encodes, sans re-encoder."""
    liste = os.path.join(TRAVAIL, "liste.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for x in fichiers:
            f.write("file '" + x.replace(chr(92), '/') + "'" + chr(10))
    _run([ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", liste,
          "-c", "copy", sortie])


def duree_de(fichier):
    exe = ffmpeg()
    # meme precaution que _run : ffmpeg lit stdin par defaut, et
    # -i sans sortie le fait quitter en erreur apres avoir consomme
    # l entree du parent.
    r = subprocess.run([exe, "-nostdin", "-i", fichier],
                       capture_output=True, text=True,
                       stdin=subprocess.DEVNULL,
                       creationflags=SANS_CONSOLE)
    for ligne in r.stderr.split("\n"):
        if "Duration:" in ligne:
            hms = ligne.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


if __name__ == "__main__":
    print(__doc__)
    print("  Ce module fournit la fabrique d'images et l'assemblage.")
    print("  Le contenu des six segments est dans tutoriel_contenu.py.")
