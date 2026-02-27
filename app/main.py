import tempfile
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import Base, engine, get_db
from .models import Product
from .parse_docx import parse_docx
from .openai_client import generate_description
from .qa import qa_check
from .export_utils import export_csv, export_xlsx

Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

LOCK_TTL_MIN = 30

def current_user(request: Request) -> str:
    # MVP: User via Header (später SSO/Login)
    return request.headers.get("X-User", "unknown@local")

@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db), status: str = "pending", q: str = ""):
    stmt = select(Product)
    if status:
        stmt = stmt.where(Product.review_status == status)
    if q:
        stmt = stmt.where((Product.art_nr.ilike(f"%{q}%")) | (Product.name.ilike(f"%{q}%")))
    products = db.execute(stmt.order_by(Product.art_nr)).scalars().all()
    return templates.TemplateResponse("index.html", {"request": request, "products": products, "status": status, "q": q})

@app.post("/upload")
def upload_docx(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Bitte eine .docx Datei hochladen")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(file.file.read())
        path = tmp.name

    items = parse_docx(path)
    for it in items:
        p = db.get(Product, it["art_nr"])
        if not p:
            p = Product(art_nr=it["art_nr"], name=it["name"])
        p.name = it["name"]
        p.beschreibung_quelle = it["beschreibung_quelle"]
        p.review_status = "pending"
        p.updated_at = datetime.utcnow()
        db.add(p)

    db.commit()
    return RedirectResponse("/", status_code=303)

def lock_product(db: Session, art_nr: str, user: str):
    p = db.get(Product, art_nr)
    if not p:
        raise HTTPException(404, "Nicht gefunden")

    now = datetime.utcnow()
    expired = p.locked_at and (now - p.locked_at) > timedelta(minutes=LOCK_TTL_MIN)

    if p.locked_by and p.locked_by != user and not expired:
        raise HTTPException(409, f"Gesperrt von {p.locked_by}")

    p.locked_by = user
    p.locked_at = now
    if p.review_status == "pending":
        p.review_status = "in_review"
    db.add(p)
    db.commit()
    return p

@app.get("/p/{art_nr}", response_class=HTMLResponse)
def product_detail(request: Request, art_nr: str, db: Session = Depends(get_db)):
    user = current_user(request)
    p = lock_product(db, art_nr, user)
    return templates.TemplateResponse("product_detail.html", {"request": request, "p": p, "user": user})

@app.post("/p/{art_nr}/save")
def save_product(
    request: Request,
    art_nr: str,
    prompt_ergaenzungen: str = Form(""),
    beschreibung_final: str = Form(""),
    db: Session = Depends(get_db),
):
    user = current_user(request)
    p = db.get(Product, art_nr)
    if not p:
        raise HTTPException(404, "Nicht gefunden")
    if p.locked_by and p.locked_by != user:
        raise HTTPException(409, f"Gesperrt von {p.locked_by}")

    p.prompt_ergaenzungen = prompt_ergaenzungen
    p.beschreibung_final = beschreibung_final
    p.updated_by = user
    p.updated_at = datetime.utcnow()
    db.add(p)
    db.commit()
    return RedirectResponse(f"/p/{art_nr}", status_code=303)

@app.post("/p/{art_nr}/generate")
def generate_for_product(request: Request, art_nr: str, db: Session = Depends(get_db)):
    user = current_user(request)
    p = db.get(Product, art_nr)
    if not p:
        raise HTTPException(404, "Nicht gefunden")
    if p.locked_by and p.locked_by != user:
        raise HTTPException(409, f"Gesperrt von {p.locked_by}")

    text = generate_description(p.name, p.beschreibung_quelle, p.prompt_ergaenzungen)
    ok, note = qa_check(text)

    p.beschreibung_generiert = text
    p.qa_notes = "" if ok else note
    p.updated_by = user
    p.updated_at = datetime.utcnow()
    db.add(p)
    db.commit()
    return RedirectResponse(f"/p/{art_nr}", status_code=303)

@app.post("/p/{art_nr}/approve")
def approve(request: Request, art_nr: str, db: Session = Depends(get_db)):
    user = current_user(request)
    p = db.get(Product, art_nr)
    if not p:
        raise HTTPException(404, "Nicht gefunden")
    if p.locked_by and p.locked_by != user:
        raise HTTPException(409, f"Gesperrt von {p.locked_by}")

    p.review_status = "approved"
    p.updated_by = user
    p.updated_at = datetime.utcnow()
    db.add(p)
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/p/{art_nr}/reject")
def reject(request: Request, art_nr: str, db: Session = Depends(get_db)):
    user = current_user(request)
    p = db.get(Product, art_nr)
    if not p:
        raise HTTPException(404, "Nicht gefunden")
    if p.locked_by and p.locked_by != user:
        raise HTTPException(409, f"Gesperrt von {p.locked_by}")

    p.review_status = "rejected"
    p.updated_by = user
    p.updated_at = datetime.utcnow()
    db.add(p)
    db.commit()
    return RedirectResponse("/", status_code=303)

@app.get("/export.csv")
def export_csv_route(db: Session = Depends(get_db)):
    products = db.execute(
        select(Product).where(Product.review_status == "approved").order_by(Product.art_nr)
    ).scalars().all()

    rows = []
    for p in products:
        beschreibung = (p.beschreibung_final or p.beschreibung_generiert).strip()
        rows.append({"art_nr": p.art_nr, "name": p.name, "beschreibung": beschreibung})

    data = export_csv(rows)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shop_export.csv"},
    )

@app.get("/export.xlsx")
def export_xlsx_route(db: Session = Depends(get_db)):
    products = db.execute(
        select(Product).where(Product.review_status == "approved").order_by(Product.art_nr)
    ).scalars().all()

    rows = []
    for p in products:
        beschreibung = (p.beschreibung_final or p.beschreibung_generiert).strip()
        rows.append({"art_nr": p.art_nr, "name": p.name, "beschreibung": beschreibung})

    data = export_xlsx(rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=shop_export.xlsx"},
    )