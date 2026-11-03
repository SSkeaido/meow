# Citation Accuracy Checker Frontend

## Run

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` and `/health` to `http://127.0.0.1:8000`.

Start the backend first, then run the Vite server. The interface uses the real project, PDF, evidence, retrieval, and batch-audit APIs.

## Environment

Optional:

```bash
VITE_API_BASE_URL=/api
```

Set `VITE_API_BASE_URL=http://127.0.0.1:8000/api` only when the frontend is hosted separately from the Vite proxy. The backend allows the local Vite origins by default; configure `CORS_ALLOW_ORIGINS` before a deployed frontend is connected.

When the backend returns HTTP 401, the app displays an invite-key screen. The
key is stored in browser local storage and sent as `X-Access-Key` on API,
upload, and authenticated export requests. Production deployments must use
HTTPS because browser storage does not encrypt network traffic.

## UI scope

- project management
- PDF upload
- evidence card browsing
- claim-level audit
- retrieval sandbox
