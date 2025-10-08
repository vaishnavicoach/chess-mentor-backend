from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import secrets

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
try:
    client.admin.command('ping')
    print("✅ MongoDB connection successful!")
except Exception as e:
    print("❌ MongoDB connection failed:", e)


# Create the main app without a prefix
app = FastAPI(title="Chess Mentor Hub API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

security = HTTPBasic()

# Assessment Models
class OpeningAssessment(BaseModel):
    white_openings: str = ""
    black_openings: str = ""
    preparation_depth: int = 1  # 1-20 moves
    opening_study_time: int = 0  # minutes per week
    favorite_opening: str = ""
    opening_weaknesses: str = ""
    opening_study_resources: str = ""

class MiddlegameAssessment(BaseModel):
    calculation_ability: int = 1  # 1-10
    tactical_vision: int = 1  # 1-10
    middlegame_study_time: int = 0  # minutes per week
    main_problems: str = ""
    pattern_recognition: str = ""
    strategic_understanding: str = ""
    piece_coordination: str = ""
    attack_defense_balance: str = ""

class EndgameAssessment(BaseModel):
    endgame_calculation: int = 1  # 1-10
    theoretical_knowledge: int = 1  # 1-10
    endgame_study_time: int = 0  # minutes per week
    endgame_intuition: str = ""
    practical_application: str = ""
    pawn_endgames: int = 1  # 1-10
    rook_endgames: int = 1  # 1-10
    bishop_endgames: int = 1  # 1-10
    knight_endgames: int = 1  # 1-10
    queen_endgames: int = 1  # 1-10

class PsychologyAssessment(BaseModel):
    confidence_level: int = 1  # 1-10
    motivation_level: int = 1  # 1-10
    focus_duration: int = 10  # minutes
    anxiety_management: str = ""
    pressure_handling: str = ""
    tilt_recovery: str = ""
    competitive_mindset: str = ""
    mental_preparation: str = ""
    self_evaluation_skills: str = ""

class StudyHabitsAssessment(BaseModel):
    daily_study_time: int = 10  # minutes
    study_consistency: int = 1  # 1-10
    preferred_methods: str = ""
    analysis_habits: str = ""
    game_review_frequency: str = ""
    coach_interaction: str = ""
    goal_setting: str = ""
    study_resources: str = ""

class GeneralAssessment(BaseModel):
    physical_stamina: int = 1  # 1-10
    sleep_before_games: float = 8.0  # hours (allow float for half-hour values)
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

# Coach Models
class Coach(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CoachCreate(BaseModel):
    username: str
    password: str

class CoachLogin(BaseModel):
    username: str
    password: str

# Assessment Summary for Dashboard
class AssessmentSummary(BaseModel):
    assessment_id: str
    player_name: str
    submission_date: datetime
    overall_score: float
    critical_areas: List[str]  # Areas with scores <= 3
    strengths: List[str]       # Areas with scores >= 8
    
# Utility function to prepare data for MongoDB
def prepare_for_mongo(data: dict) -> dict:
    """Convert datetime objects to ISO strings for MongoDB storage"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = prepare_for_mongo(value)
    return data

def parse_from_mongo(data: dict) -> dict:
    """Convert ISO strings back to datetime objects"""
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ['submission_date', 'created_at'] and isinstance(value, str):
                try:
                    data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except:
                    pass
            elif isinstance(value, dict):
                data[key] = parse_from_mongo(value)
    return data

# Assessment calculation utilities
def calculate_section_score(section_data: dict, section_type: str) -> float:
    """Calculate average score for a section based on numerical ratings"""
    scores = []
    
    if section_type == "opening":
        scores = [section_data.get("preparation_depth", 1) / 20 * 10]  # Convert to 1-10 scale
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
            min(section_data.get("focus_duration", 10) / 60 * 10, 10)  # Convert minutes to 1-10 scale
        ]
    elif section_type == "study_habits":
        scores = [
            section_data.get("study_consistency", 1),
            min(section_data.get("daily_study_time", 10) / 120 * 10, 10)  # Convert minutes to 1-10 scale
        ]
    elif section_type == "general":
        scores = [
            section_data.get("physical_stamina", 1),
            min(section_data.get("sleep_before_games", 8) / 8 * 10, 10)  # Convert hours to 1-10 scale
        ]
    
    return sum(scores) / len(scores) if scores else 1.0

def analyze_assessment(assessment: dict) -> dict:
    """Analyze assessment and generate summary data"""
    sections = ['opening', 'middlegame', 'endgame', 'psychology', 'study_habits', 'general']
    section_scores = {}
    critical_areas = []
    strengths = []
    
    for section in sections:
        if section in assessment:
            score = calculate_section_score(assessment[section], section)
            section_scores[section] = score
            
            if score <= 3:
                critical_areas.append(section.replace('_', ' ').title())
            elif score >= 8:
                strengths.append(section.replace('_', ' ').title())
    
    overall_score = sum(section_scores.values()) / len(section_scores) if section_scores else 1.0
    
    return {
        'overall_score': overall_score,
        'section_scores': section_scores,
        'critical_areas': critical_areas,
        'strengths': strengths
    }

from passlib.hash import bcrypt

def hash_password(password: str) -> str:
    """Hash the password securely before storing"""
    try:
        password = str(password).strip()
        if len(password.encode("utf-8")) > 72:
            password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
        hashed = bcrypt.hash(password)
        print(f"✅ Password hashed successfully: {hashed[:20]}...")  # Debug preview
        return hashed
    except Exception as e:
        print("❌ Error hashing password:", e)
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash"""
    try:
        plain_password = str(plain_password).strip()
        hashed_password = str(hashed_password).strip()

        if not plain_password or not hashed_password:
            print("❌ Empty password or hash during verification")
            return False

        if len(plain_password.encode("utf-8")) > 72:
            plain_password = plain_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")

        result = bcrypt.verify(plain_password, hashed_password)
        print(f"✅ bcrypt verification result: {result}")
        return result
    except Exception as e:
        print("❌ Password verification error:", e)
        return False


# Routes
@api_router.get("/")
async def root():
    return {"message": "Chess Mentor Hub API"}

# Assessment routes
@api_router.post("/assessments", response_model=PlayerAssessment)
async def create_assessment(assessment_data: PlayerAssessmentCreate):
    """Create a new player assessment"""
    try:
        assessment = PlayerAssessment(**assessment_data.dict())
        assessment_dict = prepare_for_mongo(assessment.dict())
        
        result = await db.assessments.insert_one(assessment_dict)
        
        if result.inserted_id:
            return assessment
        else:
            raise HTTPException(status_code=500, detail="Failed to create assessment")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating assessment: {str(e)}")

@api_router.get("/assessments", response_model=List[PlayerAssessment])
async def get_all_assessments():
    """Get all player assessments"""
    try:
        assessments = await db.assessments.find({}, {"_id": 0}).sort("submission_date", -1).to_list(1000)
        return [PlayerAssessment(**parse_from_mongo(assessment)) for assessment in assessments]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching assessments: {str(e)}")

@api_router.get("/assessments/{assessment_id}", response_model=PlayerAssessment)
async def get_assessment(assessment_id: str):
    """Get a specific assessment by ID"""
    try:
        assessment = await db.assessments.find_one({"id": assessment_id}, {"_id": 0})
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        return PlayerAssessment(**parse_from_mongo(assessment))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching assessment: {str(e)}")

@api_router.get("/assessments/summary/all")
async def get_assessments_summary():
    """Get summary of all assessments with analysis"""
    try:
        assessments = await db.assessments.find({}, {"_id": 0}).sort("submission_date", -1).to_list(1000)
        
        summaries = []
        for assessment in assessments:
            parsed_assessment = parse_from_mongo(assessment)
            analysis = analyze_assessment(parsed_assessment)
            
            summary = {
                "assessment_id": parsed_assessment["id"],
                "player_name": parsed_assessment["player_name"],
                "submission_date": parsed_assessment["submission_date"],
                "overall_score": analysis["overall_score"],
                "section_scores": analysis["section_scores"],
                "critical_areas": analysis["critical_areas"],
                "strengths": analysis["strengths"]
            }
            summaries.append(summary)
            
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summaries: {str(e)}")

# Coach routes
@api_router.post("/coaches/register", response_model=Coach)
async def register_coach(coach_data: CoachCreate):
    """Register a new coach"""
    try:
        # Check if username already exists
        existing_coach = await db.coaches.find_one({"username": coach_data.username})
        if existing_coach:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        print("🔍 Raw password data:", coach_data.password, type(coach_data.password))

        coach = Coach(
            username=coach_data.username,
            password_hash=hash_password(coach_data.password)
        )
        
        coach_dict = prepare_for_mongo(coach.dict())
        result = await db.coaches.insert_one(coach_dict)
        
        if result.inserted_id:
            return coach
        else:
            raise HTTPException(status_code=500, detail="Failed to register coach")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error registering coach: {str(e)}")

from fastapi import Request

@api_router.post("/coaches/login")
async def login_coach(request: Request):
    """Authenticate a coach (safe and axios-compatible)"""
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        print("🧠 Login attempt:", username, password)

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")

        coach = await db.coaches.find_one({"username": username})
        if not coach:
            print("❌ No coach found:", username)
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        print("🧠 Stored hash:", coach.get("password_hash"))

        if not verify_password(password, coach["password_hash"]):
            print("❌ Password verification failed")
            raise HTTPException(status_code=401, detail="Incorrect username or password")

        print("✅ Login success for:", username)
        return {
            "message": "Login successful",
            "coach_id": coach["id"],
            "username": coach["username"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Error during login:", e)
        raise HTTPException(status_code=500, detail=f"Error during login: {str(e)}")


@api_router.get("/coaches")
async def get_coaches():
    """Get all coaches (for admin purposes)"""
    try:
        coaches = await db.coaches.find({}, {"password_hash": 0, "_id": 0}).to_list(1000)
        return [parse_from_mongo(coach) for coach in coaches]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching coaches: {str(e)}")

# Health check
@api_router.get("/health")
async def health_check():
    """API health check"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

# Include the router in the main app
app.include_router(api_router)

# ✅ Define allowed origins explicitly
allowed_origins = os.environ.get(
    'CORS_ORIGINS',
    'https://hca-coachmentor.netlify.app,http://localhost:3000'
).split(',')

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def root():
    return {"message": "🎉 Chess Mentor Backend is Live and Connected!"}


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)