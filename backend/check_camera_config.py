import asyncio
import httpx


async def check_config():
    url = "http://172.16.170.35/cgi-bin/configManager.cgi"
    auth = httpx.DigestAuth("admin", "StudioSvetle2024@!")

    params = {
        "action": "getConfig",
        "name": "VideoAnalyseRule[0][6].Config.ReportInterval",
    }

    async with httpx.AsyncClient() as client:
        print("Checking ReportInterval...")
        resp = await client.get(url, params=params, auth=auth, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text.strip()}")


if __name__ == "__main__":
    asyncio.run(check_config())
