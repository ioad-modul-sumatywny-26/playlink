import { dev } from '$app/environment';
import { env } from '$env/dynamic/public';

export type RegionId = 'eu' | 'us';

export interface RegionConfig {
	id: RegionId;
	label: string;
	/** Public frontend origin for this region, e.g. https://eu.playlink.example */
	frontend: string;
	/** Public API origin for this region, e.g. https://api-eu.playlink.example */
	api: string;
	/** Public WebSocket origin for this region, e.g. wss://api-eu.playlink.example */
	ws: string;
	healthPath: string;
}

export interface ProbeResult {
	region: RegionConfig;
	ok: boolean;
	ms: number | null;
}

function clean(value: string | undefined): string | null {
	const trimmed = value?.trim();
	return trimmed ? trimmed.replace(/\/$/, '') : null;
}

function localFallback(value: string | null, fallback: string): string {
	if (value) return value;
	return dev ? fallback : '';
}

const EU_FRONTEND = clean(env.PUBLIC_REGION_EU_FRONTEND);
const EU_API = clean(env.PUBLIC_REGION_EU_API);
const EU_WS = clean(env.PUBLIC_REGION_EU_WS);
const US_FRONTEND = clean(env.PUBLIC_REGION_US_FRONTEND);
const US_API = clean(env.PUBLIC_REGION_US_API);
const US_WS = clean(env.PUBLIC_REGION_US_WS);

export const REGIONS: RegionConfig[] = [
	{
		id: 'eu',
		label: 'Europa',
		frontend: localFallback(EU_FRONTEND, 'http://localhost:3000'),
		api: localFallback(EU_API, 'http://localhost:8000'),
		ws: localFallback(EU_WS, 'ws://localhost:8000'),
		healthPath: '/healthz'
	},
	{
		id: 'us',
		label: 'USA',
		frontend: localFallback(US_FRONTEND, 'http://localhost:3001'),
		api: localFallback(US_API, 'http://localhost:8001'),
		ws: localFallback(US_WS, 'ws://localhost:8001'),
		healthPath: '/healthz'
	}
];

/** Hostname (optionally with port) that serves the region chooser, if any. */
export const ENTRY_HOST = clean(env.PUBLIC_ENTRY_HOST);

/** Region served by this frontend instance. */
export const CURRENT_REGION: RegionId = env.PUBLIC_REGION === 'us' ? 'us' : 'eu';

export function isEntryHost(host: string): boolean {
	return host === ENTRY_HOST;
}

export function otherRegion(id: RegionId): RegionConfig | undefined {
	return REGIONS.find((region) => region.id !== id);
}

/** Probe one region twice; return the best successful round-trip. */
export async function probeRegion(region: RegionConfig, samples = 2): Promise<ProbeResult> {
	if (!region.api) {
		return { region, ok: false, ms: null };
	}

	let best: number | null = null;
	for (let attempt = 0; attempt < samples; attempt += 1) {
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), 2500);
		const started = performance.now();
		try {
			const response = await fetch(`${region.api}${region.healthPath}`, {
				cache: 'no-store',
				signal: controller.signal,
				headers: { Accept: 'application/json' }
			});
			if (!response.ok) continue;
			const elapsed = performance.now() - started;
			best = best === null ? elapsed : Math.min(best, elapsed);
		} catch {
			// A timeout or network failure means "not a candidate".
		} finally {
			clearTimeout(timer);
		}
	}

	return { region, ok: best !== null, ms: best };
}

export async function probeAll(regions: RegionConfig[] = REGIONS): Promise<ProbeResult[]> {
	return Promise.all(regions.map((region) => probeRegion(region)));
}

const REGION_COOKIE = 'playlink.region';

export function readSavedRegion(): RegionId | null {
	if (typeof document === 'undefined') return null;
	const match = document.cookie
		.split(';')
		.map((part) => part.trim())
		.find((part) => part.startsWith(`${REGION_COOKIE}=`));
	if (!match) return null;
	const value = match.slice(REGION_COOKIE.length + 1);
	return value === 'eu' || value === 'us' ? value : null;
}

export function saveRegion(id: RegionId): void {
	if (typeof document === 'undefined') return;
	const secure = window.location.protocol === 'https:' ? '; Secure' : '';
	document.cookie = `${REGION_COOKIE}=${id}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

/**
 * Navigate to a region's frontend, preserving the current path and query.
 * Returns false when the target is the current host (avoids redirect loops).
 */
export function redirectToRegion(id: RegionId, regions: RegionConfig[] = REGIONS): boolean {
	if (typeof window === 'undefined') return false;
	const region = regions.find((candidate) => candidate.id === id);
	if (!region?.frontend) return false;

	try {
		const target = new URL(region.frontend);
		const current = new URL(window.location.href);
		if (target.host === current.host) return false;

		// Pin the origin: resolving a path like `//evil.example` would change the host.
		const destination = new URL(target);
		destination.pathname = window.location.pathname.replace(/^\/+/, '/');
		destination.search = window.location.search;
		window.location.replace(destination.toString());
		return true;
	} catch {
		return false;
	}
}
