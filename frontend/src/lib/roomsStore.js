import { writable } from "svelte/store";
import { browser } from "$app/environment";
import { PUBLIC_WS_URL } from "$env/static/public";

function createRoomsStore() {
  const { subscribe, set } = writable([]);

  let reconnectTimeout = null;
  let ws = null;

  function connect() {
    ws = new WebSocket(`${PUBLIC_WS_URL}/ws/rooms`);

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      set(JSON.parse(event.data));
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected, retrying...");
      reconnect();
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  function reconnect() {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = setTimeout(connect, 1000);
  }

  if (browser) {
    connect();
  }

  return {
    subscribe,
  };
}

export const roomsStore = createRoomsStore();
