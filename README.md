# Atleti News

Bot que recoge noticias del Atlético de Madrid de 3 periódicos deportivos y las publica en GitHub Pages + Telegram.

## Fuentes

| Fuente | Método |
|---|---|
| Mundo Deportivo | RSS dedicado |
| Marca | RSS general (filtrado por URL) |
| AS | RSS |

## Cómo funciona

1. Cada día a las 05:30 CEST, GitHub Actions ejecuta `main.py`
2. El script lee los RSS feeds y filtra artículos nuevos desde la última ejecución
3. Genera una página HTML estática en `docs/` con las noticias del día
4. Actualiza el índice `docs/index.html` con todas las ediciones
5. Envía un resumen a Telegram

## Estructura

```
.github/workflows/news.yml   # Workflow de GitHub Actions
main.py                       # Script principal
requirements.txt              # Dependencias Python
last_run.json                 # Estado de la última ejecución
templates/                    # Plantillas HTML
  ├── index.html              # Plantilla del índice
  └── page.html               # Plantilla de cada día
docs/                         # Páginas generadas (GitHub Pages)
```

## Despliegue

El sitio se sirve desde GitHub Pages: https://jekopena.github.io/atletico-news/

## Configuración

Se necesitan los siguientes GitHub Secrets:

- `BOT_TOKEN` — Token del bot de Telegram
- `CHAT_ID` — ID del chat de Telegram donde se envían las notificaciones

## Ejecución local

```bash
pip install -r requirements.txt
BOT_TOKEN=tu_token CHAT_ID=tu_chat_id python main.py
```

## Ejecución manual

Desde la pestaña **Actions** del repo, pulsar **Run workflow**.
