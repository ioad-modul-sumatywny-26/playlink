<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import type { RegionConfig, RegionId } from '$lib/regions';
	import { isMeaningfullyFaster, probeAll, saveRegion } from '$lib/regions';
	import OrnateButton from '$lib/components/chrome/OrnateButton.svelte';

	let {
		currentRegion,
		other
	}: {
		currentRegion: RegionId;
		other: RegionConfig | undefined;
	} = $props();

	const DISMISS_KEY = 'playlink.regionProposalDismissed';

	let visible = $state(false);
	let otherMs = $state<number | null>(null);
	let currentMs = $state<number | null>(null);

	function dismissed(): boolean {
		try {
			return sessionStorage.getItem(DISMISS_KEY) === currentRegion;
		} catch {
			return false;
		}
	}

	function dismiss() {
		try {
			sessionStorage.setItem(DISMISS_KEY, currentRegion);
		} catch {
			/* ignore */
		}
		visible = false;
	}

	onMount(() => {
		if (!other?.api || dismissed()) return;

		let cancelled = false;
		void (async () => {
			const results = await probeAll();
			if (cancelled) return;
			const here = results.find((result) => result.region.id === currentRegion);
			const there = results.find((result) => result.region.id === other.id);
			if (!here?.ok || !there?.ok) return;
			if (!isMeaningfullyFaster(there.ms, here.ms)) return;
			currentMs = here.ms;
			otherMs = there.ms;
			visible = true;
		})();

		return () => {
			cancelled = true;
		};
	});
</script>

{#if visible && other}
	<div class="banner" role="status">
		<span class="text">
			{other.label} looks faster ({Math.round(otherMs ?? 0)} ms vs {Math.round(currentMs ?? 0)} ms). Saved
			region stays put unless you switch.
		</span>
		<div class="actions">
			<OrnateButton variant="secondary" size="sm" onclick={dismiss}>Keep current</OrnateButton>
			<a
				class="switch-link"
				href={`${other.frontend}${page.url.pathname}${page.url.search}`}
				onclick={() => {
					saveRegion(other.id);
				}}
			>
				Switch to {other.label}
			</a>
		</div>
	</div>
{/if}

<style>
	.banner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin: 0 8px 10px;
		padding: 0.55rem 0.8rem;
		border: 1px solid var(--stone-5);
		background: var(--stone-1);
		box-shadow: var(--bevel-in);
	}

	.text {
		font-family: var(--font-mono);
		font-size: 0.72rem;
		color: var(--bone);
		line-height: 1.4;
		flex: 1 1 220px;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.55rem;
	}

	.switch-link {
		font-family: var(--font-display);
		font-size: 0.65rem;
		letter-spacing: var(--track-loose);
		color: var(--gold-muted);
		text-decoration: none;
		border-bottom: 1px dashed var(--gold-muted);
		text-transform: uppercase;
	}

	.switch-link:hover {
		color: var(--gold-lit);
		border-bottom-color: var(--gold-lit);
	}
</style>
