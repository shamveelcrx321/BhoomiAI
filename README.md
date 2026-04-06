# BhoomiAI

An AI-powered geospatial analysis platform for infrastructure planning, environmental assessment, and geographic intelligence.

## 🔎Overview

BhoomiAI leverages advanced AI and geospatial technology to provide actionable insights about locations and development opportunities. By combining data from OpenStreetMap, Open-Meteo, Wikipedia, and Census datasets with both Retrieval-Augmented Generation (RAG) and an Agentic AI pipeline, BhoomiAI enables intelligent geographic analysis through an intuitive LLM-based interface.

The platform integrates a tool-based reasoning agent that dynamically fetches and processes real-time geospatial data, allowing more accurate, contextual, and explainable insights for decision-making.

### Key Capabilities

- **Location Analysis** - Explore detailed geographic and infrastructure data for any location  
- **Infrastructure Mapping** - Analyze nearby infrastructure within a 15 km radius  
- **Demographic Insights** - Access population statistics and development metrics  
- **AI-Powered Chatbot** - Ask questions about construction, geography, and development opportunities  
- **Agentic AI Reasoning** - Uses a tool-based AI agent to fetch, analyze, and reason over live geospatial data  
- **Data Aggregation** - Unified access to multiple data sources through a single platform  

---

## 🛠️Tech Stack

| Layer | Technologies |
|-------|--------------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, LangChain, RAG, Agentic AI |
| LLM | Ollama (Local Inference - Qwen, Gemma) |
| Data Sources | OpenStreetMap, Open-Meteo, Wikipedia, Census Data |

---

## 🤖Agentic Architecture

BhoomiAI incorporates an **Agentic AI system** implemented in a dedicated `agent.py` module.

- Uses **tool-based execution** for structured data retrieval  
- Integrates multiple domain-specific tools (climate, infrastructure, demographics)  
- Powered by local LLMs via **Ollama (e.g., Qwen3, Gemma3)**  
- Enables **multi-step reasoning** instead of static responses  
- Provides **context-aware answers** based on real-time location data  

This architecture enhances the system from a traditional RAG pipeline to a more dynamic and intelligent decision-support system.

---

## 🚀Getting Started

### Prerequisites

- Python 3.8 or higher  
- Ollama installed on your system  
- Required Python packages (see requirements.txt)  

### Installation

1. Clone the repository:
```bash
git clone https://github.com/shamveelcrx321/BhoomiAI.git
cd BhoomiAI
```

2. Set up the LLM model:
```bash
ollama run gemma3:4b
```
*Note: You can use a different model (e.g., qwen3:8b) by updating the model name in `agent.py` or `app.py`*

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

5. Open your browser and navigate to:
```
http://localhost:8000
```

---

## 📁Project Structure

```
BhoomiAI/
├── app.py                 
├── agent.py               
├── data_fetcher.py       
├── requirements.txt       
├── static/               
│   ├── css/
│   ├── js/
│   └── index.html
└── README.md
```

---

## 👥Team

BhoomiAI was created by **Team Fringes** - CSE Batch (S2)

### 👑Leadership

**Midhun K M** - Team Lead  

### 👥Team Members

- Abiraj TM  
- Shamveel C  
- Devananda C  
- Sarang K  

---

## 🙏Acknowledgement

The team would like to express special appreciation to **Midhun K M** for leading the project, coordinating the development process, and guiding the team throughout the workshop and hackathon.

---

## 🤝Support

For questions or issues, please reach out to the team lead:  
**Midhun K M**  
midhunkm1294@outlook.com  


