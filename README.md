# Bill-Dash

Invoice management dashboard built with Django.

## Running with Docker (Windows)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) to be installed and running.

### 1. Start the app

```
docker-run.cmd
```

This builds the images and starts three containers — Postgres, Django (gunicorn) and nginx. On first start it also applies database migrations and collects static files, so it takes a minute or two.

The app is then available at **http://localhost:8080**

### 2. Create the admin user

Run this once, after the app is up:

```
docker-createuser.cmd
```

Default credentials are `KavinText` / `Admin@123` — edit the values at the top of `docker-createuser.cmd` to change them.

### 3. Log in

Open http://localhost:8080 and sign in with the user created above.

## Other commands

| Command | What it does |
| --- | --- |
| `docker-run.cmd` | Build and start everything in the background |
| `docker-logs.cmd` | Follow logs for all services |
| `docker-logs.cmd web` | Follow Django logs only (`nginx` and `db` also work) |
| `docker-remove.cmd` | Stop and remove containers, **keeping** the database |
| `docker-remove.cmd --all` | Also delete the database volume (permanent data loss) |

Re-run `docker-run.cmd` after changing Python code, templates or CSS — the image copies the code in, so a rebuild is needed for changes to appear.

## Configuration

Copy `.env.example` to `.env` to override defaults.

By default the app uses the bundled Postgres container. If `DATABASE_URL` is set in `.env` (for example pointing at Supabase), that is used instead and the local `db` container goes unused.

All ports are bound to `127.0.0.1`, so the app is reachable only from this machine and not from others on the network.

## Notes

- `docker/entrypoint.sh` runs *inside* the Linux container, not on Windows — it must stay a shell script.
- Static files are served by nginx from a shared volume and are re-collected on every container start.
