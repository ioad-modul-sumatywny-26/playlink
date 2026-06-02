import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ cookies }) => {
	return {
		isAuthenticated: !!cookies.get('session')
	};
};
