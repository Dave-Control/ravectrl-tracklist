"""
Registro de canciones de RAVE//CTRL - version para GitHub Actions.
Se ejecuta una vez por corrida y mantiene canciones.csv limpio:
- agrega las canciones nuevas
- quita repeticiones (misma cancion en menos de 10 minutos)
- quita las cortinillas/frases de la estacion
"""

import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

URL = ("https://ravecontrol.com/_serverFn/"
       "50a4176b5a427aacb0a9bc190608058a257fb9339a105927aeb03be4dfac5193")
ARCHIVO = "canciones.csv"
ZONA = ZoneInfo("America/Mexico_City")  # los servidores de GitHub usan hora UTC
VENTANA_MS = 10 * 60 * 1000              # repeticiones dentro de 10 minutos se ignoran
CAMPOS = ["fecha", "hora", "artista", "titulo", "ts"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (registro personal de canciones)",
    "Referer": "https://ravecontrol.com/",
    "Accept": "application/json",
}


def valor(nodo):
    return nodo.get("s") if isinstance(nodo, dict) else nodo


def buscar_tracks(nodo, encontrados):
    if isinstance(nodo, dict):
        p = nodo.get("p")
        if isinstance(p, dict) and "artista" in p.get("k", []):
            encontrados.append(dict(zip(p["k"], (valor(v) for v in p["v"]))))
        for v in nodo.values():
            buscar_tracks(v, encontrados)
    elif isinstance(nodo, list):
        for v in nodo:
            buscar_tracks(v, encontrados)
    return encontrados


def limpiar(titulo):
    titulo = (titulo or "").strip()
    for ext in (".mp3", ".wav", ".flac", ".m4a", ".aac"):
        if titulo.lower().endswith(ext):
            titulo = titulo[: -len(ext)]
    return titulo


def es_cortinilla(t):
    """Frases, identificaciones, huecos vacios y avisos del sistema: no son canciones."""
    a, ti = t["artista"].strip().lower(), t["titulo"].strip().lower()
    texto = f"{a} {ti}"
    if ti in ("", "-") and a in ("", "-"):
        return True                                   # registro vacio
    if a == "libretime" or ti == "offline":
        return True                                   # aviso del sistema de la radio
    if a.startswith("frase") or ti.startswith("frase"):
        return True                                   # cortinillas "FRASE ..."
    return any(x in texto for x in ("rave ctrl", "rave//ctrl", "rave-ctrl", "ravectrl"))


def quitar_artista_repetido(t):
    """'Claptone - Beautiful Times' en el titulo -> 'Beautiful Times'."""
    pref = t["artista"].strip() + " - "
    if t["artista"].strip() and t["titulo"].lower().startswith(pref.lower()):
        t["titulo"] = t["titulo"][len(pref):].strip()
    return t


def clave(t):
    """Identifica la cancion aunque artista y titulo vengan invertidos."""
    return frozenset([t["artista"].lower(), t["titulo"].lower()])


def depurar(filas):
    filas = sorted(filas, key=lambda x: int(x["ts"]))
    limpias, ultima_vez = [], {}
    for t in filas:
        if es_cortinilla(t):
            continue
        t = quitar_artista_repetido(t)
        k, ts = clave(t), int(t["ts"])
        if limpias and clave(limpias[-1]) == k:
            ultima_vez[k] = ts  # igual a la anterior (p. ej. programa que se re-anuncia): se omite
            continue
        if k in ultima_vez and ts - ultima_vez[k] < VENTANA_MS:
            ultima_vez[k] = ts  # sigue "sonando": extiende la ventana
            continue
        ultima_vez[k] = ts
        limpias.append(t)
    return limpias


def main():
    filas = []
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
    vistos = {fila["ts"] for fila in filas}

    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()

    nuevos = []
    for t in buscar_tracks(r.json(), []):
        ts = str(t["ts"])
        if ts in vistos:
            continue
        momento = datetime.fromtimestamp(int(ts) / 1000, tz=ZONA)
        nuevos.append({
            "fecha": momento.strftime("%Y-%m-%d"),
            "hora": momento.strftime("%H:%M:%S"),
            "artista": (t.get("artista") or "").strip(),
            "titulo": limpiar(t.get("titulo")),
            "ts": ts,
        })

    antes = len(filas)
    resultado = depurar(filas + nuevos)

    with open(ARCHIVO, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(resultado)

    print(f"Antes: {antes} filas | nuevas consultadas: {len(nuevos)} | ahora: {len(resultado)}")


if __name__ == "__main__":
    main()
