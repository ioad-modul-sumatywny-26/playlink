<script>
	import "../lib/global.css";

	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav>
	<a href="/">HOME</a>
	<a href="/about">ABOUT</a>
	<a href="/test">TEST</a>
</nav>

{@render children()}

<style>
	nav {
		font-size: 2rem;

		display: flex;
		gap: 1rem;

		justify-content: center;
		align-items: center;
	}
</style>