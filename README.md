# Molecule Explorer deployment

The website is static, but molecular analysis runs in a Python API. GitHub Pages
can host `index.html`; it cannot run `app.py`. Deploy the API to Render and point
the page to that service.

## 1. Deploy the API to Render

Create a **Web Service** from the GitHub repository containing this project.
If the project is in a subfolder, set Render's **Root Directory** to that folder
(for example, `Projects/Chem Assignment`).

Use these settings:

- **Runtime:** Python
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app`

Add this environment variable in the Render service settings:

- **Key:** `CORS_ORIGINS`
- **Value:** `https://YOUR-GITHUB-USERNAME.github.io`

Replace the value with the exact origin of your Pages site. For a custom domain,
include its origin too, comma-separated, for example:
`https://YOUR-GITHUB-USERNAME.github.io,https://chem.example.com`.
Do not include a repository path or trailing slash in an origin.

After deployment, verify the service is healthy at
`https://YOUR-RENDER-SERVICE.onrender.com/api/health`. It should return
`{"status":"ok"}`.

## 2. Point GitHub Pages at the API

In `index.html`, find `YOUR-RENDER-SERVICE` and replace it with the Render
service's hostname. For example:

```js
? "https://molecule-explorer-api.onrender.com"
```

Keep the `https://` scheme and do not add `/api` at the end. Commit and push this
change.

## 3. Publish the website with GitHub Pages

In the GitHub repository, open **Settings → Pages** and select the branch/folder
containing `index.html` as the publishing source. The page and `index.html` must
be in the selected publishing folder. If this project is in a subfolder of a
larger repository, either publish the repository root and open the project's
subfolder URL, or move/copy the site files into the repository root or `docs`
folder.

Wait for the Pages deployment to finish, then open the published site and test
with one of the example molecules.

## Local development

Install dependencies with `pip install -r requirements.txt`, then run
`python app.py` and open `http://127.0.0.1:5000`. The API base is left relative
on localhost, so no deployment URL is needed for local testing.
