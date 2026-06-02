<script lang="ts">
	import '../lib/global.css';

	import favicon from '$lib/assets/favicon.svg';
	import PageFrame from '$lib/components/chrome/PageFrame.svelte';
	import Tabs from '$lib/components/chrome/Tabs.svelte';
	import Tab from '$lib/components/chrome/Tab.svelte';
	import HintBar from '$lib/components/chrome/HintBar.svelte';
	import Hint from '$lib/components/chrome/Hint.svelte';
	import { provideHints } from '$lib/hintsContext.svelte';

	let { children, data } = $props();

	const hints = provideHints([
		{ key: 'Esc', label: 'Back', tone: 'red' },
		{ key: '?', label: 'Help', tone: 'stone' }
	]);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<PageFrame>
	<div class="brand-bar anim-frame-in">
		<a href="/" class="brand">
			<span class="brand-mark" aria-hidden="true">◆</span>
			<span class="brand-name">PLAYLINK</span>
			<span class="brand-mark" aria-hidden="true">◆</span>
		</a>
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

<style>
	.brand-bar {
		display: flex;
		justify-content: center;
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

	.page-main {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-height: 0;
		padding: 0 8px;
	}
</style>
