from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import mongo_lite
from controllers import sms_manager

router = APIRouter(tags=["sim"])


def _serialize_sim(sim: dict) -> dict:
    sim = dict(sim)
    sim_id = sim.get("_id")
    if sim_id is not None:
        sim["_id"] = str(sim_id)
    return sim


@router.get("/sims")
def list_sims(
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    com_port: Optional[str] = None,
) -> dict:
    query = {}
    if com_port:
        query["com_port"] = com_port
    cursor = mongo_lite.sim_collection.find(query).skip(skip).limit(limit)
    items = [_serialize_sim(sim) for sim in cursor]
    return {"items": items, "count": len(items)}


@router.get("/sims/{iccid}")
def get_sim(iccid: str) -> dict:
    sim = mongo_lite.sim_collection.find_one({"iccid": iccid})
    if not sim:
        raise HTTPException(status_code=404, detail="Sim not found")
    return _serialize_sim(sim)

@router.get("/sims/sms/{iccid}")
def get_sms(iccid: str) -> dict:
    sms = sms_manager.SMSManager().get_sms_all(iccid)
    if sms is None:
        raise HTTPException(status_code=404, detail="SMS not found")
    return {"sms": sms}