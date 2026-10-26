# Krinea product video

The 42-second product tour shown on krinea.org, written as a [HyperFrames](https://github.com/heygen-com/hyperframes) composition: plain HTML and CSS, one seekable GSAP timeline, rendered to MP4 by Chrome and FFmpeg. Everything on screen is either a real screenshot of the application (`assets/screens`, taken on a sample review of fictitious records) or a native element built with the site's design tokens.

## Files

- `index.html`: the composition (six scenes, 1920x1080, 42 s). The `lang` variable selects the captions: `fr` (default) or `en`.
- `variants/square.html`: the same six scenes cut for social feeds (1080x1080), rendered with `npm run render -- -c variants/square.html ...`.
- `assets/screens`: screenshots copied from `apps/web/public/screens`.
- `assets/fonts`: Inter (variable weight), the site's typeface.
- `assets/brand`: the Krinea mark and wordmark.
- `renders/` and `.hyperframes/`: generated, not committed. The published files live in `apps/web/public/video`.

## Commands

Node 22 and FFmpeg are required. The CLI version is pinned in `package.json`.

```bash
npm run check                                  # lint, runtime, layout, motion and contrast checks
npx hyperframes snapshot --at 1.6,9,14.5,24,34 # still frames for a quick look
npm run dev                                    # live preview in the browser
npm run render -- --quality delivery --variables '{"lang":"fr"}' --output renders/krinea-tour-fr.mp4
npm run render -- --quality delivery --variables '{"lang":"en"}' --output renders/krinea-tour-en.mp4
```

After rendering, compress for the web and copy to the site:

```bash
ffmpeg -i renders/krinea-tour-fr.mp4 -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -movflags +faststart -an ../web/public/video/krinea-tour-fr.mp4
```

## Editing

Scene timings are the `S` constants at the top of the timeline script; clip windows are the `data-start` and `data-duration` attributes on each `<section>`. Captions live in the `COPY` table (French first, English second). Keep the house rules of the site: no em-dashes, no emoji, honest claims only.
