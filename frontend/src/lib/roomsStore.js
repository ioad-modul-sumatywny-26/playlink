import { writable } from "svelte/store";
import { browser } from "$app/environment";

function createRoomsStore() {
  const { subscribe, set } = writable([]);

  let reconnectTimeout = null;
  let ws = null;

  function connect() {
    ws = new WebSocket("ws://localhost:8000/ws/rooms"); // path tymczasowy, jak cos to sie zmieni

    ws.onopen = () => {
      console.log("WebSocket connected");
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error("Failed to parse rooms WebSocket message", error, event.data);
        return;
      }

      if (!Array.isArray(data)) {
        console.error("Unexpected rooms WebSocket payload, expected an array", data);
        return;
      }

      set(data);
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
