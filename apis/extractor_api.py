# ============================================================================
# EXTRACCIÓN API-FOOTBALL - COPA MUNDIAL
# ============================================================================
# Taller 1
# ============================================================================
#
# Nota: el plan gratuito de API-Sports no permite consultar season=2026
# (el mensaje de error indica que solo hay acceso a las temporadas 2022-2024).
# Por eso se usa season=2022, correspondiente al Mundial de Qatar 2022,
# manteniendo league=1 (Copa Mundial) como pide el taller.

import json
import os
import time
from datetime import datetime

import pandas as pd
import requests
from dotenv import load_dotenv


# ============================================================================
# CONFIGURACIÓN GENERAL
# ============================================================================

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(OUTPUT_DIR, "cache")

load_dotenv(os.path.join(OUTPUT_DIR, ".env"))

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": os.getenv("API_SPORTS_KEY")}

LEAGUE_ID = 1
SEASON = 2022

EXTRAIDO_POR = "Pablo y Pedro"


# ============================================================================
# CONSULTA A LA API (CON PAGINACIÓN Y CACHE EN DISCO)
# ============================================================================

def consultar_api(endpoint, params):
    """
    Consulta un endpoint de API-Football recorriendo todas las páginas
    que indique la respuesta (campo 'paging').
    """
    resultados = []
    pagina = 1

    while True:
        params_pagina = params if pagina == 1 else {**params, "page": pagina}
        response = requests.get(BASE_URL + endpoint, headers=HEADERS, params=params_pagina)
        response.raise_for_status()
        data = response.json()

        if data.get("errors"):
            raise RuntimeError(f"Error consultando {endpoint}: {data['errors']}")

        resultados.extend(data["response"])

        paging = data.get("paging", {"current": 1, "total": 1})
        print(f"  {endpoint} -> página {paging['current']}/{paging['total']} ({len(data['response'])} registros)")

        if paging["current"] >= paging["total"]:
            break

        pagina += 1
        time.sleep(1)

    return resultados


def obtener_datos(endpoint, params, nombre_cache):
    """
    Consulta un endpoint, pero si ya existe una copia previa en cache/
    la reutiliza en lugar de volver a consultar la API. El plan gratuito
    tiene un límite diario de solicitudes, así que evita repetir consultas
    ya hechas.
    """
    ruta_cache = os.path.join(CACHE_DIR, nombre_cache)

    if os.path.exists(ruta_cache):
        print(f"Usando cache existente: {ruta_cache}")
        with open(ruta_cache, "r", encoding="utf-8") as archivo:
            return json.load(archivo)

    print(f"Consultando {endpoint}...")
    resultados = consultar_api(endpoint, params)

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(ruta_cache, "w", encoding="utf-8") as archivo:
        json.dump(resultados, archivo, ensure_ascii=False)

    return resultados


# ============================================================================
# NORMALIZACIÓN DE CADA ENDPOINT
# ============================================================================

def normalizar_equipo(item):
    team = item["team"]
    return {
        "equipo_id": team["id"],
        "nombre_equipo": team["name"],
        "codigo_equipo": team.get("code"),
        "pais": team.get("country"),
        "anio_fundacion": team.get("founded"),
        "es_seleccion_nacional": team.get("national"),
        "logo_url": team.get("logo"),
        "competencia_id": LEAGUE_ID,
        "temporada": SEASON,
        "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
        "extraido_por": EXTRAIDO_POR,
        "endpoint_origen": "/teams",
    }


def normalizar_partido(item):
    fixture = item["fixture"]
    league = item["league"]
    teams = item["teams"]
    goals = item["goals"]
    penales = item["score"]["penalty"]

    return {
        "partido_id": fixture["id"],
        "competencia_id": league["id"],
        "competencia_nombre": league["name"],
        "temporada": league["season"],
        "ronda": league["round"],
        "fecha_partido": fixture["date"],
        "zona_horaria": fixture["timezone"],
        "estado_partido": fixture["status"]["long"],
        "minuto_transcurrido": fixture["status"]["elapsed"],
        "arbitro": fixture.get("referee"),
        "estadio_id": fixture["venue"].get("id"),
        "estadio_nombre": fixture["venue"].get("name"),
        "estadio_ciudad": fixture["venue"].get("city"),
        "equipo_local_id": teams["home"]["id"],
        "equipo_local_nombre": teams["home"]["name"],
        "equipo_visitante_id": teams["away"]["id"],
        "equipo_visitante_nombre": teams["away"]["name"],
        "gano_local": teams["home"]["winner"],
        "gano_visitante": teams["away"]["winner"],
        "goles_local": goals["home"],
        "goles_visitante": goals["away"],
        "penales_local": penales.get("home"),
        "penales_visitante": penales.get("away"),
        "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
        "extraido_por": EXTRAIDO_POR,
        "endpoint_origen": "/fixtures",
    }


