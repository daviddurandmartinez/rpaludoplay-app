# Guía de Presentación: Ludoplay Sync App

---

## ESTRUCTURA DE LA PRESENTACIÓN (15-20 minutos)

1. Apertura: El problema que resolvemos (2 min)
2. Qué hace el sistema (3 min)
3. Cómo funciona técnicamente (5 min)
4. Estado actual y próximos pasos (3 min)
5. Preguntas (2-3 min)

---

## 1. APERTURA — El problema que resolvemos (2 min)

> "Teníamos un problema operativo: cada vez que MINCETUR actualizaba el registro de personas vinculadas al juego, un operador tenía que entrar manualmente al portal, descargar un PDF, revisarlo registro por registro, y actualizar nuestra base de datos. Esto tomaba horas, era propenso a errores, y si se nos escapaba un registro, podíamos tener un problema de cumplimiento normativo."

**Frase clave para el jefe:**
> "Automatizamos un proceso manual que tomaba horas y lo convertimos en un proceso de minutos, garantizando que nuestra base de datos esté siempre sincronizada con el registro oficial."

---

## 2. QUÉ HACE EL SISTEMA (3 min)

### En una oración:
> "El sistema conecta automáticamente con el portal de MINCETUR, descarga la información oficial de jugadores, la compara con nuestra base de datos, y ejecuta los cambios necesarios: altas, bajas y reactivaciones."

### Flujo simple (para el jefe):

```
MINCETUR                    LUDOPLAY APP                    BASE DE DATOS
   │                             │                                │
   │  1. Acceso automático       │                                │
   │◄────────────────────────────│                                │
   │                             │                                │
   │  2. Descarga PDF            │                                │
   │────────────────────────────►│                                │
   │                             │                                │
   │                             │  3. Extrae datos del PDF       │
   │                             │                                │
   │                             │  4. Compara con DB existente   │
   │                             │───────────────────────────────►│
   │                             │                                │
   │                             │  5. Inserta/Desactiva/Reactiva │
   │                             │───────────────────────────────►│
   │                             │                                │
   │                             │  6. Respuesta: qué cambió     │
   │                             │◄───────────────────────────────│
```

### Qué detecta automáticamente:

| Escenario | Qué hace | Ejemplo |
|-----------|----------|---------|
| **Persona nueva** en MINCETUR | La inserta en nuestra DB | Jugador recién registrado |
| **Persona ya no está** en MINCETUR | La desactiva (soft delete) | Registro dado de baja |
| **Persona reapareció** en MINCETUR | La reactiva | Registro que había sido desactivado |

**Frase clave para el jefe:**
> "El sistema no solo agrega nuevos registros, también detecta bajas y reactivaciones. Si alguien ya no está autorizado, nuestro sistema lo detecta automáticamente."

---

## 3. CÓMO FUNCIONA TÉCNICAMENTE (5 min)

### Arquitectura por capas (para equipo técnico):

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPAS DEL SISTEMA                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  SCRAPER    │    │  SERVICE    │    │ REPOSITORY  │     │
│  │  (Selenium) │───►│  (Negocio)  │───►│  (Datos)    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│        │                  │                   │             │
│        ▼                  ▼                   ▼             │
│   MINCETUR            Reglas             SQL Server        │
│   (portal web)        de negocio         (base de datos)   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| Capa | Qué hace | Tecnología |
|------|----------|------------|
| **Scraper** | Ingresa al portal de MINCETUR, descarga y parsea el PDF | Selenium + pdfplumber + PyMuPDF |
| **Service** | Aplica reglas de negocio: qué insertar, qué desactivar, qué reactivar | Python + pandas |
| **Repository** | Ejecuta las operaciones SQL contra la base de datos | SQLAlchemy 2.0 (async) + SQL Server |
| **API** | Expone endpoints para que otros sistemas se conecten | FastAPI |

### Stack tecnológico:

| Componente | Tecnología | Por qué |
|------------|------------|---------|
| Framework web | FastAPI | Rendimiento async, documentación automática |
| ORM | SQLAlchemy 2.0 | Moderno, soporte async, type hints |
| Base de datos | SQL Server | Base de datos corporativa existente |
| Scraping | Selenium | Automatización de navegador para portales web |
| Extracción PDF | pdfplumber + PyMuPDF | Manejo de tablas e imágenes en PDF |
| Datos | pandas | Comparaciones eficientes entre datasets |

### Detalle técnico: El merge (para equipo técnico)

```python
# sync_merger.py — La lógica central
df_insert    = scraper_data[~scraper_data.id_card.isin(db_ids)]      # Nuevos
df_deactivate = db_active[~db_active.id_card.isin(scraper_ids)]       # Bajas
df_reactivate = db_inactive[db_inactive.id_card.isin(scraper_ids)]    # Reactivaciones
```

