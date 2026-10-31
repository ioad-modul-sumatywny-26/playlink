<script lang="ts">
	import '../lib/global.css';

	import favicon from '$lib/assets/favicon.svg';
	import PageFrame from '$lib/components/chrome/PageFrame.svelte';
	import Tabs from '$lib/components/chrome/Tabs.svelte';
	import Tab from '$lib/components/chrome/Tab.svelte';
	import HintBar from '$lib/components/chrome/HintBar.svelte';
	import Hint from '$lib/components/chrome/Hint.svelte';
	import RegionChooser from '$lib/components/RegionChooser.svelte';
	import { page } from '$app/state';
	import { otherRegion } from '$lib/regions';
	import { provideHints } from '$lib/hintsContext.svelte';

	let { children, data } = $props();

	const other = $derived(data?.region ? otherRegion(data.region) : undefined);

	const hints = provideHints([
		{ key: 'Esc', label: 'Back', tone: 'red' },
		{ key: '?', label: 'Help', tone: 'stone' }
	]);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	{#if data?.isEntryHost}
		<title>PlayLink — Choose region</title>
	{/if}
</svelte:head>

{#if data?.isEntryHost}
	<PageFrame>
		<div class="brand-bar anim-frame-in">
			<a href="/" class="brand">
				<span class="brand-mark" aria-hidden="true">◆</span>
				<span class="brand-name">PLAYLINK</span>
				<span class="brand-mark" aria-hidden="true">◆</span>
			</a>
		</div>

		<main class="page-main anim-content-in">
			<RegionChooser regions={data.regions} />
		</main>
	</PageFrame>
{:else}
	<PageFrame>
		<div class="brand-bar anim-frame-in">
			<a href="/" class="brand">
				<span class="brand-mark" aria-hidden="true">◆</span>
				<span class="brand-name">PLAYLINK</span>
				<span class="brand-mark" aria-hidden="true">◆</span>
			</a>
			<span class="region-badge" title="Active API region">
				{data?.region?.toUpperCase() ?? '—'}
			</span>
			{#if other?.frontend}
				<a
					class="region-switch"
					href={`${other.frontend}${page.url.pathname}${page.url.search}`}
					title="Switch region — separate session, sign in with the same 12 words"
				>
					→ {other.label}
				</a>
			{/if}
		</div>

		<Tabs>
			<Tab href="/auth">Identity</Tab>
			<Tab href="/rooms">Rooms</Tab>
			{#if data?.isAuthenticated}
				<Tab href="/profile">Profile</Tab>
			{/if}
			<Tab href="/about">About</Tab>
		</Tabs>

		<main class="page-main anim-content-in">
			{@render children()}
		</main>

		<HintBar>
			{#if hints.hints.length === 0}
				<Hint key="Esc" label="Back" tone="red" />
			{:else}
				{#each hints.hints as h (h.key + h.label)}
					<Hint key={h.key} label={h.label} tone={h.tone} onclick={h.onclick} />
				{/each}
			{/if}
		</HintBar>
	</PageFrame>
{/if}

<style>
	.brand-bar {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		padding: 8px 0 18px;
	}

	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.9rem;
		font-family: var(--font-display);
		font-size: 1.4rem;
		letter-spacing: var(--track-extra);
		color: var(--bone-bright);
		text-decoration: none;
		text-shadow: 0 1px 0 rgba(0, 0, 0, 0.75);
	}

	.brand-mark {
		color: var(--gold-base);
		font-size: 0.7em;
		text-shadow: 0 1px 0 rgba(0, 0, 0, 0.75);
	}

	.brand:hover {
		color: var(--gold-lit);
	}

	.region-badge {
		font-family: var(--font-mono);
		font-size: 0.65rem;
		letter-spacing: var(--track-extra);
		color: var(--gold-muted);
		border: 1px solid var(--stone-5);
		padding: 2px 7px;
		background: var(--stone-1);
	}

	.region-switch {
		font-family: var(--font-display);
		font-size: 0.65rem;
		letter-spacing: var(--track-loose);
		color: var(--bone-muted);
		text-decoration: none;
		border-bottom: 1px dashed var(--stone-5);
		text-transform: uppercase;
	}

	.region-switch:hover {
		color: var(--gold-lit);
		border-bottom-color: var(--gold-muted);
	}

	.page-main {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
		padding: 0 8px;
	}
</style>
