import type { RequestHandler } from './$types';

export const GET: RequestHandler = () =>
	new Response(JSON.stringify({ status: 'ok' }), {
		headers: {
			'content-type': 'application/json',
			'cache-control': 'no-store'
		}
	});
