# Deployment checklist

Run this from the backend directory after applying migrations and before routing traffic:

```sh
python manage.py launch_check --production
```

Deployment must stop if this command exits nonzero. It uses the same `run_launch_checks` function as the reviewer launch gate, so the content and production settings criteria match. Set `LAUNCH_MIN_FLOWS` to the required minimum before running it; the default is 3.
