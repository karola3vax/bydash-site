# Deployment

This project runs as a single Python web service. `server.py` serves the static storefront and the local API.

## Local

```powershell
.\start-backend.ps1
```

Open:

```text
http://127.0.0.1:4193/
```

## Render

1. Push this folder to a GitHub repository.
2. In Render, create a new Blueprint or Web Service from the repository.
3. If using the included `render.yaml`, Render can provision the service automatically.
4. If creating the service manually:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `python server.py`
   - Health check path: `/api/health`
   - Environment variables:
     - `PYTHON_VERSION=3.12.7`
     - `DATA_DIR=/var/data`
   - Add a persistent disk mounted at `/var/data`.

The app reads Render's `PORT` automatically and binds to `0.0.0.0`, which is required for public web traffic.

## Notes

The current checkout is a local iyzico-style demo flow. For real payments, replace it with the official iyzico API flow and keep API keys in Render environment variables.
