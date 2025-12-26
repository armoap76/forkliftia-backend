# ForkliftIA Backend

API backend para gestionar casos de diagnóstico de montacargas.

## Variables de entorno
- `ADMIN_UIDS`: lista separada por coma con los UID que se consideran administradores (por ejemplo, `ADMIN_UIDS=admin-1,admin-2`). Estos UID pueden modificar cualquier caso.
- `OPENAI_API_KEY`: requerida solo si se usa el endpoint `/diagnosis` para generar diagnósticos.

## Autenticación
Los endpoints de escritura esperan `Authorization: Bearer <uid>` donde `<uid>` es el identificador del solicitante. Si falta el header, la API responde 401. `GET /cases` permanece público.

## Ejecutar localmente
```bash
uvicorn app.main:app --reload
```

## Pruebas manuales de permisos
1. Exporta administradores antes de levantar el servidor:
   ```bash
   export ADMIN_UIDS=admin-1
   ```
2. Crea un caso (requiere `OPENAI_API_KEY`) para obtener un `case_id` asociado a un UID de creador:
   ```bash
   curl -X POST http://localhost:8000/diagnosis \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer owner-123" \
     -d '{
       "brand": "Toyota",
       "model": "8FBM20",
       "series": "A",
       "error_code": "E01",
       "symptom": "No levanta",
       "checks_done": "Batería revisada"
     }'
   ```
   Anota el `case_id` devuelto.
3. Caso permitido (creador):
   ```bash
   curl -X PATCH http://localhost:8000/cases/<case_id>/resolve \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer owner-123" \
     -d '{"resolution_note": "Se reemplazó el contactor principal"}'
   ```
4. Caso no-owner (espera 403):
   ```bash
   curl -X PATCH http://localhost:8000/cases/<case_id>/resolve \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer intruder-999" \
     -d '{"resolution_note": "Intento no autorizado"}'
   ```
5. Caso admin permitido:
   ```bash
   curl -X PATCH http://localhost:8000/cases/<case_id>/resolve \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer admin-1" \
     -d '{"resolution_note": "Validado por admin"}'
   ```

`GET /cases` puede consultarse sin token para verificar el estado final del caso.
