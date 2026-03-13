<script>
    import '../lib/global.css'

    let {children} = $props();
</script>

<header class="site-header">
    <nav>
        <a href="/">BROWSE</a>
        <a href="/about">ABOUT</a>
    </nav>
</header>

<main>
    {@render children?.()}
</main>

<footer>
    <p>

    </p>
</footer>

<style>
    .site-header {
        width: 100%;
        box-sizing: border-box;

        font-size: 2em;
        padding: 1em;
        text-align: center;
    }
</style>