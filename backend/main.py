
from pathlib import Path
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pypdf import PdfReader
import ollama

# MARK: - Configuration

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# MARK: - Document Storage

uploaded_document_text = ""
uploaded_document_name = ""


# MARK: - Models

class ChatRequest(BaseModel):
    message: str


# MARK: - Routes

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# MARK: - Chat

@app.post("/chat")
def chat(request: ChatRequest):

    if not uploaded_document_text:
        system_prompt = """
        You are AssistAI, a helpful customer support assistant
        for a school.

        Be friendly, clear, and professional.
        Never invent school policies, fees, schedules, or requirements.

        No school document has been uploaded yet.
        Do not pretend to know specific school information.
        """
    else:
        system_prompt = f"""
        You are AssistAI, a helpful school document assistant.

        Answer the user's questions using the uploaded document below.

        Rules:
        - Use the document as your primary source.
        - Do not invent information.
        - If the answer is not in the document, say so.
        - Keep answers simple and easy to understand.
        - Mention the page number when possible.

        Document name: {uploaded_document_name}

        DOCUMENT CONTENT:
        {uploaded_document_text}
        """

    response = ollama.chat(
        model="llama3.2:1b",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": request.message
            }
        ]
    )

    return {"response": response.message.content}


# MARK: - PDF Upload

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):

    global uploaded_document_text
    global uploaded_document_name

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    filename = Path(file.filename).name
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    try:
        pdf_reader = PdfReader(BytesIO(content))

        extracted_pages = []

        for page_number, page in enumerate(pdf_reader.pages, start=1):
            page_text = page.extract_text() or ""

            extracted_pages.append(
                f"[Page {page_number}]\n{page_text}"
            )

        extracted_text = "\n\n".join(extracted_pages)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text found in this PDF."
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read this PDF file."
        )

    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as uploaded_file:
        uploaded_file.write(content)

    uploaded_document_text = extracted_text[:20000]
    uploaded_document_name = filename

    return {
        "message": "PDF uploaded and processed successfully!",
        "filename": filename,
        "pages": len(pdf_reader.pages),
        "characters_extracted": len(extracted_text)
    }
