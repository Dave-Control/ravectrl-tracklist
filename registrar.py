"""
Registro de canciones de RAVE//CTRL - version para GitHub Actions.
Se ejecuta una vez por corrida (GitHub lo lanza cada 10 minutos)
y agrega a canciones.csv las canciones nuevas.
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


def main():
    vistos = set()
    ultima = None  # ultima cancion guardada, para evitar repeticiones
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        vistos = {fila["ts"] for fila in filas}
        if filas:
            ultima = filas[-1]

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
    nuevos.sort(key=lambda x: int(x["ts"]))

    # El sistema de la radio a veces reporta la misma cancion dos veces
    # con segundos de diferencia: si se repite en menos de 2 minutos, se ignora.
    filtrados = []
    for t in nuevos:
        if (ultima
                and t["artista"] == ultima["artista"]
                and t["titulo"] == ultima["titulo"]
                and int(t["ts"]) - int(ultima["ts"]) < 120_000):
            continue
        filtrados.append(t)
        ultima = t
    nuevos = filtrados

    if not nuevos:
        print("Sin canciones nuevas.")
        return

    existe = os.path.exists(ARCHIVO)
    with open(ARCHIVO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fecha", "hora", "artista", "titulo", "ts"])
        if not existe:
            w.writeheader()
        w.writerows(nuevos)
    for t in nuevos:
        print(f'{t["fecha"]} {t["hora"]}  {t["artista"]} - {t["titulo"]}')


if __name__ == "__main__":
    main()
