import type { RequestHandler } from './$types';
import { logLine } from '$lib/server/log';

const MAX_PER_MINUTE = 20;
const hits = new Map<string, number[]>();

function limited(ip: string): boolean {
	const now = Date.now();
	const recent = (hits.get(ip) ?? []).filter((t) => now - t < 60_000);
	recent.push(now);
	hits.set(ip, recent);
	if (hits.size > 5000) hits.clear();
	return recent.length > MAX_PER_MINUTE;
}

const clip = (value: unknown, max: number) => String(value ?? '').slice(0, max);

/** Browser-side errors reported by hooks.client.ts; written to the log stream. */
export const POST: RequestHandler = async ({ request, getClientAddress }) => {
	const ip = request.headers.get('cf-connecting-ip') ?? getClientAddress();
	if (limited(ip)) return new Response(null, { status: 429 });

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
