let sent = 0;

/** Report a browser error to the server log (best effort, at most 5 per page load). */
export function reportClientError(error: unknown): void {
	if (sent >= 5 || typeof navigator === 'undefined') return;
	sent += 1;
	const err = error instanceof Error ? error : new Error(String(error));
	const body = JSON.stringify({
		path: window.location.pathname,
		message: err.message,
		stack: err.stack
	});
	navigator.sendBeacon('/api/client-errors', new Blob([body], { type: 'application/json' }));
}
