# Frontend — SvelteKit

SvelteKit-based frontend for the Playlink project.

## Requirements

- **Bun** (latest)

## Technologies Used

- **Svelte** `^5.51.0` (latest)
- **SvelteKit** `^2.50.2`
- **Bun** (Runtime, Package Manager, Bundler)

## Getting Started

> Use **Bun only** for dependency management and scripts in this project.
> Do not use `npm`, `pnpm`, or `yarn`.

### 1. Installation

Install dependencies:

```bash
cd frontend
bun install
```

### 2. Running the Dev Server

Start the development server:

```bash
bun dev

# or open in browser automatically
bun dev -- --open
```

The app will be available at `http://localhost:5173/`

Before starting the frontend locally, create `frontend/.env` from `frontend/.env.example`.
The public variables used by the app are:

```bash
PUBLIC_BACKEND_URL=http://localhost:8000
PUBLIC_WS_URL=ws://localhost:8000
```

### 3. Building for Production

```bash
bun run build
```

Output is placed under `.svelte-kit/output/`. For deployment, install an
[adapter](https://svelte.dev/docs/kit/adapters) suited to your target platform.

### 4. Previewing the Production Build

```bash
bun run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── lib/             # Shared Svelte components and utilities
│   │   └── index.js     # Public exports
│   ├── routes/          # SvelteKit file-based routing
│   │   ├── +layout.svelte  # Root layout
│   │   └── +page.svelte    # Home page
│   └── app.html         # HTML shell
├── static/              # Static assets served as-is
├── jsconfig.json
├── package.json
├── svelte.config.js     # SvelteKit + Svelte configuration
└── vite.config.js
```

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Svelte extension](https://marketplace.visualstudio.com/items?itemName=svelte.svelte-vscode).

## Notes

- This project uses **Svelte 5 runes** (`$state`, `$derived`, `$props`, etc.)
  and **SvelteKit** for file-based routing, SSR, and adapter-based deployment.
- To deploy, replace `@sveltejs/adapter-auto` with a platform-specific adapter
  (e.g. `adapter-node`, `adapter-vercel`, `adapter-netlify`).
