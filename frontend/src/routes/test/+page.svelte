<script lang="ts">
	import { onMount } from 'svelte';
	import { env } from '$env/dynamic/public';

	let data = $state<unknown>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	onMount(async () => {
		try {
			const backendUrl = env.PUBLIC_BACKEND_URL;
			if (!backendUrl) {
				throw new Error('Missing PUBLIC_BACKEND_URL');
			}

			const response = await fetch(`${backendUrl}/`);
			if (!response.ok) {
				throw new Error(`Error: ${response.status}`);
			}
			data = await response.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});
</script>

<div class="test-container">
	<h2>TEST BACKEND CONNECTION</h2>

	{#if loading}
		<p>Loading data from backend...</p>
	{:else if error}
		<p class="error">FAILED: {error}</p>
	{:else}
		<div class="result">
			<p>Data from backend:</p>
			<pre>{JSON.stringify(data, null, 2)}</pre>
		</div>
	{/if}
</div>

<style>
	.test-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 2rem;
		text-align: center;
	}

	.result {
		background: rgba(0, 0, 0, 0.5);
		padding: 1.5rem;
		border-radius: 8px;
		margin-top: 1rem;
	}

	.error {
		color: #ff4444;
	}

	pre {
		font-family: monospace;
		font-size: 1.2rem;
	}
</style>
