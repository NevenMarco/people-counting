import asyncio
import httpx


async def probe():
    url = "http://172.16.170.35/cgi-bin/videoStatServer.cgi"
    auth = httpx.DigestAuth("admin", "StudioSvetle2024@!")

    # Try different combinations
    queries = [
        {"action": "getSummary", "channel": "1"},
        {"action": "getSummary", "channel": "1", "ruleType": "ManNumDetection"},
        {"action": "getSummary", "channel": "1", "ruleId": "7"},
        {"action": "getSummary", "channel": "1", "name": "PC-1"},
    ]

    async with httpx.AsyncClient() as client:
        for params in queries:
            print(f"\n--- Testing params: {params} ---")
            try:
                resp = await client.get(url, params=params, auth=auth, timeout=5.0)
                print(f"Status: {resp.status_code}")
                print(f"Body: {resp.text[:500]}...")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(probe())
