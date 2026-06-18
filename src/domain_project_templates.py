from typing import Dict, List


def get_domain_project_templates(domain: str, user_query: str) -> List[Dict]:
    templates = {
        "frontend": get_frontend_templates(user_query),
        "backend": get_backend_templates(user_query),
        "ai_ml": get_ai_ml_templates(user_query),
        "data": get_data_templates(user_query),
        "security": get_security_templates(user_query),
        "healthcare": get_healthcare_templates(user_query),
        "blockchain": get_blockchain_templates(user_query),
        "education": get_education_templates(user_query),
        "general": get_general_templates(user_query)
    }

    return templates.get(domain, templates["general"])


def get_frontend_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "AI-Powered Frontend Project Generator",
            "mvp_scope": [
                "Build a React dashboard where users enter frontend project goals.",
                "Generate project ideas based on skill level, target role, and available build time.",
                "Suggest UI pages, reusable components, state management approach, and deployment plan.",
                "Show frontend project difficulty, resume value, and GitHub-readiness score."
            ],
            "advanced_extensions": [
                "Generate wireframe suggestions for each project idea.",
                "Recommend reusable UI component patterns.",
                "Add performance and accessibility checklist generation.",
                "Export project plans as README-ready markdown."
            ],
            "tech_stack": [
                "React",
                "TypeScript",
                "Tailwind CSS",
                "Vite",
                "FastAPI",
                "PostgreSQL",
                "Streamlit"
            ],
            "target_roles": [
                "Frontend Engineer",
                "Full-Stack Engineer",
                "UI Engineer",
                "Developer Tools Engineer"
            ]
        },
        {
            "project_title": "Reusable Component Discovery Dashboard",
            "mvp_scope": [
                "Build a dashboard that helps developers discover reusable UI components.",
                "Allow users to search by component type, design pattern, or project goal.",
                "Recommend components for dashboards, forms, landing pages, and admin panels.",
                "Show usage examples, complexity, and project-fit score."
            ],
            "advanced_extensions": [
                "Add semantic search over component descriptions.",
                "Generate component documentation automatically.",
                "Suggest component combinations for complete project screens.",
                "Add design-system compatibility scoring."
            ],
            "tech_stack": [
                "React",
                "TypeScript",
                "Tailwind CSS",
                "Sentence Transformers",
                "FAISS",
                "FastAPI"
            ],
            "target_roles": [
                "Frontend Engineer",
                "Full-Stack Engineer",
                "Design Systems Engineer",
                "Developer Tools Engineer"
            ]
        },
        {
            "project_title": "Frontend Performance and UX Intelligence Platform",
            "mvp_scope": [
                "Build a tool that analyzes frontend project ideas and suggests performance-focused improvements.",
                "Track frontend concerns such as loading speed, accessibility, responsiveness, and component complexity.",
                "Generate an MVP roadmap for improving UI quality.",
                "Show role-specific skills demonstrated by the project."
            ],
            "advanced_extensions": [
                "Add Lighthouse-style scoring.",
                "Suggest accessibility fixes and UI testing strategies.",
                "Generate deployment and monitoring checklist.",
                "Add frontend architecture comparison between simple and advanced versions."
            ],
            "tech_stack": [
                "React",
                "TypeScript",
                "Tailwind CSS",
                "FastAPI",
                "Playwright",
                "PostgreSQL"
            ],
            "target_roles": [
                "Frontend Engineer",
                "UI Engineer",
                "Full-Stack Engineer",
                "Web Performance Engineer"
            ]
        }
    ]


def get_backend_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Backend API Project Intelligence Platform",
            "mvp_scope": [
                "Build an API-driven system that recommends backend project ideas.",
                "Generate database schema, API routes, authentication plan, and deployment strategy.",
                "Score each idea by scalability, complexity, and resume value.",
                "Export backend implementation roadmap."
            ],
            "advanced_extensions": [
                "Add architecture diagrams for microservices and monolith options.",
                "Generate OpenAPI documentation.",
                "Add load testing and observability recommendations.",
                "Support Docker-based deployment templates."
            ],
            "tech_stack": [
                "FastAPI",
                "PostgreSQL",
                "Redis",
                "Docker",
                "SQLAlchemy",
                "AWS"
            ],
            "target_roles": [
                "Backend Engineer",
                "Software Engineer",
                "Platform Engineer",
                "Cloud Engineer"
            ]
        }
    ]


def get_ai_ml_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "AI Research-to-Prototype Idea Engine",
            "mvp_scope": [
                "Retrieve research papers related to the user query.",
                "Extract technical themes and project opportunities.",
                "Generate AI/ML project ideas with MVP scope and target roles.",
                "Score each idea by feasibility and career signal."
            ],
            "advanced_extensions": [
                "Add LLM-based project generation grounded in retrieved papers.",
                "Add hallucination and evidence-grounding checks.",
                "Add model comparison and evaluation metrics.",
                "Generate GitHub README and resume bullets automatically."
            ],
            "tech_stack": [
                "Python",
                "Sentence Transformers",
                "FAISS",
                "CrossEncoder",
                "FastAPI",
                "Streamlit",
                "OpenAI or local LLM"
            ],
            "target_roles": [
                "AI Engineer",
                "ML Engineer",
                "NLP Engineer",
                "Search/Relevance Engineer"
            ]
        }
    ]


