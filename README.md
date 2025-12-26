# ForkliftIA Backend

## Requisitos previos
- Python 3.11+
- Docker y Docker Compose (para entorno local)
- PostgreSQL disponible (local o en la nube)

## Variables de entorno
Configura `DATABASE_URL` con la cadena de conexión de PostgreSQL. Ejemplo local (coincide con `docker-compose.yml`):

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/forkliftia
```

Coloca esta variable en un archivo `.env` en la raíz o expórtala en tu shell.

## Levantar PostgreSQL con Docker Compose

```bash
docker-compose up -d
```

Esto expondrá PostgreSQL en `localhost:5432` con las credenciales por defecto `postgres/postgres` y base de datos `forkliftia`.

## Migraciones con Alembic

Instala dependencias:

```bash
pip install -r requirements.txt
```

Ejecuta las migraciones:

```bash
alembic upgrade head
```

## Importar los casos existentes de JSON (one-shot)

El script lee `app/data/cases.json` y vuelca la información en la base de datos.

```bash
python scripts/import_cases.py --path app/data/cases.json
```

> El script creará el usuario `legacy-import` si no existe y agregará los casos con los campos adicionales requeridos.

## Ejecutar la API localmente

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API leerá `DATABASE_URL` para conectarse a Postgres.

## Pruebas/manual checks sugeridos
- `GET /ping` responde `{ "message": "forkliftia ok" }`.
- `GET /cases` devuelve los casos desde la base de datos.
- `PATCH /cases/{id}` y `PATCH /cases/{id}/resolve` actualizan el estado y guardan `closed_at`/`resolution_note`.
- `POST /diagnosis` crea un caso nuevo usando el token del header `Authorization` como `created_by_uid`.
