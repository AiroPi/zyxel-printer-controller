import datetime
import os
from typing import Any
import zoneinfo

import httpx2

MONITORING_REF = os.environ["MONITORING_REF"]
LINE_REF = os.environ["LINE_REF"]
API_KEY = os.environ["API_KEY"]

headers = {
    "Accept": "application/json",
    "apikey": API_KEY
}

def get_minutes(train: dict[str, Any]) -> int:
    expected = datetime.datetime.fromisoformat(train["MonitoredVehicleJourney"]["MonitoredCall"]["ExpectedArrivalTime"])
    now = datetime.datetime.now(tz=zoneinfo.ZoneInfo("Europe/Paris"))

    return int((expected - now).total_seconds() / 60)

def get_name(train: dict[str, Any]) -> str:
    return train["MonitoredVehicleJourney"]["JourneyNote"][0]["value"]

async def get_next_trains(direction: str) -> list[tuple[str, int]] | None:
    async with httpx2.AsyncClient(headers=headers) as client:
        req = await client.get("https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring", params={"MonitoringRef": MONITORING_REF, "LineRef": LINE_REF})
        trains = req.json().get("Siri", {}).get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
        if len(trains) > 0:
            trains = trains["MonitoredStopVisit"]
        else:
            return None

        trains = [t for t in trains if t["MonitoredVehicleJourney"]["DirectionRef"]["value"] == direction]
        return sorted([(get_name(t), get_minutes(t)) for t in trains], key=lambda c: c[0])

