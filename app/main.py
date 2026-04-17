import os
import smtplib
import csv
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, BackgroundTasks, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

from sqlalchemy.orm import Session
from . import models, database

# Load ENV
load_dotenv()

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
TARGET_EMAIL = os.getenv("TARGET_EMAIL")

if not ADMIN_USER or not ADMIN_PASSWORD:
    print("WARNING: ADMIN_USER o ADMIN_PASSWORD no configurados.")
if not TARGET_EMAIL:
    print("WARNING: TARGET_EMAIL no configurado.")

# Init DB
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Evaluación PRISMA", version="1.1.0")
security = HTTPBasic()

# Rutas absolutas para producción y Vercel
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mount static and templates
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Dependency DB
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth Dependency
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    if not ADMIN_USER or not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="Credenciales de admin no configuradas en servidor")
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Email Task (Manual)
def send_notification_email_manual(response_id: int, name: str, email: str, response_data: dict):
    if not SMTP_USERNAME or not SMTP_PASSWORD or not TARGET_EMAIL:
        print("Atención: Credenciales SMTP no configuradas. Correo no enviado.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = TARGET_EMAIL
        msg["Subject"] = f"Nueva Evaluación PRISMA MANUAL de: {name}"

        body = f"""
        <html>
          <body>
            <h2>Nueva respuesta - Evaluación MANUAL</h2>
            <p><strong>ID:</strong> {response_id}</p>
            <p><strong>Nombre:</strong> {name}</p>
            <p><strong>Correo del participante:</strong> {email}</p>
            <p><strong>Tiempo (minutos):</strong> {response_data.get('time_minutes')}</p>
            <hr>
            <h3>Calificaciones (1 a 5):</h3>
            <ul>
              <li><strong>q1_filters:</strong> {response_data.get('q1_filters')}</li>
              <li><strong>q2_export:</strong> {response_data.get('q2_export')}</li>
              <li><strong>q3_dedup_visual:</strong> {response_data.get('q3_dedup_visual')}</li>
              <li><strong>q4_dedup_error:</strong> {response_data.get('q4_dedup_error')}</li>
              <li><strong>q5_screen_fatigue:</strong> {response_data.get('q5_screen_fatigue')}</li>
              <li><strong>q6_screen_fear:</strong> {response_data.get('q6_screen_fear')}</li>
              <li><strong>q7_synthesis_slow:</strong> {response_data.get('q7_synthesis_slow')}</li>
              <li><strong>q8_reproducibility:</strong> {response_data.get('q8_reproducibility')}</li>
            </ul>
            <p><strong>Cuello de botella:</strong></p>
            <p>"{response_data.get('q9_bottleneck')}"</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Correo enviado exitosamente a {TARGET_EMAIL}")
    except Exception as e:
        print(f"Error enviando correo: {e}")

# Email Task (AI)
def send_notification_email_ai(response_id: int, name: str, email: str, response_data: dict):
    if not SMTP_USERNAME or not SMTP_PASSWORD or not TARGET_EMAIL:
        print("Atención: Credenciales SMTP no configuradas. Correo no enviado.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = TARGET_EMAIL
        msg["Subject"] = f"Nueva Evaluación PRISMA IA de: {name}"

        body = f"""
        <html>
          <body>
            <h2>Nueva respuesta - Evaluación SISTEMA IA</h2>
            <p><strong>ID:</strong> {response_id}</p>
            <p><strong>Nombre:</strong> {name}</p>
            <p><strong>Correo del participante:</strong> {email}</p>
            <p><strong>Tiempo (minutos):</strong> {response_data.get('time_minutes')}</p>
            <hr>
            <h3>Calificaciones (1 a 5):</h3>
            <ul>
              <li><strong>1. Esfuerzo Deduplicación:</strong> {response_data.get('q1_ai_dedup_effort')}</li>
              <li><strong>2. Confianza Deduplicación:</strong> {response_data.get('q2_ai_dedup_trust')}</li>
              <li><strong>3. Fatiga Screening:</strong> {response_data.get('q3_ai_screening_fatigue')}</li>
              <li><strong>4. Confianza Screening (Miedo descarte):</strong> {response_data.get('q4_ai_screening_trust')}</li>
              <li><strong>5. Tiempo Síntesis automatizada:</strong> {response_data.get('q5_ai_synthesis_time')}</li>
              <li><strong>6. Reproducibilidad metodológica:</strong> {response_data.get('q6_ai_reproducibility')}</li>
              <li><strong>7. Viabilidad plataforma:</strong> {response_data.get('q7_ai_viability')}</li>
            </ul>
            <p><strong>Cualitativa 1 (Mayor impacto):</strong></p>
            <p>"{response_data.get('q8_ai_best_feature')}"</p>
            <p><strong>Cualitativa 2 (Errores o alucinaciones):</strong></p>
            <p>"{response_data.get('q9_ai_hallucinations')}"</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Correo AI enviado exitosamente a {TARGET_EMAIL}")
    except Exception as e:
        print(f"Error enviando correo: {e}")

# Routes HTML
@app.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")

@app.get("/form/manual", response_class=HTMLResponse)
async def read_form_manual(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/form/ai", response_class=HTMLResponse)
async def read_form_ai(request: Request):
    return templates.TemplateResponse(request=request, name="form_ai.html")

# Submit Routes
@app.post("/submit/manual", response_class=HTMLResponse)
async def submit_form_manual(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    time_minutes: float = Form(0.0),
    q1_filters: int = Form(...),
    q2_export: int = Form(...),
    q3_dedup_visual: int = Form(...),
    q4_dedup_error: int = Form(...),
    q5_screen_fatigue: int = Form(...),
    q6_screen_fear: int = Form(...),
    q7_synthesis_slow: int = Form(...),
    q8_reproducibility: int = Form(...),
    q9_bottleneck: str = Form(...),
    db: Session = Depends(get_db)
):
    new_response = models.EvaluationResponse(
        name=name, email=email, time_minutes=time_minutes,
        q1_filters=q1_filters, q2_export=q2_export, q3_dedup_visual=q3_dedup_visual,
        q4_dedup_error=q4_dedup_error, q5_screen_fatigue=q5_screen_fatigue,
        q6_screen_fear=q6_screen_fear, q7_synthesis_slow=q7_synthesis_slow,
        q8_reproducibility=q8_reproducibility, q9_bottleneck=q9_bottleneck
    )
    db.add(new_response)
    db.commit()
    db.refresh(new_response)

    response_data = {"time_minutes": time_minutes, "q1_filters": q1_filters, "q2_export": q2_export, "q3_dedup_visual": q3_dedup_visual, "q4_dedup_error": q4_dedup_error, "q5_screen_fatigue": q5_screen_fatigue, "q6_screen_fear": q6_screen_fear, "q7_synthesis_slow": q7_synthesis_slow, "q8_reproducibility": q8_reproducibility, "q9_bottleneck": q9_bottleneck}
    background_tasks.add_task(send_notification_email_manual, new_response.id, name, email, response_data)
    return templates.TemplateResponse(request=request, name="success.html", context={"name": name})

@app.post("/submit/ai", response_class=HTMLResponse)
async def submit_form_ai(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    time_minutes: float = Form(0.0),
    q1_ai_dedup_effort: int = Form(...),
    q2_ai_dedup_trust: int = Form(...),
    q3_ai_screening_fatigue: int = Form(...),
    q4_ai_screening_trust: int = Form(...),
    q5_ai_synthesis_time: int = Form(...),
    q6_ai_reproducibility: int = Form(...),
    q7_ai_viability: int = Form(...),
    q8_ai_best_feature: str = Form(...),
    q9_ai_hallucinations: str = Form(...),
    db: Session = Depends(get_db)
):
    new_response = models.AIEvaluationResponse(
        name=name, email=email, time_minutes=time_minutes,
        q1_ai_dedup_effort=q1_ai_dedup_effort, q2_ai_dedup_trust=q2_ai_dedup_trust,
        q3_ai_screening_fatigue=q3_ai_screening_fatigue, q4_ai_screening_trust=q4_ai_screening_trust,
        q5_ai_synthesis_time=q5_ai_synthesis_time, q6_ai_reproducibility=q6_ai_reproducibility,
        q7_ai_viability=q7_ai_viability, q8_ai_best_feature=q8_ai_best_feature,
        q9_ai_hallucinations=q9_ai_hallucinations
    )
    db.add(new_response)
    db.commit()
    db.refresh(new_response)

    response_data = {
        "time_minutes": time_minutes, "q1_ai_dedup_effort": q1_ai_dedup_effort, "q2_ai_dedup_trust": q2_ai_dedup_trust, 
        "q3_ai_screening_fatigue": q3_ai_screening_fatigue, "q4_ai_screening_trust": q4_ai_screening_trust, 
        "q5_ai_synthesis_time": q5_ai_synthesis_time, "q6_ai_reproducibility": q6_ai_reproducibility, 
        "q7_ai_viability": q7_ai_viability, "q8_ai_best_feature": q8_ai_best_feature, "q9_ai_hallucinations": q9_ai_hallucinations
    }
    background_tasks.add_task(send_notification_email_ai, new_response.id, name, email, response_data)
    return templates.TemplateResponse(request=request, name="success.html", context={"name": name})

# Admin Routes
@app.get("/admin", response_class=HTMLResponse)
async def view_admin(
    request: Request, 
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    resp_manual = db.query(models.EvaluationResponse).order_by(models.EvaluationResponse.id.desc()).all()
    resp_ai = db.query(models.AIEvaluationResponse).order_by(models.AIEvaluationResponse.id.desc()).all()
    return templates.TemplateResponse(request=request, name="admin.html", context={"resp_manual": resp_manual, "resp_ai": resp_ai})

@app.post("/admin/delete/manual/{response_id}")
async def delete_response_manual(
    response_id: int,
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    resp = db.query(models.EvaluationResponse).filter(models.EvaluationResponse.id == response_id).first()
    if resp:
        db.delete(resp)
        db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/delete/ai/{response_id}")
async def delete_response_ai(
    response_id: int,
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    resp = db.query(models.AIEvaluationResponse).filter(models.AIEvaluationResponse.id == response_id).first()
    if resp:
        db.delete(resp)
        db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/edit/manual/{response_id}")
async def edit_time_manual(
    response_id: int,
    time_minutes: float = Form(...),
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    resp = db.query(models.EvaluationResponse).filter(models.EvaluationResponse.id == response_id).first()
    if not resp:
        raise HTTPException(status_code=404, detail=f"Respuesta manual con ID {response_id} no encontrada.")
    try:
        resp.time_minutes = time_minutes
        db.commit()
        db.refresh(resp)
        print(f"[EDIT OK] Manual ID={response_id} -> time_minutes={time_minutes}")
    except Exception as e:
        db.rollback()
        print(f"[EDIT ERROR] Manual ID={response_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar: {e}")
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/edit/ai/{response_id}")
async def edit_time_ai(
    response_id: int,
    time_minutes: float = Form(...),
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    resp = db.query(models.AIEvaluationResponse).filter(models.AIEvaluationResponse.id == response_id).first()
    if not resp:
        raise HTTPException(status_code=404, detail=f"Respuesta IA con ID {response_id} no encontrada.")
    try:
        resp.time_minutes = time_minutes
        db.commit()
        db.refresh(resp)
        print(f"[EDIT OK] AI ID={response_id} -> time_minutes={time_minutes}")
    except Exception as e:
        db.rollback()
        print(f"[EDIT ERROR] AI ID={response_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al guardar: {e}")
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

from sqlalchemy import text
@app.get("/admin/migrate-db")
async def migrate_db(username: str = Depends(get_current_username), db: Session = Depends(get_db)):
    try:
        from .database import engine
        if engine.dialect.name == "postgresql":
            db.execute(text("ALTER TABLE evaluation_responses ALTER COLUMN time_minutes TYPE DOUBLE PRECISION;"))
            db.execute(text("ALTER TABLE ai_evaluation_responses ALTER COLUMN time_minutes TYPE DOUBLE PRECISION;"))
            db.commit()
            return {"status": "Exito: La base de datos (Postgres) fue migrada a decimales correctamente."}
        else:
            return {"status": f"No se requieren cambios en {engine.dialect.name}. Intente borrar la bd sqlite y reiniciar si esta en local."}
    except Exception as e:
        db.rollback()
        return {"status": "Error", "detalle": str(e)}

@app.get("/admin/export/manual")
async def export_csv_manual(
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    responses = db.query(models.EvaluationResponse).order_by(models.EvaluationResponse.id.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["ID", "Fecha", "Nombre", "Correo", "Tiempo (minutos)", "Q1: Busqueda y Filtros", "Q2: Exportar y Consolidar", "Q3: Deduplicacion Visual", "Q4: Inseguridad Excel", "Q5: Fatiga de Screening", "Q6: Miedo de Descartar", "Q7: Síntesis y Matriz", "Q8: Reproducibilidad", "Q9: Cuello de Botella"])
    for r in responses:
        writer.writerow([r.id, r.created_at.strftime('%Y-%m-%d %H:%M'), r.name, r.email, r.time_minutes, r.q1_filters, r.q2_export, r.q3_dedup_visual, r.q4_dedup_error, r.q5_screen_fatigue, r.q6_screen_fear, r.q7_synthesis_slow, r.q8_reproducibility, r.q9_bottleneck])
    csv_bytes = "\ufeff" + output.getvalue()
    headers = {'Content-Disposition': 'attachment; filename="resultados_manual_prisma.csv"'}
    return Response(content=csv_bytes, media_type="text/csv; charset=utf-8", headers=headers)

@app.get("/admin/export/ai")
async def export_csv_ai(
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    responses = db.query(models.AIEvaluationResponse).order_by(models.AIEvaluationResponse.id.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["ID", "Fecha", "Nombre", "Correo", "Tiempo (minutos)", "Q1: Esfuerzo Deduplicacion", "Q2: Confianza Deduplicacion", "Q3: Fatiga Screening", "Q4: Confianza Screening", "Q5: Tiempo Sintesis", "Q6: Reproducibilidad", "Q7: Viabilidad", "Q8: Mayor Impacto", "Q9: Alucinaciones"])
    for r in responses:
        writer.writerow([r.id, r.created_at.strftime('%Y-%m-%d %H:%M'), r.name, r.email, r.time_minutes, r.q1_ai_dedup_effort, r.q2_ai_dedup_trust, r.q3_ai_screening_fatigue, r.q4_ai_screening_trust, r.q5_ai_synthesis_time, r.q6_ai_reproducibility, r.q7_ai_viability, r.q8_ai_best_feature, r.q9_ai_hallucinations])
    csv_bytes = "\ufeff" + output.getvalue()
    headers = {'Content-Disposition': 'attachment; filename="resultados_ia_prisma.csv"'}
    return Response(content=csv_bytes, media_type="text/csv; charset=utf-8", headers=headers)
