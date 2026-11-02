import type { HandleClientError } from '@sveltejs/kit';
import { reportClientError } from '$lib/clientErrors';

window.addEventListener('error', (event) => reportClientError(event.error ?? event.message));
window.addEventListener('unhandledrejection', (event) => reportClientError(event.reason));

export const handleError: HandleClientError = ({ error }) => {
	reportClientError(error);
	return { message: 'Something went wrong' };
};
