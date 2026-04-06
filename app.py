import os
import traceback
import asyncio
from quart import Quart, request, jsonify, render_template
from quart_cors import cors
from data_fetcher import generate_context_parallel, context_to_text, forward_geocode
from agent import OllamaAgent
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

app = Quart(__name__)
app = cors(app, allow_origin="*")
rag_chain = None
current_site_text = ""

# we load ai models here just once when server starts
print("Initializing Embeddings & LLM...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
llm = ChatOllama(model="gemma3:4b", temperature=0.15)

prompt = ChatPromptTemplate.from_template("""You are BhoomiAI Developed by FringeLabs, an expert industrial site analysis and location intelligence assistant for India.

Use the site data below to answer the question. Focus on:
- Infrastructure readiness for industrial use
- Environmental constraints
- Demographic and workforce context
- Economic and regulatory environment

Site Data:
{context}

Question:
{question}

Provide a precise, data-backed answer.
always mention your name while answering queries.
also be specific yes or no, by weighing all the aspects!""")


def _llm_invoke(text: str) -> str:
    """
    call ai model here
    this is safe to run in background thread so server does not block
    """
    return llm.invoke(text).content


def build_rag_chain(text_context: str) -> None:
    """
    takes scraped text and makes search database
    we use faiss for fast searching of context
    """
    global rag_chain, current_site_text
    current_site_text = text_context
    docs = [Document(page_content=text_context)]
    vectorstore = FAISS.from_documents(docs, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )



@app.route("/")
async def index():
    return await render_template("index.html")




@app.route("/api/analyze_location", methods=["POST"])
async def analyze_location():
    try:
        data = await request.json
        if not data:
            return jsonify({"error": "No JSON body provided."}), 400

        lat = data.get("lat")
        lon = data.get("lon")
        query = data.get("query", "").strip()

        # if user gave name instead of coordinates, find lat lon here
        if (lat is None or lon is None) and query:
            print(f"[APP] Forward geocoding: {query}")
            lat, lon = await forward_geocode(query)
            if lat is None or lon is None:
                return jsonify({"error": f"Could not geocode '{query}'. Try a more specific name."}), 400

        if lat is None or lon is None:
            return jsonify({"error": "Provide lat/lon coordinates or a location name."}), 400

        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid coordinates — must be numbers."}), 400

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return jsonify({"error": "Coordinates out of range."}), 400

        print(f"[APP] Analyzing {lat}, {lon}...")

        context = await generate_context_parallel(lat, lon, llm_fn=_llm_invoke)
        text_format = context_to_text(context)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, build_rag_chain, text_format)

        print(f"[APP] Done. Context text length: {len(text_format)} chars")

        return jsonify({
            "status": "success",
            "context": context,
            "text_summary": text_format,
        })

    except Exception as e:
        print(f"[APP] /analyze_location error:\n{traceback.format_exc()}")
        return jsonify({"error": f"Analysis engine error: {type(e).__name__}: {e}"}), 500


@app.route("/api/chat", methods=["POST"])
async def chat():
    global rag_chain
    if not rag_chain:
        return jsonify({"error": "No site analysed yet. Please analyse a location first."}), 400

    try:
        data = await request.json
        if not data:
            return jsonify({"error": "No JSON body."}), 400
        question = (data.get("question") or "").strip()
        if not question:
            return jsonify({"error": "Question is required."}), 400

        print(f"[APP] Chat: {question}")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, rag_chain.invoke, question)
        return jsonify({"response": result})

    except Exception as e:
        print(f"[APP] /chat error:\n{traceback.format_exc()}")
        return jsonify({"error": f"Chat error: {type(e).__name__}: {e}"}), 500


# agent endpoint — uses qwen3:8b with tool calling
agent_instance = OllamaAgent()

@app.route("/api/agent", methods=["POST"])
async def agent_chat():
    """Agentic AI endpoint that uses tool-calling to answer queries."""
    try:
        data = await request.json
        if not data:
            return jsonify({"error": "No JSON body."}), 400

        query = (data.get("query") or "").strip()
        if not query:
            return jsonify({"error": "Query is required."}), 400

        location_context = {}
        if data.get("location"):
            location_context["location"] = data["location"]
        if data.get("coordinates"):
            coords = data["coordinates"]
            location_context["lat"] = coords.get("lat")
            location_context["lon"] = coords.get("lon")

        print(f"[APP] Agent query: {query}")
        result = await agent_instance.run(query, location_context)
        return jsonify(result)

    except Exception as e:
        print(f"[APP] /agent error:\n{traceback.format_exc()}")
        return jsonify({"error": f"Agent error: {type(e).__name__}: {e}"}), 500


@app.route("/api/agent/health", methods=["GET"])
async def agent_health():
    """Ping Ollama and report model availability without running full agent."""
    try:
        status = await agent_instance.ping()
        return jsonify(status)
    except Exception as e:
        return jsonify({"ollama": "unreachable", "error": str(e)}), 503


@app.route("/api/health", methods=["GET"])
async def health():
    return jsonify({
        "status": "ok",
        "model": "gemma3:4b",
        "rag_ready": rag_chain is not None,
    })


if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)
