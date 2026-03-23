import asyncio
import json

import httpx


async def main():
    async with httpx.AsyncClient(timeout=None) as client:
        print("Creating session...")
        res = await client.post("http://127.0.0.1:7420/api/sessions", json={})
        res.raise_for_status()
        session_id = res.json()["id"]
        print(f"Session: {session_id}")

        print("Sending message...")
        try:
            async with client.stream(
                "POST",
                f"http://127.0.0.1:7420/api/sessions/{session_id}/messages",
                json={"content": "hello"},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    print(line)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
