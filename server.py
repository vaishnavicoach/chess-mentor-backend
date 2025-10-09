from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime, timezone
import json

# ----------------------------------------------------------------
# 🌍 Load environment
# ----------------------------------------------------------------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ----------------------------------------------------------------
# 🧩 MongoDB connection
# ----------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

try:
    client.admin.command('ping')
    print("✅ MongoDB connection successful!")
except Exception as e:
    print("❌ MongoDB connection failed:", e)

# ----------------------------------------------------------------
# ⚙️ App setup
# ----------------------------------------------------------------
app = FastAPI(title="Chess Mentor Hub API")
api_router = APIRouter(prefix="/api")

# ----------------------------------------------------------------
# 🧩 Models
# ----------------------------------------------------------------
class OpeningAssessment(BaseModel):
    white_openings: str = ""
    black_openings: str = ""
    preparation_depth: int = 1
    opening_study_time: int = 0
    favorite_opening: str = ""
    opening_weaknesses: str = ""
    opening_study_resources: str = ""

class MiddlegameAssessment(BaseModel):
    calculation_ability: int = 1
    tactical_vision: int = 1
    middlegame_study_time: int = 0
    main_problems: str = ""
    pattern_recognition: str = ""
    strategic_understanding: str = ""
    piece_coordination: str = ""
    attack_defense_balance: str = ""

class EndgameAssessment(BaseModel):
    endgame_calculation: int = 1
    theoretical_knowledge: int = 1
    endgame_study_time: int = 0
    endgame_intuition: str = ""
    practical_application: str = ""
    pawn_endgames: int = 1
    rook_endgames: int = 1
    bishop_endgames: int = 1
    knight_endgames: int = 1
    queen_endgames: int = 1

class PsychologyAssessment(BaseModel):
    confidence_level: int = 1
    motivation_level: int = 1
    focus_duration: int = 10
    anxiety_management: str = ""
    pressure_handling: str = ""
    tilt_recovery: str = ""
    competitive_mindset: str = ""
    mental_preparation: str = ""
    self_evaluation_skills: str = ""

class StudyHabitsAssessment(BaseModel):
    daily_study_time: int = 10
    study_consistency: int = 1
    preferred_methods: str = ""
    analysis_habits: str = ""
    game_review_frequency: str = ""
    coach_interaction: str = ""
    goal_setting: str = ""
    study_resources: str = ""

class GeneralAssessment(BaseModel):
    physical_stamina: int = 1
    sleep_before_games: float = 8.0
    nutrition_habits: str = ""
    exercise_routine: str = ""
    technology_usage: str = ""
    tournament_purpose: str = ""
    additional_notes: str = ""

class PlayerAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_name: str
    submission_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    opening: OpeningAssessment
    middlegame: MiddlegameAssessment
    endgame: EndgameAssessment
    psychology: PsychologyAssessment
    study_habits: StudyHabitsAssessment
    general: GeneralAssessment

class PlayerAssessmentCreate(BaseModel):
    player_name: str
    opening: OpeningAssessment
    middlegame: MiddlegameAssessment
    endgame: EndgameAssessment
    psychology: PsychologyAssessment
    study_habits: StudyHabitsAssessment
    general: GeneralAssessment

# ----------------------------------------------------------------
# 🧠 Utility functions
# ----------------------------------------------------------------
def prepare_for_mongo(data: dict) -> dict:
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
        elif isinstance(v, dict):
            data[k] = prepare_for_mongo(v)
    return data

def parse_from_mongo(data: dict) -> dict:
    for k, v in data.items():
        if k in ['submission_date', 'created_at'] and isinstance(v, str):
            try:
                data[k] = datetime.fromisoformat(v.replace('Z', '+00:00'))
            except:
                pass
        elif isinstance(v, dict):
            data[k] = parse_from_mongo(v)
    return data