def normalizar_clasificacion(item, competencia_id, temporada):
    team = item["team"]
    todos = item["all"]

    return {
        "grupo": item["group"],
        "posicion": item["rank"],
        "equipo_id": team["id"],
        "nombre_equipo": team["name"],
        "puntos": item["points"],
        "partidos_jugados": todos["played"],
        "partidos_ganados": todos["win"],
        "partidos_empatados": todos["draw"],
        "partidos_perdidos": todos["lose"],
        "goles_favor": todos["goals"]["for"],
        "goles_contra": todos["goals"]["against"],
        "diferencia_gol": item["goalsDiff"],
        "forma_reciente": item["form"],
        "estado_clasificacion": item["status"],
        "descripcion_clasificacion": item.get("description"),
        "fecha_actualizacion": item.get("update"),
        "competencia_id": competencia_id,
        "temporada": temporada,
        "fecha_extraccion": datetime.now().isoformat(timespec="seconds"),
        "extraido_por": EXTRAIDO_POR,
        "endpoint_origen": "/standings",
    }


# ============================================================================
# PROGRAMA PRINCIPAL
# ============================================================================

def main():
    params = {"league": LEAGUE_ID, "season": SEASON}

    equipos_raw = obtener_datos("/teams", params, "teams.json")
    fixtures_raw = obtener_datos("/fixtures", params, "fixtures.json")
    standings_raw = obtener_datos("/standings", params, "standings.json")

    equipos_data = [normalizar_equipo(item) for item in equipos_raw]
    partidos_data = [normalizar_partido(item) for item in fixtures_raw]

    clasificacion_data = []
    for liga in standings_raw:
        competencia_id = liga["league"]["id"]
        temporada = liga["league"]["season"]
        for grupo in liga["league"]["standings"]:
            for equipo_clasificacion in grupo:
                clasificacion_data.append(
                    normalizar_clasificacion(equipo_clasificacion, competencia_id, temporada)
                )

    df_equipos = pd.DataFrame(equipos_data).drop_duplicates(subset="equipo_id")
    df_partidos = pd.DataFrame(partidos_data).drop_duplicates(subset="partido_id")
    df_clasificacion = pd.DataFrame(clasificacion_data).drop_duplicates(subset=["grupo", "equipo_id"])

    df_equipos["anio_fundacion"] = df_equipos["anio_fundacion"].astype("Int64")
    df_equipos["es_seleccion_nacional"] = df_equipos["es_seleccion_nacional"].astype(bool)

    df_partidos["fecha_partido"] = pd.to_datetime(df_partidos["fecha_partido"])
    df_partidos["minuto_transcurrido"] = df_partidos["minuto_transcurrido"].astype("Int64")
    df_partidos["gano_local"] = df_partidos["gano_local"].astype("boolean")
    df_partidos["gano_visitante"] = df_partidos["gano_visitante"].astype("boolean")
    df_partidos["penales_local"] = df_partidos["penales_local"].astype("Int64")
    df_partidos["penales_visitante"] = df_partidos["penales_visitante"].astype("Int64")

    df_clasificacion["fecha_actualizacion"] = pd.to_datetime(df_clasificacion["fecha_actualizacion"])

    df_equipos.to_parquet(os.path.join(OUTPUT_DIR, "equipos.parquet"), index=False)
    df_partidos.to_parquet(os.path.join(OUTPUT_DIR, "partidos.parquet"), index=False)
    df_clasificacion.to_parquet(os.path.join(OUTPUT_DIR, "clasificacion.parquet"), index=False)

    print("\nExtracción completada.")
    print(f"Equipos: {len(df_equipos)} filas")
    print(f"Partidos: {len(df_partidos)} filas")
    print(f"Clasificación: {len(df_clasificacion)} filas")


if __name__ == "__main__":
    main()
