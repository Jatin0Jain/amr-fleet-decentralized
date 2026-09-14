import asyncio
import json
import websockets

async def test_demo():
    async with websockets.connect('ws://localhost:8080') as ws:
        # Wait a tick
        await asyncio.sleep(0.5)
        # Trigger demo
        await ws.send(json.dumps({'action': 'trigger_demo'}))
        await asyncio.sleep(0.5)
        # Check messages
        for i in range(20):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                if data.get('type') == 'demo_step':
                    print(f'Step: {data.get("step")}/{data.get("total")} - {data.get("name")}')
                elif data.get('type') == 'demo_end':
                    print('Demo ended')
                    break
            except asyncio.TimeoutError:
                break

asyncio.run(test_demo())