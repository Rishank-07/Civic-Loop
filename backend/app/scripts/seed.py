"""
Seed script for CivicLoop database.
Populates:
1. Demo users (Citizen, BBMP Officer, System Admin)
2. 3 Realistic Bengaluru cases (Ward 150 Bellandur, Ward 112 Domlur, Ward 174 HSR Layout)
3. Immutable complaint records
4. Append-only timeline events with strict origin labels
5. Evidence items
6. Background tasks
7. Grounded knowledge chunks from /knowledge
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from backend.app.core.database import SessionLocal, engine, Base, setup_database_triggers
from backend.app.core.security import get_password_hash
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.models.evidence import Evidence
from backend.app.models.timeline import TimelineEvent
from backend.app.models.task import Task
from backend.app.models.approval import Approval
from backend.app.models.knowledge import KnowledgeChunk
from backend.app.domain.timeline_service import record_event, TimelineOrigin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")


def seed_database():
    logger.info("Initializing tables and triggers...")
    Base.metadata.create_all(bind=engine)
    setup_database_triggers(engine)

    db = SessionLocal()
    try:
        # 1. Users
        existing_user = db.query(User).filter(User.email == "citizen@civicloop.org").first()
        if existing_user:
            logger.info("Database already seeded. Skipping.")
            return

        logger.info("Seeding demo users...")
        citizen = User(
            email="citizen@civicloop.org",
            name="Ramesh Kumar",
            hashed_password=get_password_hash("Password123!"),
            role="CITIZEN",
        )
        officer = User(
            email="officer@bbmp.gov.in",
            name="AEE K. Venkatraman (SWD)",
            hashed_password=get_password_hash("Password123!"),
            role="OFFICER",
        )
        admin = User(
            email="admin@civicloop.org",
            name="CivicLoop Administrator",
            hashed_password=get_password_hash("Password123!"),
            role="ADMIN",
        )
        db.add_all([citizen, officer, admin])
        db.commit()
        db.refresh(citizen)
        db.refresh(officer)
        db.refresh(admin)

        # 2. Case 1: Ward 150 Bellandur (GARBAGE + DRAINAGE)
        logger.info("Seeding Case 1: Ward 150 Bellandur...")
        case1 = Case(
            user_id=citizen.id,
            title="Chronic Commercial Waste Dumping along Green Glen Storm Water Canal",
            issue_category="GARBAGE",
            location_text="Green Glen Layout 4th Cross, near Bellandur Lake Canal Culvert, Ward 150, Bengaluru",
            lat=12.9298,
            lng=77.6744,
            ward="Ward 150 - Bellandur",
            jurisdiction="BBMP Mahadevapura Zone",
            status="MONITORING",
            verification_state="AWAITING_VERIFICATION",
        )
        db.add(case1)
        db.commit()
        db.refresh(case1)

        complaint1 = ComplaintRecord(
            case_id=case1.id,
            source="BBMP Sahaaya 2.0",
            external_id="BBMP-SHY-2026-89412",
            raw_text="Severe blackspot garbage accumulation on storm water drain perimeter along 4th Cross. Auto-tippers dumping residual commercial waste at night. Foul smell and stray dogs blocking footpath.",
            official_status="ASSIGNED",
            official_status_retrieved_at=datetime.now(timezone.utc) - timedelta(hours=6),
            retrieval_method="AUTHORISED_CONNECTOR",
            extracted_json={
                "complaint_type": "Solid Waste Management / Blackspot",
                "assigned_division": "Mahadevapura Sub-Division",
                "nodal_officer": "Junior Health Inspector Ward 150",
            },
            confidence=0.96,
        )
        db.add(complaint1)
        db.commit()
        db.refresh(complaint1)

        evidence1 = Evidence(
            case_id=case1.id,
            file_path="/evidence/ward150_bellandur_garbage_culvert.jpg",
            mime="image/jpeg",
            exif_json={"lat": 12.9298, "lng": 77.6744, "camera": "OnePlus 11"},
            captured_at=datetime.now(timezone.utc) - timedelta(hours=12),
            supplied_by=citizen.id,
            provenance="CITIZEN_MOBILE_UPLOAD",
            ai_description="Overflowing commercial garbage bags and styrofoam packaging spilling over masonry drain parapet wall.",
        )
        db.add(evidence1)
        db.commit()

        record_event(
            db=db,
            case_id=case1.id,
            event_type="CASE_CREATED",
            origin=TimelineOrigin.SYSTEM_EVENT,
            actor="CivicLoop System",
            source="Intake Engine",
            payload={"initial_status": "OPEN", "ward": case1.ward},
        )
        record_event(
            db=db,
            case_id=case1.id,
            event_type="COMPLAINT_RECORDED",
            origin=TimelineOrigin.SOURCE_FACT,
            actor="BBMP Sahaaya Connector",
            source="BBMP Sahaaya 2.0 API",
            payload={"ticket_id": "BBMP-SHY-2026-89412", "official_status": "ASSIGNED"},
        )
        record_event(
            db=db,
            case_id=case1.id,
            event_type="AI_RECOMMENDATION_POSTED",
            origin=TimelineOrigin.AI_RECOMMENDATION,
            actor="CivicLoop Agent (DeepSeek V4)",
            source="Agent Reasoning Engine",
            payload={
                "grounded_sop": "BBMP SWM Bye-laws 2020 Clause 4",
                "recommendation": "SLA for commercial blackspot clearance is 48 hours. Schedule automated status sync check for 2026-10-10 10:00 IST.",
            },
        )

        # 3. Case 2: Ward 112 Domlur (DRAINAGE - RESOLUTION DISPUTED)
        logger.info("Seeding Case 2: Ward 112 Domlur...")
        case2 = Case(
            user_id=citizen.id,
            title="Blocked Intermediate Ring Road Storm Water Drain Culvert Choking Challaghatta Runoff",
            issue_category="DRAINAGE",
            location_text="Domlur 100 Feet Road, Intermediate Ring Road Junction underpass culvert, Ward 112, Bengaluru",
            lat=12.9609,
            lng=77.6387,
            ward="Ward 112 - Domlur",
            jurisdiction="BBMP East Zone (SWD Division)",
            status="MONITORING",
            verification_state="RESOLUTION_DISPUTED",
        )
        db.add(case2)
        db.commit()
        db.refresh(case2)

        complaint2 = ComplaintRecord(
            case_id=case2.id,
            source="Namma Bengaluru Grievance",
            external_id="NBG-SWD-2026-43109",
            raw_text="Primary storm water drain (Raja Kaluve feeder) completely choked with silt and plastic debris. Portal marked closed by ward engineer claiming desilting completed.",
            official_status="CLOSED",
            official_status_retrieved_at=datetime.now(timezone.utc) - timedelta(hours=3),
            retrieval_method="AUTHORISED_CONNECTOR",
            extracted_json={
                "complaint_type": "Storm Water Drain Desilting",
                "contractor_id": "BLR-SWD-2026-C8",
                "official_remarks": "Excavator desilting work completed on 2026-10-08.",
            },
            confidence=0.99,
        )
        db.add(complaint2)
        db.commit()

        evidence2 = Evidence(
            case_id=case2.id,
            file_path="/evidence/ward112_domlur_swd_choked_silt.jpg",
            mime="image/jpeg",
            exif_json={"lat": 12.9609, "lng": 77.6387, "camera": "Samsung S24"},
            captured_at=datetime.now(timezone.utc) - timedelta(hours=2),
            supplied_by=citizen.id,
            provenance="CITIZEN_VERIFICATION_AUDIT",
            ai_description="Ground inspection reveals 80% culvert cross-section blocked by excavated silt left on curb, contrary to official closure claim.",
        )
        db.add(evidence2)
        db.commit()

        record_event(
            db=db,
            case_id=case2.id,
            event_type="CASE_CREATED",
            origin=TimelineOrigin.SYSTEM_EVENT,
            actor="CivicLoop System",
            source="Intake Engine",
            payload={"initial_status": "OPEN", "ward": case2.ward},
        )
        record_event(
            db=db,
            case_id=case2.id,
            event_type="OFFICIAL_STATUS_RETRIEVED",
            origin=TimelineOrigin.SOURCE_FACT,
            actor="Namma Bengaluru Connector",
            source="Official Civic Portal",
            payload={"official_status": "CLOSED", "external_id": "NBG-SWD-2026-43109"},
        )
        record_event(
            db=db,
            case_id=case2.id,
            event_type="VERIFICATION_STATE_CHANGED",
            origin=TimelineOrigin.USER_CLAIM,
            actor="Ramesh Kumar (Citizen)",
            source="Citizen Dispute Portal",
            payload={
                "old_state": "AWAITING_VERIFICATION",
                "new_state": "RESOLUTION_DISPUTED",
                "reason": "Official status claims completed, but ground photo audit confirms culvert still choked with excavated silt.",
            },
        )
        record_event(
            db=db,
            case_id=case2.id,
            event_type="AI_RECOMMENDATION_POSTED",
            origin=TimelineOrigin.AI_RECOMMENDATION,
            actor="CivicLoop Agent (DeepSeek V4)",
            source="Agent Escalation Engine",
            payload={
                "action": "DRAFT_SAKALA_ESCALATION",
                "legal_citation": "Karnataka Sakala Services Act 2011 Section 7 (compensatory penalty)",
                "authority_addressed": "Assistant Executive Engineer (SWD), East Zone",
            },
        )

        # 4. Case 3: Ward 174 HSR Layout (GARBAGE - CITIZEN CONFIRMED RESOLVED)
        logger.info("Seeding Case 3: Ward 174 HSR Layout...")
        case3 = Case(
            user_id=citizen.id,
            title="Blackspot Waste Dumping at Sector 3 14th Main Park Rear Lane",
            issue_category="GARBAGE",
            location_text="Sector 3, 14th Main Park Rear Lane, Ward 174, HSR Layout, Bengaluru",
            lat=12.9116,
            lng=77.6388,
            ward="Ward 174 - HSR Layout",
            jurisdiction="BBMP Bommanahalli Zone",
            status="CLOSED",
            verification_state="CITIZEN_CONFIRMED_RESOLVED",
        )
        db.add(case3)
        db.commit()
        db.refresh(case3)

        complaint3 = ComplaintRecord(
            case_id=case3.id,
            source="Swachhata App (Simulated MOCK)",
            external_id="SWCH-BLR-2026-10294",
            raw_text="Secondary dumping blackspot near park perimeter wall. Dry leaves and mixed plastic waste accumulating for 5 days.",
            official_status="RESOLVED",
            official_status_retrieved_at=datetime.now(timezone.utc) - timedelta(hours=1),
            retrieval_method="MOCK",
            extracted_json={"spot_cleared": True, "cleanliness_score": "A"},
            confidence=0.99,
        )
        db.add(complaint3)
        db.commit()

        evidence3 = Evidence(
            case_id=case3.id,
            file_path="/evidence/ward174_hsr_cleared_spot.jpg",
            mime="image/jpeg",
            exif_json={"lat": 12.9116, "lng": 77.6388, "camera": "Pixel 8"},
            captured_at=datetime.now(timezone.utc) - timedelta(minutes=45),
            supplied_by=citizen.id,
            provenance="CITIZEN_INSPECTION_CONFIRMED",
            ai_description="Lane cleared completely of debris, lime powder applied on ground, civic awareness notice installed.",
        )
        db.add(evidence3)
        db.commit()

        record_event(
            db=db,
            case_id=case3.id,
            event_type="CASE_CREATED",
            origin=TimelineOrigin.SYSTEM_EVENT,
            actor="CivicLoop System",
            source="Intake Engine",
            payload={"initial_status": "OPEN", "ward": case3.ward},
        )
        record_event(
            db=db,
            case_id=case3.id,
            event_type="OFFICIAL_STATUS_UPDATED",
            origin=TimelineOrigin.SOURCE_FACT,
            actor="Swachhata Mock Connector",
            source="Swachhata App",
            payload={"official_status": "RESOLVED"},
        )
        record_event(
            db=db,
            case_id=case3.id,
            event_type="VERIFICATION_STATE_CHANGED",
            origin=TimelineOrigin.USER_CLAIM,
            actor="Ramesh Kumar (Citizen)",
            source="Citizen Verification Inspection",
            payload={
                "old_state": "AWAITING_VERIFICATION",
                "new_state": "CITIZEN_CONFIRMED_RESOLVED",
                "reason": "Citizen inspected location in person. BBMP Marshals cleared waste, washed lane, and posted warning banner.",
            },
        )

        # 5. Seed Background Tasks
        logger.info("Seeding background tasks...")
        task1 = Task(
            case_id=case1.id,
            task_type="SYNC_EXTERNAL_STATUS",
            status="PENDING",
            run_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            attempts=0,
            max_attempts=3,
            idempotency_key=f"sync_status_{case1.id}_20261009",
            payload_json={"connector": "BBMP_SAHAAYA", "ticket_id": "BBMP-SHY-2026-89412"},
        )
        task2 = Task(
            case_id=case2.id,
            task_type="AUDIT_VERIFICATION_DISPUTE",
            status="PENDING",
            run_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            attempts=0,
            max_attempts=3,
            idempotency_key=f"audit_dispute_{case2.id}_20261009",
            payload_json={"dispute_type": "FALSE_CLOSURE", "escalate_to": "SAKALA"},
        )
        db.add_all([task1, task2])
        db.commit()

        # 6. Seed Knowledge Chunks
        logger.info("Seeding grounded knowledge chunks...")
        knowledge_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../knowledge"))
        
        # Load bengaluru_wards.json
        wards_file = os.path.join(knowledge_dir, "bengaluru_wards.json")
        if os.path.exists(wards_file):
            with open(wards_file, "r", encoding="utf-8") as f:
                wards_data = json.load(f)
                for w in wards_data:
                    chunk = KnowledgeChunk(
                        title=f"Bengaluru Ward {w['ward_number']}: {w['ward_name']} Context",
                        department=w['jurisdiction'],
                        jurisdiction=w['zone'],
                        text=json.dumps(w, indent=2),
                    )
                    db.add(chunk)

        # Load SWM SOP
        swm_sop_file = os.path.join(knowledge_dir, "bbmp_garbage_swm_sop.md")
        if os.path.exists(swm_sop_file):
            with open(swm_sop_file, "r", encoding="utf-8") as f:
                swm_text = f.read()
                db.add(KnowledgeChunk(
                    title="BBMP Solid Waste Management (SWM) Standard Operating Procedure",
                    department="BBMP Solid Waste Management Department",
                    jurisdiction="Bruhat Bengaluru Mahanagara Palike",
                    text=swm_text,
                ))

        # Load SWD SOP
        swd_sop_file = os.path.join(knowledge_dir, "bbmp_drainage_sop.md")
        if os.path.exists(swd_sop_file):
            with open(swd_sop_file, "r", encoding="utf-8") as f:
                swd_text = f.read()
                db.add(KnowledgeChunk(
                    title="BBMP Storm Water Drain (SWD / Raja Kaluve) SOP",
                    department="BBMP Storm Water Drains (SWD) Department",
                    jurisdiction="Bruhat Bengaluru Mahanagara Palike",
                    text=swd_text,
                ))

        # Load Citizen Charter
        charter_file = os.path.join(knowledge_dir, "citizen_charter_karnataka.json")
        if os.path.exists(charter_file):
            with open(charter_file, "r", encoding="utf-8") as f:
                charter_text = f.read()
                db.add(KnowledgeChunk(
                    title="Karnataka Sakala Services Act 2011 Citizen Charter & Timelines",
                    department="DPAR Karnataka / Sakala Mission",
                    jurisdiction="Government of Karnataka",
                    text=charter_text,
                ))

        db.commit()
        logger.info("Database seeding successfully completed!")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
