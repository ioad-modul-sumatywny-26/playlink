<script>
	import { onMount } from 'svelte';
	import { PUBLIC_BACKEND_URL } from '$env/static/public';

	let data = $state(null);
	let error = $state(null);
	let loading = $state(true);

	onMount(async () => {
		try {
			// Using the direct address as it's client-side fetch from the browser
			const response = await fetch(`${PUBLIC_BACKEND_URL}/`);
			if (!response.ok) {
				throw new Error(`Error: ${response.status}`);
			}
			data = await response.json();
		} catch (e) {
			error = e.message;
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
