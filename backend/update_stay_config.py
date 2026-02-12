import asyncio
import httpx


async def update_stay_config():
    url = "http://172.16.170.35/cgi-bin/configManager.cgi"
    auth = httpx.DigestAuth("admin", "StudioSvetle2024@!")

    print("Setting StayReportInterval=5...")
    params_set = {
        "action": "setConfig",
        "VideoAnalyseRule[0][6].Config.StayReportInterval": "5",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params_set, auth=auth, timeout=10.0)
        print(f"Set Status: {resp.status_code}")
        print(f"Set Body: {resp.text.strip()}")


if __name__ == "__main__":
    asyncio.run(update_stay_config())
