<script lang="ts">
	import { roomsStore } from '$lib/roomsStore';
</script>

{#each $roomsStore as room (room.name)}
	<div>
		{room.name} ({room.players_active}/{room.players_max})
	</div>
{/each}