**En palabras:** Comparamos los IDs del scraper contra los IDs de la DB usando operaciones de conjunto. Lo que está en uno pero no en el otro determina la acción.

### Detalle técnico: Transaccionalidad

```python
# service.py — sync_all()
try:
    await self.deactivate_players(...)  # Paso 1
    await self.reactivate_players(...)  # Paso 2
    await self.insert_players(...)      # Paso 3
except Exception as e:
    await self.repo.rollback()          # Si falla, deshace TODO
```

**En palabras:** Todo se ejecuta dentro de una transacción. Si algo falla en cualquier paso, se revierten todos los cambios. No quedan datos a medias.

### Endpoints disponibles:

| Método | Ruta | Qué hace |
|--------|------|----------|
| `POST` | `/api/v1/players` | Insertar nuevos jugadores |
| `PATCH` | `/api/v1/players/deactivate` | Desactivar por lista de IDs |
| `PATCH` | `/api/v1/players/reactivate` | Reactivar por lista de IDs |
| `POST` | `/api/v1/players/sync` | Sincronización completa (los 3 anteriores juntos) |
| `POST` | `/api/v1/players/{id}/photo` | Subir foto de un jugador |
| `GET` | `/health` | Verificar que el API está funcionando |

---

## 4. ESTADO ACTUAL Y PRÓXIMOS PASOS (3 min)

### Lo que ya funciona:

| Funcionalidad | Estado |
|---------------|--------|
| Scraping automático de MINCETUR | ✅ Funcional |
| Extracción de datos de PDF | ✅ Funcional |
| Comparación inteligente (insert/deactivate/reactivate) | ✅ Funcional |
| Persistencia en SQL Server | ✅ Funcional |
| API REST para operaciones puntuales | ✅ Funcional |
| Gestión de fotos de jugadores | ✅ Funcional |
| Manejo de errores y transaccionalidad | ✅ Funcional |

### Lo que falta (próximos pasos):

| Área | Estado | Prioridad |
|------|--------|-----------|
| Tests automatizados | ❌ No implementado | Alta |
| Contenerización (Docker) | ❌ No implementado | Media |
| Migraciones de DB (Alembic) | ❌ No implementado | Media |
| CI/CD | ❌ No implementado | Baja |
| Monitoreo y alertas | ❌ No implementado | Baja |

**Frase clave para el jefe:**
> "El sistema ya funciona end-to-end. El camino a producción es claro: añadir tests para garantizar estabilidad, containerizar para despliegue consistente, y configurar CI/CD para automatizar la entrega."

---

## 5. PREGUNTAS FRECUENTES (preparar respuestas)

### "¿Es seguro?"
> "Las credenciales se manejan por variables de entorno (.env), no están en el código. El acceso a la DB usa sesiones asíncronas que se cierran automáticamente al finalizar cada petición."

### "¿Qué pasa si MINCETUR cambia su portal?"
> "El scraper usa selectores XPath y reglas de navegación. Si MINCETUR cambia la estructura del portal, habría que actualizar los selectores en `constants.py`. Es un punto de mantenimiento conocido."

### "¿Puede manejar millones de registros?"
> "El sistema usa operaciones bulk (inserción masiva) y comparaciones basadas en pandas. Para volúmenes muy grandes, se podrían optimizar las consultas, pero para el volumen actual de MINCETUR (miles de registros) funciona sin problemas."

### "¿Por qué no usamos Docker?"
> "Es una decisión de prioridad. El sistema ya funciona en el entorno actual. Docker añadiría consistencia en el despliegue, pero no es bloqueante para la funcionalidad."

### "¿Hay documentación?"
> "Sí: `readme.md` documenta el flujo principal, `contexto_general.md` tiene el análisis completo del sistema, y `entities_routes.md` detalla la interacción entre capas."

---

## CHECKLIST ANTES DE LA PRESENTACIÓN

- [ ] Tener el API corriendo (`python main.py --server`)
- [ ] Tener un ejemplo de request/response para mostrar
- [ ] Tener el `contexto_general.md` como referencia
- [ ] Tener el `entities_routes.md` para preguntas técnicas
- [ ] Preparar demo visual del flujo (diagrama en la pantalla)
- [ ] Practicar el discurso de apertura (2 minutos)

---

## FRASES CLAVE PARA RECORDAR

| Para el jefe | Para el equipo técnico |
|--------------|------------------------|
| "Automatizamos un proceso manual" | "Arquitectura en capas con separación de responsabilidades" |
| "Garantizamos cumplimiento normativo" | "Operaciones bulk + transaccionalidad SQL" |
| "El sistema ya funciona end-to-end" | "FastAPI + SQLAlchemy 2.0 async + SQL Server" |
| "El camino a producción es claro" | "Tests, Docker, CI/CD como próximos pasos" |
