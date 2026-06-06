# Plan: Atleti News Bot

## Resumen

Script Python que cada mañana a las 6:00 AM (hora Madrid) lee RSS feeds de 3 periódicos deportivos, filtra noticias del Atlético de Madrid nuevas desde la última ejecución, y envía un mensaje a Telegram. Se ejecuta con GitHub Actions y guarda el estado en `last_run.json`.

## Fuentes de datos

| Fuente | Tipo | URL | Método |
|---|---|---|---|
| Mundo Deportivo | RSS dedicado | `https://www.mundodeportivo.com/rss/futbol/atletico-madrid` | `feedparser` — ya filtrado |
| Marca | RSS general | `https://www.marca.com/futbol/atletico.html` | `feedparser` + filtrar por link que contenga `/futbol/atletico/` |
| AS | HTML | `https://as.com/noticias/atletico-madrid/` | `requests` + `beautifulsoup4` |

## Estructura del proyecto

```
atletico-news/
├── .github/
│   └── workflows/
│       └── news.yml
├── main.py
├── requirements.txt
├── last_run.json
└── PLAN.md
```

## Tareas y dependencias

### Tarea 1: Configurar GitHub Secrets

- **Descripción**: Guardar `BOT_TOKEN` y `CHAT_ID` como GitHub Secrets del repo
- **Dependencias**: Ninguna
- **Nota**: El token fue expuesto en el chat. Después de guardar el secret, regenerar el token con `/revoke` en BotFather y actualizar el secret

### Tarea 2: Crear `requirements.txt`

- **Descripción**: Dependencias Python
- **Contenido**: `feedparser`, `requests`, `beautifulsoup4`
- **Dependencias**: Ninguna

### Tarea 3: Crear `main.py`

- **Descripción**: Script principal
- **Dependencias**: Tarea 2
- **Lógica**:
  1. Leer `last_run.json` (si no existe, usar hace 24h como fallback)
  2. Fetch de las 3 fuentes:
     - Mundo Deportivo: parsear RSS con `feedparser`
     - Marca: parsear RSS con `feedparser`, filtrar entries cuyo link contenga `/futbol/atletico/`
     - AS: parsear HTML con BeautifulSoup, extraer artículos de la lista
  3. Para cada artículo, extraer: título, URL, fecha, fuente
  4. Filtrar artículos con fecha posterior a `last_run`
  5. Deduplicar por URL
  6. Formatear mensaje y enviar a Telegram con `requests` a `https://api.telegram.org/bot<TOKEN>/sendMessage`
  7. Actualizar `last_run.json` con timestamp actual
  8. Hacer commit y push de `last_run.json`

- **Formato del mensaje Telegram**:
  ```
  ⚽ Noticias del Atlético - 06/06/2026

  📰 Mundo Deportivo
  • Título noticia 1
  • Título noticia 2

  📰 Marca
  • Título noticia 3

  📰 AS
  ⚠️ No se pudieron obtener noticias de esta fuente
  ```

- **Manejo de errores por fuente**: Si una fuente falla, incluir en el mensaje un aviso como `⚠️ No se pudieron obtener noticias de [fuente]` en lugar de esa sección. Las demás fuentes se procesan normalmente.

- **Formato de `last_run.json`**:
  ```json
  {
    "last_run": "2026-06-06T07:00:00+02:00"
  }
  ```

### Tarea 4: Crear `.github/workflows/news.yml`

- **Descripción**: Workflow de GitHub Actions
- **Dependencias**: Tarea 3
- **Configuración**:
  - Trigger `schedule`: cron `0 4 * * *` (4:00 UTC = 6:00 AM CEST en verano)
  - Trigger `workflow_dispatch`: para ejecución manual
  - Steps:
    1. `actions/checkout@v4`
    2. Setup Python 3.12
    3. `pip install -r requirements.txt`
    4. `python main.py`
    5. Configurar git con bot identity
    6. `git add last_run.json && git commit && git push` (solo si hay cambios)
  - Variables de entorno: `BOT_TOKEN` y `CHAT_ID` desde GitHub Secrets

### Tarea 5: Verificar y probar

- **Descripción**: Ejecutar el workflow manualmente y verificar que:
  - Llega el mensaje a Telegram
  - `last_run.json` se actualiza y commitea
  - Los 3 parsers funcionan (o muestran aviso de error)
- **Dependencias**: Tareas 1, 3, 4

## Grafo de dependencias

```
Tarea 1 (Secrets) ─────────────────────────┐
                                             ├─> Tarea 5 (Verificar)
Tarea 2 (requirements.txt) ─> Tarea 3 (main.py) ─> Tarea 4 (workflow) ─┘
```

## Notas técnicas

- **AS scraping**: La página carga artículos en HTML inicial (no es SPA), `requests` + BS4 funciona
- **Marca RSS**: `marca.com/futbol/atletico.html` devuelve RSS en fetch simple, sin necesidad de navegador
- **Deduplicación**: Usar la URL del artículo como clave única
- **Timezone**: Usar UTC en `last_run.json` para evitar ambigüedades. El cron de GitHub Actions siempre corre en UTC. 4:00 UTC = 6:00 AM en horario de verano de Madrid (CEST). En invierno (CET) serían las 5:00 AM Madrid.
- **Error handling**: Si una fuente falla, continuar con las demás y avisar en el mensaje de Telegram
