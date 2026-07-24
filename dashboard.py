"""
Streamlit Dashboard for the AI Career Agent.

Provides a visual interface for:
    - Application funnel (Applied → Interview → Rejected → Offer)
    - Job matches table with scores
    - Skill gap analysis charts
    - Learning recommendations
    - Resume upload to re-trigger pipeline
    - Status updater (triggers interview prep)
    - Interview prep viewer

Run: streamlit run dashboard.py
"""

import csv
import json
import os
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Page Config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Career Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }

    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        background: linear-gradient(135deg, #e94560, #f5a623);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .main-header p {
        color: #a0aec0;
        margin-top: 0.5rem;
        font-size: 1rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #1e293b, #334155);
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #475569;
        transition: transform 0.2s;
    }

    .metric-card:hover {
        transform: translateY(-2px);
    }

    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #e94560;
    }

    .metric-label {
        font-size: 0.9rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.5rem;
    }

    .status-applied { color: #3b82f6; }
    .status-interview { color: #f59e0b; }
    .status-rejected { color: #ef4444; }
    .status-offer { color: #10b981; }

    .skill-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        margin: 2px;
        font-weight: 500;
    }

    .skill-matched {
        background: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 1px solid #10b981;
    }

    .skill-missing {
        background: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid #ef4444;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b, #334155);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #475569;
    }
</style>
""", unsafe_allow_html=True)

# ─── Constants ─────────────────────────────────────────────────────
APPLICATIONS_CSV = "database/applications.csv"
RESUME_JSON_PATH = "resumes/resume.json"
REPORTS_DIR = "reports"
GENERATED_DIR = "resumes/generated"
COVER_LETTERS_DIR = "cover_letters"
HISTORY_DIR = "database/history"


# ─── Helper Functions ──────────────────────────────────────────────
def load_applications():
    """Load applications.csv into a DataFrame."""
    if not os.path.exists(APPLICATIONS_CSV):
        return pd.DataFrame(columns=["Company", "Role", "Match", "Applied", "Status", "Resume", "CoverLetter"])
    try:
        df = pd.read_csv(APPLICATIONS_CSV)
        if df.empty:
            return pd.DataFrame(columns=["Company", "Role", "Match", "Applied", "Status", "Resume", "CoverLetter"])
        return df
    except Exception:
        return pd.DataFrame(columns=["Company", "Role", "Match", "Applied", "Status", "Resume", "CoverLetter"])


def load_learning_report():
    """Load the latest learning report."""
    path = os.path.join(REPORTS_DIR, "learning_report.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_interview_prep(company: str):
    """Load interview prep for a specific company."""
    import re
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", company)
    path = os.path.join(REPORTS_DIR, f"{safe}_interview_prep.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_digest():
    """Load the latest digest text."""
    path = os.path.join(REPORTS_DIR, "latest_digest.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_resume_json():
    """Load the structured resume data."""
    if os.path.exists(RESUME_JSON_PATH):
        with open(RESUME_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ─── Header ────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🎯 AI Career Agent</h1>
    <p>Multi-Agent Job Search Automation — Discover, Match, Apply, Prepare</p>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Controls")

    st.markdown("---")

    # Pipeline trigger
    st.markdown("### 🚀 Run Pipeline")
    resume_path = st.text_input("Resume Path", value="resumes/master_resume.pdf")
    threshold = st.slider("Match Threshold", 0, 100, 70, 5)

    if st.button("▶️ Run Full Pipeline", type="primary", use_container_width=True):
        with st.spinner("Running pipeline... This may take a few minutes."):
            try:
                from graph_flow.graph import build_graph
                graph = build_graph()
                result = graph.invoke({
                    "resume_path": resume_path,
                    "match_threshold": float(threshold),
                    "errors": [],
                })
                st.success(f"✅ Pipeline complete! {len(result.get('qualified_matches', []))} qualified matches found.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Pipeline error: {e}")

    st.markdown("---")

    # Status updater
    st.markdown("### 📝 Update Status")
    df_apps = load_applications()
    if not df_apps.empty:
        companies = df_apps["Company"].unique().tolist()
        selected_company = st.selectbox("Company", companies)
        new_status = st.selectbox("New Status", ["Applied", "Interview", "Rejected", "Offer"])

        if st.button("Update Status", use_container_width=True):
            try:
                from agents.tracker_agent import update_status
                update_status(selected_company, new_status)
                st.success(f"Updated {selected_company} → {new_status}")

                if new_status == "Interview":
                    st.info("🎓 Generating interview prep...")
                    try:
                        from graph_flow.graph import build_interview_graph
                        igraph = build_interview_graph()
                        result = igraph.invoke({
                            "interview_company": selected_company,
                            "errors": [],
                        })
                        if result.get("interview_questions"):
                            st.success("Interview prep generated! Check the Interview Prep tab.")
                        else:
                            st.warning(f"Interview prep issues: {result.get('errors', [])}")
                    except Exception as e:
                        st.warning(f"Could not generate interview prep: {e}")

                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.info("No applications yet. Run the pipeline first.")

    st.markdown("---")
    st.markdown(f"*Last updated: {date.today().strftime('%B %d, %Y')}*")

# ─── Main Content ──────────────────────────────────────────────────
df = load_applications()
learning_report = load_learning_report()
resume_data = load_resume_json()

# ─── Tabs ──────────────────────────────────────────────────────────
tab_dashboard, tab_matches, tab_skills, tab_learning, tab_interview, tab_resume, tab_digest = st.tabs([
    "📊 Dashboard", "🎯 Matches", "📈 Skills Analysis",
    "📚 Learning", "🎓 Interview Prep", "📄 Resume", "📬 Digest",
])

# ═══════════════════════════════════════════════════════════════════
# TAB 1: Dashboard
# ═══════════════════════════════════════════════════════════════════
with tab_dashboard:
    if df.empty:
        st.info("🚀 No applications yet. Run the pipeline from the sidebar to get started!")
    else:
        # Funnel metrics
        st.markdown("### 📊 Application Funnel")
        col1, col2, col3, col4 = st.columns(4)

        total = len(df)
        interviews = len(df[df["Status"] == "Interview"]) if "Status" in df.columns else 0
        rejected = len(df[df["Status"] == "Rejected"]) if "Status" in df.columns else 0
        offers = len(df[df["Status"] == "Offer"]) if "Status" in df.columns else 0

        with col1:
            st.metric("📨 Applied", total)
        with col2:
            st.metric("🗣️ Interview", interviews)
        with col3:
            st.metric("❌ Rejected", rejected)
        with col4:
            st.metric("🎉 Offers", offers)

        st.markdown("---")

        # Charts row
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("#### Status Distribution")
            if "Status" in df.columns:
                status_counts = df["Status"].value_counts()
                colors = {
                    "Applied": "#3b82f6",
                    "Interview": "#f59e0b",
                    "Rejected": "#ef4444",
                    "Offer": "#10b981",
                }
                fig = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color=status_counts.index,
                    color_discrete_map=colors,
                    hole=0.4,
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0",
                    showlegend=True,
                    height=350,
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            st.markdown("#### Match Score Distribution")
            if "Match" in df.columns:
                # Parse match scores
                match_scores = df["Match"].apply(
                    lambda x: float(str(x).replace("%", "")) if pd.notna(x) else 0
                )
                fig = px.histogram(
                    x=match_scores,
                    nbins=10,
                    labels={"x": "Match Score (%)", "count": "Jobs"},
                    color_discrete_sequence=["#e94560"],
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e2e8f0",
                    xaxis_title="Match Score (%)",
                    yaxis_title="Number of Jobs",
                    height=350,
                )
                st.plotly_chart(fig, use_container_width=True)

        # Application timeline
        if "Applied" in df.columns:
            st.markdown("#### 📅 Application Timeline")
            try:
                df_timeline = df.copy()
                df_timeline["Applied"] = pd.to_datetime(df_timeline["Applied"], errors="coerce")
                df_timeline = df_timeline.dropna(subset=["Applied"])
                if not df_timeline.empty:
                    daily = df_timeline.groupby(df_timeline["Applied"].dt.date).size().reset_index()
                    daily.columns = ["Date", "Applications"]
                    fig = px.bar(
                        daily, x="Date", y="Applications",
                        color_discrete_sequence=["#e94560"],
                    )
                    fig.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#e2e8f0",
                        height=300,
                    )
                    st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

# ═══════════════════════════════════════════════════════════════════
# TAB 2: Matches
# ═══════════════════════════════════════════════════════════════════
with tab_matches:
    if df.empty:
        st.info("No matches yet. Run the pipeline first.")
    else:
        st.markdown("### 🎯 Job Matches")

        # Sort by match score
        df_display = df.copy()
        if "Match" in df_display.columns:
            df_display["Score"] = df_display["Match"].apply(
                lambda x: float(str(x).replace("%", "")) if pd.notna(x) else 0
            )
            df_display = df_display.sort_values("Score", ascending=False)

        # Color-coded table
        for _, row in df_display.iterrows():
            score = float(str(row.get("Match", "0")).replace("%", ""))
            if score >= 90:
                color = "#10b981"
                emoji = "🟢"
            elif score >= 80:
                color = "#f59e0b"
                emoji = "🟡"
            elif score >= 70:
                color = "#f97316"
                emoji = "🟠"
            else:
                color = "#ef4444"
                emoji = "🔴"

            status = row.get("Status", "Applied")
            status_colors = {
                "Applied": "#3b82f6",
                "Interview": "#f59e0b",
                "Rejected": "#ef4444",
                "Offer": "#10b981",
            }

            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.markdown(f"**{row.get('Company', 'N/A')}**")
                    st.caption(row.get("Role", "N/A"))
                with col2:
                    st.markdown(f"Applied: {row.get('Applied', 'N/A')}")
                with col3:
                    st.markdown(f"{emoji} **{row.get('Match', 'N/A')}**")
                with col4:
                    st.markdown(f":{status_colors.get(status, '#666')}[**{status}**]")
                st.divider()

# ═══════════════════════════════════════════════════════════════════
# TAB 3: Skills Analysis
# ═══════════════════════════════════════════════════════════════════
with tab_skills:
    st.markdown("### 📈 Skill Gap Analysis")

    if learning_report and learning_report.get("recommendations"):
        recs = learning_report["recommendations"]

        # Missing skills bar chart
        skills = [r["skill"] for r in recs[:10]]
        counts = [r["requested_by"] for r in recs[:10]]
        priorities = [r["priority"] for r in recs[:10]]

        colors = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}
        bar_colors = [colors.get(p, "#666") for p in priorities]

        fig = go.Figure(go.Bar(
            x=counts,
            y=skills,
            orientation="h",
            marker_color=bar_colors,
            text=[f"{c} companies" for c in counts],
            textposition="auto",
        ))
        fig.update_layout(
            title="Most Requested Missing Skills",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0",
            yaxis=dict(autorange="reversed"),
            height=400,
            xaxis_title="Number of Companies Requesting",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Category breakdown
        cat_summary = learning_report.get("category_summary", {})
        if cat_summary:
            st.markdown("#### Skill Gap by Category")
            fig = px.pie(
                values=list(cat_summary.values()),
                names=list(cat_summary.keys()),
                color_discrete_sequence=px.colors.qualitative.Set2,
                hole=0.3,
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e2e8f0",
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run the pipeline to generate skill gap analysis.")

    # Resume skills display
    if resume_data and resume_data.get("skills"):
        st.markdown("#### Your Skills")
        skills_html = ""
        for skill in resume_data.get("skills", []):
            skills_html += f'<span class="skill-badge skill-matched">{skill}</span> '
        st.markdown(skills_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# TAB 4: Learning
# ═══════════════════════════════════════════════════════════════════
with tab_learning:
    st.markdown("### 📚 Learning Recommendations")

    if learning_report and learning_report.get("recommendations"):
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Skill Gaps", learning_report.get("total_skill_gaps", 0))
        with col2:
            st.metric("Top 5 Est. Days", learning_report.get("estimated_total_learning_days", 0))
        with col3:
            st.metric("Jobs Analyzed", learning_report.get("total_jobs_analyzed", 0))

        st.markdown("---")

        # Detailed recommendations
        for i, rec in enumerate(learning_report["recommendations"], 1):
            priority_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(rec["priority"], "⚪")

            with st.expander(
                f"{priority_emoji} {rec['skill']} — "
                f"{rec['requested_by']} companies ({rec['demand_percentage']}%) — "
                f"~{rec['estimated_days']} days",
                expanded=(i <= 3),
            ):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Priority", rec["priority"])
                with col2:
                    st.metric("Companies", rec["requested_by"])
                with col3:
                    st.metric("Demand %", f"{rec['demand_percentage']}%")
                with col4:
                    st.metric("Est. Days", rec["estimated_days"])

                st.caption(f"Category: {rec['category']}")

                # Learning time visualization
                progress = min(1.0, rec["estimated_days"] / 14)
                st.progress(progress, text=f"Estimated {rec['estimated_days']} days to learn")
    else:
        st.info("No learning recommendations yet. Run the pipeline to analyze skill gaps.")

# ═══════════════════════════════════════════════════════════════════
# TAB 5: Interview Prep
# ═══════════════════════════════════════════════════════════════════
with tab_interview:
    st.markdown("### 🎓 Interview Preparation")

    # Find companies with interview status or prep files
    interview_companies = []
    if not df.empty and "Status" in df.columns:
        interview_companies = df[df["Status"] == "Interview"]["Company"].tolist()

    # Also check for any existing prep files
    if os.path.exists(REPORTS_DIR):
        for f in os.listdir(REPORTS_DIR):
            if f.endswith("_interview_prep.json"):
                company = f.replace("_interview_prep.json", "").replace("_", " ")
                if company not in interview_companies:
                    interview_companies.append(company)

    if interview_companies:
        selected = st.selectbox("Select Company", interview_companies)
        if selected:
            prep = load_interview_prep(selected)
            if prep:
                section_config = {
                    "language_specific": ("🔧 Language & Framework", "#3b82f6"),
                    "dsa": ("📊 DSA", "#8b5cf6"),
                    "system_design": ("🏗️ System Design", "#f59e0b"),
                    "behavioral": ("🗣️ Behavioral", "#10b981"),
                    "coding_problems": ("💻 Coding Problems", "#ef4444"),
                }

                for key, (title, color) in section_config.items():
                    questions = prep.get(key, [])
                    if questions:
                        st.markdown(f"#### {title}")
                        for i, q in enumerate(questions, 1):
                            if isinstance(q, dict):
                                question = q.get("question", q.get("title", str(q)))
                                hint = q.get("hint", q.get("approach", ""))
                                with st.expander(f"Q{i}: {question}"):
                                    if hint:
                                        st.info(f"💡 **Hint:** {hint}")
                            else:
                                with st.expander(f"Q{i}: {q}"):
                                    st.write("No hint available.")
                        st.markdown("")
            else:
                st.warning(
                    f"No interview prep found for {selected}. "
                    "Update their status to 'Interview' to generate prep."
                )
    else:
        st.info(
            "No companies in interview stage. When a company responds, "
            "update their status to 'Interview' in the sidebar."
        )

    # Manual interview prep trigger
    st.markdown("---")
    st.markdown("#### Generate Interview Prep Manually")
    manual_company = st.text_input("Company Name")
    if st.button("🎓 Generate Prep") and manual_company:
        with st.spinner(f"Generating interview prep for {manual_company}..."):
            try:
                from graph_flow.graph import build_interview_graph
                igraph = build_interview_graph()
                result = igraph.invoke({
                    "interview_company": manual_company,
                    "errors": [],
                })
                if result.get("interview_questions"):
                    st.success("✅ Interview prep generated! Refresh the page to view.")
                    st.rerun()
                else:
                    st.error(f"Issues: {result.get('errors', [])}")
            except Exception as e:
                st.error(f"Error: {e}")

# ═══════════════════════════════════════════════════════════════════
# TAB 6: Resume
# ═══════════════════════════════════════════════════════════════════
with tab_resume:
    st.markdown("### 📄 Resume Data")

    if resume_data and resume_data.get("personal_info", {}).get("name"):
        info = resume_data.get("personal_info", {})

        # Personal info card
        st.markdown(f"#### {info.get('name', 'N/A')}")
        contact_parts = [
            info.get("email", ""),
            info.get("phone", ""),
            info.get("location", ""),
        ]
        st.caption(" | ".join(p for p in contact_parts if p))

        if info.get("linkedin"):
            st.markdown(f"🔗 [LinkedIn]({info['linkedin']})")
        if info.get("github"):
            st.markdown(f"💻 [GitHub]({info['github']})")

        st.markdown("---")

        # Skills
        skills = resume_data.get("skills", [])
        if skills:
            st.markdown("#### 🛠️ Skills")
            skills_html = ""
            for skill in skills:
                skills_html += f'<span class="skill-badge skill-matched">{skill}</span> '
            st.markdown(skills_html, unsafe_allow_html=True)
            st.markdown("")

        # Experience
        experience = resume_data.get("experience", [])
        if experience:
            st.markdown("#### 💼 Experience")
            for exp in experience:
                if exp.get("title") or exp.get("company"):
                    with st.expander(
                        f"**{exp.get('title', '')}** at {exp.get('company', '')} "
                        f"({exp.get('start_date', '')} - {exp.get('end_date', '')})"
                    ):
                        for bullet in exp.get("bullets", []):
                            st.markdown(f"• {bullet}")

        # Projects
        projects = resume_data.get("projects", [])
        if projects:
            st.markdown("#### 🚀 Projects")
            for proj in projects:
                if proj.get("name"):
                    with st.expander(f"**{proj.get('name', '')}**"):
                        st.write(proj.get("description", ""))
                        if proj.get("skills"):
                            st.caption(f"Skills: {', '.join(proj['skills'])}")
                        for bullet in proj.get("bullets", []):
                            st.markdown(f"• {bullet}")

        # Education
        education = resume_data.get("education", [])
        if education:
            st.markdown("#### 🎓 Education")
            for edu in education:
                if edu.get("institution"):
                    st.write(
                        f"**{edu.get('degree', '')}**, {edu.get('institution', '')} "
                        f"({edu.get('start_date', '')} - {edu.get('end_date', '')})"
                    )
    else:
        st.info(
            "No resume data loaded. Place your resume PDF at "
            "`resumes/master_resume.pdf` and run the pipeline."
        )

    # Upload section
    st.markdown("---")
    st.markdown("#### 📤 Upload New Resume")
    uploaded = st.file_uploader("Upload PDF Resume", type=["pdf"])
    if uploaded:
        save_path = "resumes/master_resume.pdf"
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.success(f"Resume saved to {save_path}. Run the pipeline to process it.")

# ═══════════════════════════════════════════════════════════════════
# TAB 7: Digest
# ═══════════════════════════════════════════════════════════════════
with tab_digest:
    st.markdown("### 📬 Latest Digest")

    digest_text = load_digest()
    if digest_text:
        st.code(digest_text, language=None)
    else:
        st.info("No digest available. Run the pipeline to generate one.")

    # Show generated files
    st.markdown("---")
    st.markdown("#### 📁 Generated Files")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Tailored Resumes**")
        if os.path.exists(GENERATED_DIR):
            pdfs = [f for f in os.listdir(GENERATED_DIR) if f.endswith(".pdf")]
            if pdfs:
                for pdf in pdfs:
                    st.write(f"📄 {pdf}")
            else:
                st.caption("None yet")
        else:
            st.caption("None yet")

    with col2:
        st.markdown("**Cover Letters**")
        if os.path.exists(COVER_LETTERS_DIR):
            docs = [f for f in os.listdir(COVER_LETTERS_DIR) if f.endswith(".docx")]
            if docs:
                for doc in docs:
                    st.write(f"📝 {doc}")
            else:
                st.caption("None yet")
        else:
            st.caption("None yet")

# ─── Footer ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #64748b; padding: 1rem;'>"
    "🤖 AI Career Agent — Built with LangGraph, Groq, FAISS, and Streamlit"
    "</div>",
    unsafe_allow_html=True,
)
