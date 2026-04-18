<script>
	import '../lib/global.css';

	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav>
	<a href="/auth">IDENTITY</a>
	<a href="/rooms">ROOMS</a>
	<a href="/about">ABOUT</a>
	<a href="/test">TEST</a>
</nav>

{@render children()}

<style>
	:global(body) {
		font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
	}

	nav {
		font-size: 2.5rem;
		display: flex;
		gap: 2rem;
		padding: 1rem;
		justify-content: center;
		align-items: center;
	}

	nav a {
		color: white;
		text-decoration: none;
		font-family: 'Exocet', serif;
		transition: color 0.2s;
	}

	nav a:hover {
		color: #e3bc74;
	}
</style>