def get_data_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Data Analytics Project Recommendation Engine",
            "mvp_scope": [
                "Allow users to enter a data or analytics topic.",
                "Generate project ideas involving datasets, dashboards, and forecasting.",
                "Suggest metrics, charts, and data pipeline steps.",
                "Map each project to data-related roles."
            ],
            "advanced_extensions": [
                "Add automated dataset suggestion.",
                "Generate exploratory data analysis plans.",
                "Add forecasting model recommendations.",
                "Export dashboard wireframes."
            ],
            "tech_stack": [
                "Python",
                "Pandas",
                "Scikit-learn",
                "Plotly",
                "Streamlit",
                "PostgreSQL"
            ],
            "target_roles": [
                "Data Analyst",
                "Data Scientist",
                "Analytics Engineer",
                "Machine Learning Engineer"
            ]
        }
    ]


def get_security_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Cybersecurity Threat Intelligence Dashboard",
            "mvp_scope": [
                "Build a dashboard for detecting and explaining suspicious activity patterns.",
                "Ingest logs or sample security events.",
                "Score threats by severity and anomaly level.",
                "Generate remediation suggestions."
            ],
            "advanced_extensions": [
                "Add anomaly detection models.",
                "Add phishing or malware classification.",
                "Generate security incident summaries.",
                "Add alerting and risk trend visualization."
            ],
            "tech_stack": [
                "Python",
                "Scikit-learn",
                "FastAPI",
                "Streamlit",
                "PostgreSQL",
                "Docker"
            ],
            "target_roles": [
                "Security Engineer",
                "Cybersecurity Analyst",
                "Software Engineer",
                "Detection Engineer"
            ]
        }
    ]


def get_healthcare_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Healthcare AI Decision Support Dashboard",
            "mvp_scope": [
                "Build a dashboard that helps analyze healthcare-related data or documents.",
                "Retrieve relevant medical or clinical research context.",
                "Generate project ideas around patient support, summarization, or risk prediction.",
                "Show feasibility, ethical concerns, and target roles."
            ],
            "advanced_extensions": [
                "Add medical document summarization.",
                "Add risk prediction model suggestions.",
                "Add privacy and compliance checklist.",
                "Add explainability layer for AI predictions."
            ],
            "tech_stack": [
                "Python",
                "Pandas",
                "Scikit-learn",
                "Streamlit",
                "FastAPI",
                "Hugging Face Transformers"
            ],
            "target_roles": [
                "AI Engineer",
                "Healthcare Data Analyst",
                "ML Engineer",
                "Software Engineer"
            ]
        }
    ]


def get_blockchain_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Smart Contract Risk and Project Intelligence Platform",
            "mvp_scope": [
                "Build a platform that recommends blockchain project ideas.",
                "Analyze smart contract use cases and technical risks.",
                "Suggest MVP scope, contract modules, and backend integration plan.",
                "Score each idea by feasibility and security complexity."
            ],
            "advanced_extensions": [
                "Add smart contract vulnerability checklist.",
                "Generate Solidity contract templates.",
                "Add Web3 frontend integration plan.",
                "Add blockchain architecture comparison."
            ],
            "tech_stack": [
                "Solidity",
                "Hardhat",
                "React",
                "FastAPI",
                "PostgreSQL",
                "Web3.py"
            ],
            "target_roles": [
                "Blockchain Engineer",
                "Smart Contract Developer",
                "Full-Stack Engineer",
                "Security Engineer"
            ]
        }
    ]


def get_education_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Adaptive Learning Project Intelligence System",
            "mvp_scope": [
                "Build a platform that recommends learning-focused software projects.",
                "Generate project ideas for tutoring, assessment, and student analytics.",
                "Suggest MVP roadmap and skill outcomes.",
                "Map each idea to education technology roles."
            ],
            "advanced_extensions": [
                "Add personalized learning path generation.",
                "Add student performance prediction.",
                "Generate quiz and feedback modules.",
                "Add teacher dashboard analytics."
            ],
            "tech_stack": [
                "Python",
                "React",
                "FastAPI",
                "PostgreSQL",
                "Scikit-learn",
                "Streamlit"
            ],
            "target_roles": [
                "Software Engineer",
                "EdTech Engineer",
                "Data Analyst",
                "AI Engineer"
            ]
        }
    ]


def get_general_templates(user_query: str) -> List[Dict]:
    return [
        {
            "project_title": "Research-Backed Project Discovery Engine",
            "mvp_scope": [
                "Allow users to enter any technical or research topic.",
                "Retrieve relevant research papers using semantic search.",
                "Generate buildable project ideas with MVP scope and tech stack.",
                "Score each project by feasibility and career relevance."
            ],
            "advanced_extensions": [
                "Add domain detection and query expansion.",
                "Add research theme extraction.",
                "Add LLM-based project generation.",
                "Add dashboard visualizations and JSON export."
            ],
            "tech_stack": [
                "Python",
                "Sentence Transformers",
                "FAISS",
                "FastAPI",
                "Streamlit",
                "PostgreSQL"
            ],
            "target_roles": [
                "Software Engineer",
                "AI Engineer",
                "Backend Engineer",
                "Full-Stack Engineer"
            ]
        }
    ]