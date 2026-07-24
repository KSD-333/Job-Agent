"""
Generate a sample master_resume.pdf for testing the AI Career Agent pipeline.
Run once: python generate_sample_resume.py
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable


def generate():
    path = "resumes/master_resume.pdf"

    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=styles["Title"], fontSize=20, spaceAfter=2, alignment=TA_LEFT)
    contact_style = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=9, textColor="#333333", spaceAfter=6)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=13, spaceAfter=3)
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=12, bulletIndent=0)
    subheader_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10, leading=13, spaceBefore=4, spaceAfter=2)

    story = []

    # Name
    story.append(Paragraph("Ketan Sharma", name_style))
    story.append(Paragraph(
        "ketan.sharma@email.com | +91-98765-43210 | Bangalore, India | "
        "linkedin.com/in/ketansharma | github.com/ketansharma",
        contact_style,
    ))

    # Skills
    story.append(Paragraph("SKILLS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
    story.append(Paragraph(
        "Java, Kotlin, Android SDK, Jetpack Compose, MVVM, MVP, REST APIs, Retrofit, "
        "Room Database, Firebase, Git, GitHub, CI/CD, Jenkins, Gradle, Unit Testing, "
        "JUnit, Espresso, Dagger/Hilt, Coroutines, RxJava, XML, JSON, SQL, SQLite, "
        "Material Design, Agile, Scrum, JIRA, Python, FastAPI, HTML/CSS, JavaScript",
        body_style,
    ))

    # Experience
    story.append(Paragraph("EXPERIENCE", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))

    story.append(Paragraph("<b>Android Developer</b>, TechCorp Solutions — Jan 2024 - Present", subheader_style))
    for bullet in [
        "Developed and maintained 3 production Android applications using Kotlin and Jetpack Compose serving 500K+ users",
        "Implemented MVVM architecture with Room database and Retrofit for offline-first data synchronization",
        "Reduced app crash rate by 40% through comprehensive unit testing with JUnit and Espresso UI testing",
        "Integrated Firebase Analytics, Crashlytics, and Cloud Messaging for user engagement and monitoring",
        "Built CI/CD pipeline with Jenkins and Gradle reducing release cycle from 2 weeks to 3 days",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    story.append(Paragraph("<b>Junior Android Developer</b>, StartupHub India — Jun 2022 - Dec 2023", subheader_style))
    for bullet in [
        "Built a food delivery app using Java and XML with MVP architecture serving 50K+ daily active users",
        "Integrated Google Maps SDK and location services for real-time delivery tracking",
        "Implemented RESTful API integration using Retrofit with OkHttp interceptors for authentication",
        "Used RxJava for reactive programming patterns to handle asynchronous data streams",
        "Collaborated with cross-functional team of 8 using Agile methodology and JIRA for sprint planning",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    story.append(Paragraph("<b>Software Intern</b>, Digital Innovations Pvt Ltd — Jan 2022 - May 2022", subheader_style))
    for bullet in [
        "Developed a task management Android app using Kotlin with MVVM architecture and Room database",
        "Implemented Material Design components and custom animations for enhanced user experience",
        "Wrote unit tests achieving 75% code coverage using JUnit and Mockito",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    # Projects
    story.append(Paragraph("PROJECTS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))

    story.append(Paragraph("<b>Universal Downloader App</b>", subheader_style))
    for bullet in [
        "Built a multi-platform media downloader app using Kotlin and Jetpack Compose supporting YouTube, Instagram, and Twitter",
        "Implemented background download service with WorkManager and notification progress tracking",
        "Used Dagger/Hilt for dependency injection and Coroutines for asynchronous operations",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    story.append(Paragraph("<b>AI Career Agent</b>", subheader_style))
    for bullet in [
        "Designed a multi-agent system using Python, LangGraph, and Groq LLM for automated job search and application tracking",
        "Implemented RAG pipeline with FAISS vector database and sentence-transformers for resume-to-job matching",
        "Built FastAPI backend and Streamlit dashboard for real-time analytics and pipeline control",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    story.append(Paragraph("<b>E-Commerce Android App</b>", subheader_style))
    for bullet in [
        "Developed a full-featured e-commerce app with product catalog, cart, payment integration using Razorpay SDK",
        "Implemented Firebase Authentication with Google Sign-In and phone number verification",
    ]:
        story.append(Paragraph(f"• {bullet}", bullet_style))

    # Education
    story.append(Paragraph("EDUCATION", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
    story.append(Paragraph(
        "Bachelor of Technology in Computer Science, VIT University (2018 - 2022)",
        body_style,
    ))

    # Achievements
    story.append(Paragraph("ACHIEVEMENTS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#666666", spaceAfter=4))
    for ach in [
        "Winner, Google Android Developer Challenge 2023 — Top 10 among 500+ participants",
        "Published 2 apps on Google Play Store with combined 100K+ downloads",
        "Solved 500+ problems on LeetCode with a contest rating of 1850",
        "Certified Google Associate Android Developer",
    ]:
        story.append(Paragraph(f"• {ach}", bullet_style))

    doc = SimpleDocTemplate(
        path, pagesize=letter,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    doc.build(story)
    print(f"Sample resume generated: {path}")


if __name__ == "__main__":
    generate()
