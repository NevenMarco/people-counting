import asyncio
import httpx


async def update_config():
    url = "http://172.16.170.35/cgi-bin/configManager.cgi"
    auth = httpx.DigestAuth("admin", "StudioSvetle2024@!")

    # 1. Verify it is indeed PC-1
    params_get = {"action": "getConfig", "name": "VideoAnalyseRule[0][6].Name"}

    async with httpx.AsyncClient() as client:
        print("Verifying Rule Name...")
        resp = await client.get(url, params=params_get, auth=auth, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text.strip()}")

        if "PC-1" not in resp.text:
            print("ABORTING: Index 6 is not PC-1")
            return

        # 2. Set ReportInterval=5
        # The user's dump showed: table.VideoAnalyseRule[0][6].Config.ReportInterval=0

        print("Setting ReportInterval=5...")
        params_set = {
            "action": "setConfig",
            "VideoAnalyseRule[0][6].Config.ReportInterval": "5",
            # Also StayReportInterval maybe?
            "VideoAnalyseRule[0][6].Config.StayReportInterval": "5",
        }

        # httpx doesn't support passing complex query params with same key easily if iterating?
        # configManager expects key=value in body or query?
        # Usually query.

        # Let's construct query string manually or pass dict
        resp = await client.get(url, params=params_set, auth=auth, timeout=10.0)
        print(f"Set Status: {resp.status_code}")
        print(f"Set Body: {resp.text.strip()}")


if __name__ == "__main__":
    asyncio.run(update_config())
