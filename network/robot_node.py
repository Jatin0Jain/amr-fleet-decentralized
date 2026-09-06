"""
robot_node.py — P2P WebSocket Network Node
[P2P PERSON] — Each robot runs one of these.

Each robot node:
  - Runs a WebSocket SERVER on its own port (R1→8001, R2→8002, R3→8003)
  - Connects as a CLIENT to all peer ports
  - Broadcasts JSON state every 200ms to all connected peers
  - Calls on_message(sender_id, data) when a message arrives

Usage:
    node = RobotNode(robot_id="R1", port=8001, peers=["ws://localhost:8002", "ws://localhost:8003"])
    asyncio.run(node.run(on_message_callback))
"""

import asyncio
import json
import time
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Callable, Optional

# Reconnect delay when a peer goes offline
RECONNECT_DELAY = 2.0
# How often to broadcast state (seconds)
BROADCAST_INTERVAL = 0.2


class RobotNode:
    """
    P2P WebSocket node for one robot.

    Maintains connections to all peer robots and the dashboard.
    """

    def __init__(self, robot_id: str, port: int, peer_urls: list[str],
                 dashboard_url: str = "ws://localhost:8080"):
        """
        Args:
            robot_id:      e.g. "R1"
            port:          this robot's server port (R1=8001, R2=8002, R3=8003)
            peer_urls:     list of other robots' WebSocket URLs
                           e.g. ["ws://localhost:8002", "ws://localhost:8003"]
            dashboard_url: where to forward state for the dashboard
        """
        self.robot_id = robot_id
        self.port = port
        self.peer_urls = peer_urls
        self.dashboard_url = dashboard_url

        # Active peer connections {url: websocket}
        self._peer_connections: dict[str, Optional[websockets.WebSocketClientProtocol]] = {
            url: None for url in peer_urls
        }
        self._dashboard_conn: Optional[websockets.WebSocketClientProtocol] = None

        # Latest state JSON to broadcast (set externally by sim_runner)
        self._current_state_json: str = ""

        # Callback for incoming messages
        self._on_message: Optional[Callable[[str, dict], None]] = None

        # Peers' latest known states {robot_id: dict}
        self.peer_states: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state_json: str) -> None:
        """Update the JSON state that will be broadcast to peers. Called every tick."""
        self._current_state_json = state_json

    def get_peer_states(self) -> dict[str, dict]:
        """Return the last received state from each peer robot."""
        return dict(self.peer_states)

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self, on_message: Callable[[str, dict], None]) -> None:
        """
        Start the node: launch server + connect to peers + broadcast loop.

        TODO [P2P PERSON]: Implement using asyncio.gather() to run all tasks concurrently.

        Tasks to run concurrently:
            1. self._serve()            — WebSocket server (receives messages)
            2. self._connect_to_peers() — maintain peer connections
            3. self._broadcast_loop()   — send state every 200ms
            4. self._connect_dashboard()— forward to dashboard
        """
        self._on_message = on_message
        # TODO: implement with asyncio.gather(...)
        raise NotImplementedError("P2P person: implement run() with asyncio.gather")

    # ------------------------------------------------------------------
    # Server — receives messages from peers
    # ------------------------------------------------------------------

    async def _serve(self) -> None:
        """
        Start WebSocket server. Peers connect here to send us their state.

        TODO [P2P PERSON]: Use websockets.serve() to listen on self.port.
        On each incoming message:
            data = json.loads(message)
            peer_id = data["robot_id"]
            self.peer_states[peer_id] = data
            if self._on_message:
                self._on_message(peer_id, data)
        """
        raise NotImplementedError("P2P person: implement _serve()")

    # ------------------------------------------------------------------
    # Client — connects to peers and sends our state
    # ------------------------------------------------------------------

    async def _connect_to_peers(self) -> None:
        """
        Connect to all peer robots and maintain those connections.
        Reconnects automatically if a peer goes offline.

        TODO [P2P PERSON]: For each url in self.peer_urls:
            - Try to connect with websockets.connect(url)
            - Store in self._peer_connections[url]
            - If connection drops → wait RECONNECT_DELAY, retry
        """
        raise NotImplementedError("P2P person: implement _connect_to_peers()")

    async def _broadcast_loop(self) -> None:
        """
        Send self._current_state_json to all connected peers every BROADCAST_INTERVAL.

        TODO [P2P PERSON]: Loop every 200ms.
        For each connection in self._peer_connections.values():
            if connection is not None:
                try: await connection.send(self._current_state_json)
                except: pass  # peer offline, will reconnect
        """
        raise NotImplementedError("P2P person: implement _broadcast_loop()")

    # ------------------------------------------------------------------
    # Dashboard forwarding
    # ------------------------------------------------------------------

    async def _connect_dashboard(self) -> None:
        """
        Connect to dashboard WebSocket and forward state every tick.

        TODO [P2P PERSON]: Connect to self.dashboard_url.
        Every BROADCAST_INTERVAL: await conn.send(self._current_state_json)
        Handle disconnects gracefully (dashboard might not be open yet).
        """
        raise NotImplementedError("P2P person: implement _connect_dashboard()")

    async def disconnect(self) -> None:
        """Gracefully close all connections."""
        for url, conn in self._peer_connections.items():
            if conn:
                await conn.close()
        if self._dashboard_conn:
            await self._dashboard_conn.close()
