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
    raise RuntimeError("CREDENTIAL ERROR: ADMIN_USER o ADMIN_PASSWORD no están configurados en el .env")
if not TARGET_EMAIL:
    raise RuntimeError("EMAIL ERROR: TARGET_EMAIL no está configurado en el .env")


# Init DB
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Evaluación PRISMA", version="1.0.0")
security = HTTPBasic()

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency DB
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth Dependency
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USER)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Email Task
def send_notification_email(response_id: int, name: str, email: str, response_data: dict):
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("Atención: Credenciales SMTP no configuradas. Correo no enviado.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = TARGET_EMAIL
        msg["Subject"] = f"Nueva Evaluación PRISMA de: {name}"

        body = f"""
        <html>
          <body>
            <h2>Nueva respuesta en el formulario de Evaluación PRISMA</h2>
            <p><strong>ID:</strong> {response_id}</p>
            <p><strong>Nombre:</strong> {name}</p>
            <p><strong>Correo del participante:</strong> {email}</p>
            <hr>
            <h3>Detalles de la encuesta:</h3>
            <ul>
              <li><strong>Tiempo (minutos):</strong> {response_data.get('time_minutes')}</li>
              <li><strong>q1_filters:</strong> {response_data.get('q1_filters')}</li>
              <li><strong>q2_export:</strong> {response_data.get('q2_export')}</li>
              <li><strong>q3_dedup_visual:</strong> {response_data.get('q3_dedup_visual')}</li>
              <li><strong>q4_dedup_error:</strong> {response_data.get('q4_dedup_error')}</li>
              <li><strong>q5_screen_fatigue:</strong> {response_data.get('q5_screen_fatigue')}</li>
              <li><strong>q6_screen_fear:</strong> {response_data.get('q6_screen_fear')}</li>
              <li><strong>q7_synthesis_slow:</strong> {response_data.get('q7_synthesis_slow')}</li>
              <li><strong>q8_reproducibility:</strong> {response_data.get('q8_reproducibility')}</li>
            </ul>
            <p><strong>Comentario Cualitativo:</strong></p>
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
        print(f"Correo de notificación enviado exitosamente a {TARGET_EMAIL}")
    except Exception as e:
        print(f"Error enviando correo: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/submit", response_class=HTMLResponse)
async def submit_form(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    time_minutes: int = Form(...),
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
    # Crear response en BD
    new_response = models.EvaluationResponse(
        name=name,
        email=email,
        time_minutes=time_minutes,
        q1_filters=q1_filters,
        q2_export=q2_export,
        q3_dedup_visual=q3_dedup_visual,
        q4_dedup_error=q4_dedup_error,
        q5_screen_fatigue=q5_screen_fatigue,
        q6_screen_fear=q6_screen_fear,
        q7_synthesis_slow=q7_synthesis_slow,
        q8_reproducibility=q8_reproducibility,
        q9_bottleneck=q9_bottleneck
    )
    db.add(new_response)
    db.commit()
    db.refresh(new_response)

    # Dictionary for email
    response_data = {
        "time_minutes": time_minutes,
        "q1_filters": q1_filters,
        "q2_export": q2_export,
        "q3_dedup_visual": q3_dedup_visual,
        "q4_dedup_error": q4_dedup_error,
        "q5_screen_fatigue": q5_screen_fatigue,
        "q6_screen_fear": q6_screen_fear,
        "q7_synthesis_slow": q7_synthesis_slow,
        "q8_reproducibility": q8_reproducibility,
        "q9_bottleneck": q9_bottleneck
    }

    # Enviar correo en background
    background_tasks.add_task(send_notification_email, new_response.id, name, email, response_data)

    return templates.TemplateResponse(request=request, name="success.html", context={"name": name})

@app.get("/admin", response_class=HTMLResponse)
async def view_admin(
    request: Request, 
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    responses = db.query(models.EvaluationResponse).order_by(models.EvaluationResponse.id.desc()).all()
    return templates.TemplateResponse(request=request, name="admin.html", context={"responses": responses})

@app.post("/admin/delete/{response_id}")
async def delete_response(
    response_id: int,
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    resp = db.query(models.EvaluationResponse).filter(models.EvaluationResponse.id == response_id).first()
    if resp:
        db.delete(resp)
        db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.get("/admin/export")
async def export_csv(
    username: str = Depends(get_current_username),
    db: Session = Depends(get_db)
):
    responses = db.query(models.EvaluationResponse).order_by(models.EvaluationResponse.id.asc()).all()
    
    output = io.StringIO()
    # Usar dialecto excel y utf-8-sig (para tildes en excel)
    # Fastapi encodea a utf-8 por defecto, así que devolvemos string pero con encode byte utf-8 con BOM
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow([
        "ID", "Fecha", "Nombre", "Correo", "Tiempo (minutos)", 
        "Q1: Busqueda y Filtros", 
        "Q2: Exportar y Consolidar", 
        "Q3: Deduplicacion Visual", 
        "Q4: Inseguridad Excel", 
        "Q5: Fatiga de Screening", 
        "Q6: Miedo de Descartar", 
        "Q7: Síntesis y Matriz", 
        "Q8: Reproducibilidad", 
        "Q9: Cuello de Botella (Opinión)"
    ])
    
    for resp in responses:
        writer.writerow([
            resp.id, 
            resp.created_at.strftime('%Y-%m-%d %H:%M'),
            resp.name,
            resp.email,
            resp.time_minutes,
            resp.q1_filters,
            resp.q2_export,
            resp.q3_dedup_visual,
            resp.q4_dedup_error,
            resp.q5_screen_fatigue,
            resp.q6_screen_fear,
            resp.q7_synthesis_slow,
            resp.q8_reproducibility,
            resp.q9_bottleneck
        ])
    
    # BOM (Byte Order Mark) helps Excel open utf-8 automatically
    csv_bytes = "\ufeff" + output.getvalue()
    
    headers = {
        'Content-Disposition': 'attachment; filename="resultados_evaluacion_prisma.csv"'
    }
    
    return Response(content=csv_bytes, media_type="text/csv; charset=utf-8", headers=headers)

