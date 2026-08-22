import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

LLAVE_DB = "id_card"
LLAVE_SCRAPER = "documento"


@dataclass
class ResultadoSync:
    """Contenedores del resultado del merge entre df_scraper y df_desde_sqlite."""
    df_insert: pd.DataFrame
    df_update: pd.DataFrame
    df_update_recurrent: pd.DataFrame


def _normalizar_llave(valores: pd.Series) -> pd.Series:
    return valores.astype(str).str.strip()


def construir_dataframes_sync(
                                df_desde_sqlite: pd.DataFrame,
                                df_scraper: pd.DataFrame,
                            ) -> ResultadoSync:
    """
    Genera los 3 dataframes de sincronización usando la llave documento <-> id_card:
      - df_insert: en scraper y NO en base (nuevos en MINCETUR)
      - df_update: en base con is_active=1 y NO en scraper (salieron del registro oficial)
      - df_update_recurrent: en ambos y is_active=0 en base (reaparecieron)
    """
    db = df_desde_sqlite.copy()
    sc = df_scraper.copy()

    db["_key"] = _normalizar_llave(db[LLAVE_DB])
    sc["_key"] = _normalizar_llave(sc[LLAVE_SCRAPER])

    db = db[db["_key"].ne("")]
    sc = sc[sc["_key"].ne("")]

    if "updated_at" in db.columns:
        db = db.sort_values("updated_at", ascending=False)
    db = db.drop_duplicates(subset="_key", keep="first")
    sc = sc.drop_duplicates(subset="_key", keep="first")

    claves_sc = set(sc["_key"])
    claves_db = set(db["_key"])

    df_insert = (
        sc[~sc["_key"].isin(claves_db)]
        .drop(columns=["_key"])
        .reset_index(drop=True)
    )

    mascara_update = (~db["_key"].isin(claves_sc)) & (db["is_active"] == 1)
    df_update = (
        db[mascara_update]
        .drop(columns=["_key"])
        .reset_index(drop=True)
    )

    estado_db = db.set_index("_key")["is_active"]
    en_ambos = sc[sc["_key"].isin(claves_db)].copy()
    en_ambos["_is_active"] = en_ambos["_key"].map(estado_db)
    df_update_recurrent = (
        en_ambos[en_ambos["_is_active"] == 0]
        .drop(columns=["_key", "_is_active"])
        .reset_index(drop=True)
    )

    logger.info(
        "Merge completado: insert=%d | update=%d | recurrent=%d",
        len(df_insert),
        len(df_update),
        len(df_update_recurrent),
    )

    return ResultadoSync(
        df_insert=df_insert,
        df_update=df_update,
        df_update_recurrent=df_update_recurrent,
    )


def _descripcion_fila(fila: dict) -> str:
    documento = fila.get(LLAVE_SCRAPER, fila.get(LLAVE_DB, ""))
    persona = fila.get("persona") or f"{fila.get('first_name', '')} {fila.get('last_name', '')}".strip()
    return f"doc={documento} | persona={persona} | ubigeo={fila.get('ubigeo', '')}"


def recorrer_e_imprimir(nombre: str, df: pd.DataFrame) -> None:
    """Recorre el dataframe imprimiendo cada registro (punto de enganche para la automatización)."""
    print(f"\n=== {nombre}: {len(df)} registro(s) ===")
    for _, fila in df.iterrows():
        print(f"  - {_descripcion_fila(fila.to_dict())}")