def calculate_section_score(section_data: dict, section_type: str) -> float:
    scores = []
    if section_type == "opening":
        scores = [section_data.get("preparation_depth", 1) / 20 * 10]
    elif section_type == "middlegame":
        scores = [
            section_data.get("calculation_ability", 1),
            section_data.get("tactical_vision", 1)
        ]
    elif section_type == "endgame":
        scores = [
            section_data.get("endgame_calculation", 1),
            section_data.get("theoretical_knowledge", 1),
            section_data.get("pawn_endgames", 1),
            section_data.get("rook_endgames", 1),
            section_data.get("bishop_endgames", 1),
            section_data.get("knight_endgames", 1),
            section_data.get("queen_endgames", 1)
        ]
    elif section_type == "psychology":
        scores = [
            section_data.get("confidence_level", 1),
            section_data.get("motivation_level", 1),
            min(section_data.get("focus_duration", 10) / 60 * 10, 10)
        ]
    elif section_type == "study_habits":
        scores = [
            section_data.get("study_consistency", 1),
            min(section_data.get("daily_study_time", 10) / 120 * 10, 10)
        ]
    elif section_type == "general":
        scores = [
            section_data.get("physical_stamina", 1),
            min(section_data.get("sleep_before_games", 8) / 8 * 10, 10)
        ]
    return sum(scores) / len(scores) if scores else 1.0

def analyze_assessment(assessment: dict) -> dict:
    sections = ['opening', 'middlegame', 'endgame', 'psychology', 'study_habits', 'general']
    section_scores = {}
    critical_areas, strengths = [], []

    for section in sections:
        if section in assessment:
            score = calculate_section_score(assessment[section], section)
            section_scores[section] = score
            if score <= 3:
                critical_areas.append(section.title())
            elif score >= 8:
                strengths.append(section.title())

    overall_score = sum(section_scores.values()) / len(section_scores)
    return {"overall_score": overall_score, "section_scores": section_scores, "critical_areas": critical_areas, "strengths": strengths}

# ----------------------------------------------------------------
# 🧑‍🏫 Predefined Coaches (no registration needed)
# ----------------------------------------------------------------
COACHES_JSON = os.environ.get("COACHES_JSON", "")
if COACHES_JSON:
    try:
        PREDEFINED_COACHES = json.loads(COACHES_JSON)
    except:
        PREDEFINED_COACHES = {}
else:
    PREDEFINED_COACHES = {
        "coachvaishnavi": "Shrinika2@",
        "GMvishnu": "hapchess1",
        "GMakash": "hapchess2",
        "coachganesh": "hapchess3",
        "coachgowthamkk": "hapchess4",
        "coachgowtham": "hapchess5",
        "coachibrahim": "hapchess6"
    }

# ----------------------------------------------------------------
# 📊 Assessment Routes
# ----------------------------------------------------------------
@api_router.post("/assessments", response_model=PlayerAssessment)
async def create_assessment(assessment_data: PlayerAssessmentCreate):
    assessment = PlayerAssessment(**assessment_data.dict())
    result = await db.assessments.insert_one(prepare_for_mongo(assessment.dict()))
    if result.inserted_id:
        return assessment
    raise HTTPException(status_code=500, detail="Failed to create assessment")

@api_router.get("/assessments", response_model=List[PlayerAssessment])
async def get_all_assessments():
    assessments = await db.assessments.find({}, {"_id": 0}).sort("submission_date", -1).to_list(1000)
    return [PlayerAssessment(**parse_from_mongo(a)) for a in assessments]

@api_router.get("/assessments/summary/all")
async def get_assessments_summary():
    assessments = await db.assessments.find({}, {"_id": 0}).to_list(1000)
    summaries = []
    for a in assessments:
        parsed = parse_from_mongo(a)
        analysis = analyze_assessment(parsed)
        summaries.append({
            "assessment_id": parsed["id"],
            "player_name": parsed["player_name"],
            "submission_date": parsed["submission_date"],
            **analysis
        })
    return summaries

# ----------------------------------------------------------------
# 👥 Coach Login Only (no registration)
# ----------------------------------------------------------------
@api_router.post("/coaches/login")
async def login_coach(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    stored_password = PREDEFINED_COACHES.get(username)
    if not stored_password or stored_password != password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    print(f"✅ Login success for: {username}")
    return {"message": "Login successful", "coach_id": username, "username": username}

# ----------------------------------------------------------------
# ❤️ Health Check
# ----------------------------------------------------------------
@app.get("/")
async def home():
    return {"message": "🎉 Chess Mentor Backend is Live and Connected!"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

# ----------------------------------------------------------------
# 🛡️ CORS Setup (add before including routes)
# ----------------------------------------------------------------
allowed_origins = [
    "https://hcacoachmentor.netlify.app",
    "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------
# 🔗 Include routes after CORS
# ----------------------------------------------------------------
app.include_router(api_router)

# ----------------------------------------------------------------
# 🧹 Cleanup
# ----------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# ----------------------------------------------------------------
# 🚀 Run locally
# ----------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
