import asyncio
import httpx


async def probe_stream():
    url = "http://172.16.170.35/cgi-bin/videoStatServer.cgi"
    params = {"action": "attach", "channel": "1", "heartbeat": "5"}
    auth = httpx.DigestAuth("admin", "StudioSvetle2024@!")

    print(f"Connecting to {url}...")
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url, params=params, auth=auth) as resp:
            print(f"Status: {resp.status_code}")
            async for line in resp.aiter_lines():
                if line.strip():
                    print(line)
                # Stop after some output or time?
                # For now just let it run and I'll kill it or let it timeout if I added one.
                # But since I'm running via tool, I rely on tool timeout or manual check.


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(probe_stream(), timeout=15))
    except asyncio.TimeoutError:
        print("Timeout reached.")
