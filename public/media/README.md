# media/

Drop Weronika's photos, videos, and audio here.

Everything in `public/` is served from the site root, so a file placed at
`public/media/intro.mp4` is reachable at `/media/intro.mp4` and can be used in
`weronika.html` like:

```html
<img src="/media/portrait.jpg" alt="Weronika" /> <video src="/media/intro.mp4" controls></video>
```

Guidelines:

- Keep individual files under ~50 MB — this folder ships with the repo.
- Use lowercase, hyphenated names (`intro-loop.mp4`, not `Intro Loop FINAL.mp4`).
- Prefer `.webp` for stills and `.mp4` (H.264) for video so every browser plays them.
