import type { LayoutServerLoad } from './$types';
import { CURRENT_REGION, REGIONS, isEntryHost } from '$lib/regions';

export const load: LayoutServerLoad = async ({ cookies, url }) => {
	return {
		isAuthenticated: !!cookies.get('session'),
		isEntryHost: isEntryHost(url.host),
		region: CURRENT_REGION,
		regions: REGIONS
	};
};
