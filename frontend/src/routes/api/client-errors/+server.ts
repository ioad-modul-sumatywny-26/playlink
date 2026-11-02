import type { RequestHandler } from './$types';
import { logLine } from '$lib/server/log';

const MAX_PER_MINUTE = 20;
const hits = new Map<string, number[]>();

// Keyed by the connection peer, never by a request header a client can forge.
// Behind the tunnel that is the connector, so the cap is shared by all visitors.
function limited(peer: string): boolean {
	const now = Date.now();
	for (const [key, times] of hits) {
		if (now - times[times.length - 1] >= 60_000) hits.delete(key);
	}
	const recent = (hits.get(peer) ?? []).filter((t) => now - t < 60_000);
	recent.push(now);
	hits.set(peer, recent);
	return recent.length > MAX_PER_MINUTE;
}

const clip = (value: unknown, max: number) => String(value ?? '').slice(0, max);

/** Browser-side errors reported by hooks.client.ts; written to the log stream. */
export const POST: RequestHandler = async ({ request, getClientAddress }) => {
	if (limited(getClientAddress())) return new Response(null, { status: 429 });

	const body = await request.json().catch(() => null);
	if (!body || typeof body !== 'object') return new Response(null, { status: 400 });

	logLine('ERROR', 'client_error', {
		event: 'client_error',
		path: clip(body.path, 200),
		error: clip(body.message, 300),
		stack: clip(body.stack, 1500),
		user_agent: clip(request.headers.get('user-agent'), 200)
	});
	return new Response(null, { status: 204 });
};
