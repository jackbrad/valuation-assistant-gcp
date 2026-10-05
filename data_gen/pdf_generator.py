"""PDF Generator for Appraisal AI Demo Documents.

Generates realistic inspection reports, legacy appraisals, and building permits
using ReportLab, including the seeded demo cases for 14 Larkspur and 22 Hilltop.
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def create_inspection_pdf(filepath: Path, property_address: str, doc_id: str, addition_narrative: bool = False,
                          water_damage: bool = False, inspection_date: str = "April 10, 2025"):
    """Generate a realistic 2-page Home Inspection Report.

    water_damage: the "new document arrives" case (18 Larkspur): roof leak, condition C4.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(filepath), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1d6c75'),
        spaceAfter=10
    )
    section_style = ParagraphStyle(
        'DocSection',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1c2a2e'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2c3e50')
    )

    # Header
    story.append(Paragraph("CEDAR HOLLOW PROPERTY INSPECTION SERVICES", title_style))
    story.append(Paragraph(f"<b>Comprehensive Property Condition Assessment</b> | Doc ID: {doc_id}", body_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1d6c75'), spaceAfter=15))

    # Summary table
    data = [
        ["Subject Property:", property_address, "Inspection Date:", inspection_date],
        ["Client:", "Servicing Audit Dept", "Inspector:", "Robert Jenkins, CMI #9842"],
        ["Weather:", "Clear, 68°F", "Property Type:", "Single Family Residence"],
        ["Foundation:", "Poured Concrete (Sound)", "Roof Condition:",
         "Architectural Shingle (End of life)" if water_damage else "Architectural Shingle (Good)"],
    ]
    t = Table(data, colWidths=[110, 160, 110, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f4f6f5')),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#1c2a2e')),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#b4c2c4')),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    story.append(Paragraph("1. Structural & Building Envelope", section_style))
    if water_damage:
        story.append(Paragraph(
            "Exterior siding, masonry, windows, and door seals were inspected. No structural settling observed. "
            "Roof shingles show granule loss and curling across the rear slope, with an active leak at the rear valley. "
            "Estimated remaining useful life 0-2 years; full roof replacement recommended.", body_style
        ))
    else:
        story.append(Paragraph(
            "Exterior siding, masonry, windows, and door seals were inspected. No active structural settling "
            "or significant foundation deflection observed. Roof sheathing and flashing inspected from eaves; "
            "estimated remaining useful life 12-15 years.", body_style
        ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Mechanical, Electrical & Plumbing", section_style))
    story.append(Paragraph(
        "Electrical service panel 200A main disconnect; copper branch wiring; GFCI receptacles functional. "
        "HVAC system operational on cooling and heating cycles. Water pressure tested at 55 PSI.", body_style
    ))
    story.append(Spacer(1, 20))
    story.append(Paragraph("<i>[End of Page 1 — Continued on Page 2]</i>", body_style))

    # PAGE 2
    story.append(PageBreak())
    story.append(Paragraph(f"<b>Inspection Report (Page 2) — {property_address} ({doc_id})</b>", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#b4c2c4'), spaceAfter=12))

    story.append(Paragraph("3. Interior Living Areas & Additions / Modifications", section_style))
    if water_damage:
        story.append(Paragraph(
            "<b>Special Finding — Water Damage:</b> Moisture readings of 28% at the primary bedroom ceiling and the "
            "exterior wall below the rear roof valley. Drywall staining and soft spots over approx. 60 sq ft. "
            "Repair of the roof and interior damage is required. Overall condition is downgraded from C3 to C4 "
            "(below average) until repairs are completed.",
            ParagraphStyle('Highlight', parent=body_style, backColor=colors.HexColor('#fbf0dc'), borderPadding=6)
        ))
    elif addition_narrative:
        # THE SEEDED DEMO NARRATIVE!
        story.append(Paragraph(
            "<b>Special Finding — Unrecorded Addition:</b> Rear two-story addition completed 2024 "
            "under permit #CH-24-0817, approx. 840 sq ft, finished, heated. Construction quality matches main residence. "
            "Includes enlarged family room on level 1 and primary suite on level 2. Full HVAC extension confirmed. "
            "Note: Public county tax records currently reflect pre-addition GLA of 1,240 sq ft.",
            ParagraphStyle('Highlight', parent=body_style, backColor=colors.HexColor('#fbf0dc'), borderPadding=6)
        ))
    else:
        story.append(Paragraph(
            "Standard interior room layout inspected. Finished living area consistent with builder specifications. "
            "No unpermitted structural additions or modifications noted.", body_style
        ))
    story.append(Spacer(1, 15))

    story.append(Paragraph("4. Inspector Summary & Rating", section_style))
    rating_data = [
        ["System", "Rating", "Comments"],
        ["Roofing", "Poor", "Active leak at rear valley"] if water_damage else ["Roofing", "Good", "Normal weathering, no leaks"],
        ["HVAC", "Good", "Serviced fall 2024"],
        ["Plumbing", "Satisfactory", "No active leaks detected"],
        ["Overall Condition", "C4 (Below Average)", "Deferred maintenance: roof and water damage"] if water_damage
        else ["Overall Condition", "C3 (Above Average)", "Well maintained residential property"],
    ]
    t2 = Table(rating_data, colWidths=[130, 110, 290])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1d6c75')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#b4c2c4')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f4f6f5')]),
    ]))
    story.append(t2)

    doc.build(story)


def create_appraisal_pdf(filepath: Path, property_address: str, doc_id: str, gla: int, beds: int, baths: float, eff_date: str):
    """Generate a legacy appraisal document (Fannie Mae 1004 style)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(filepath), pagesize=letter, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1c2a2e'),
        spaceAfter=10
    )
    body_style = ParagraphStyle('DocBody', parent=styles['Normal'], fontSize=9, leading=12)

    story.append(Paragraph("UNIFORM RESIDENTIAL APPRAISAL REPORT (URAR)", title_style))
    story.append(Paragraph(f"File No: {doc_id} | Effective Date: {eff_date}", body_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black, spaceAfter=10))

    grid = [
        ["SUBJECT PROPERTY", property_address, "County:", "Cedar Hollow"],
        ["Gross Living Area (GLA):", f"{gla:,} SF", "Total Rooms:", f"{beds + 3}"],
        ["Bedrooms Above Grade:", f"{beds}", "Bathrooms:", f"{baths:.1f}"],
        ["Year Built:", "1988", "Appraised Value:", "$315,000"],
    ]
    t = Table(grid, colWidths=[140, 140, 100, 150])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f0f0f0')),
    ]))
    story.append(t)
    doc.build(story)


def create_permit_pdf(filepath: Path, permit_num: str, address: str, sqft: int = 840):
    """Generate building permit PDF (attached as reviewer evidence during demo)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(filepath), pagesize=letter, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, leading=22, alignment=1)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=15)

    story.append(Paragraph("TOWN OF CEDAR HOLLOW", title_style))
    story.append(Paragraph("DEPARTMENT OF BUILDING & SAFETY", ParagraphStyle('Sub', parent=title_style, fontSize=12, leading=16)))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>CERTIFICATE OF OCCUPANCY & COMPLIANCE</b>", ParagraphStyle('Sub2', parent=title_style, fontSize=14, leading=18)))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.black, spaceAfter=20))

    story.append(Paragraph(f"<b>Permit Number:</b> {permit_num}", body_style))
    story.append(Paragraph(f"<b>Property Address:</b> {address}", body_style))
    story.append(Paragraph(f"<b>Issue Date:</b> September 14, 2024", body_style))
    story.append(Paragraph(f"<b>Scope of Work:</b> Two-Story Residential Addition ({sqft} sq ft finished living area).", body_style))
    story.append(Paragraph(f"<b>Contractor:</b> Apex Building & Remodeling LLC (License #CH-BLD-882)", body_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph(
        "This certifies that the permitted addition described above has been thoroughly inspected for compliance "
        "with Cedar Hollow Uniform Building, Electrical, and Mechanical Codes, and is hereby approved for occupancy.",
        body_style
    ))
    story.append(Spacer(1, 40))
    story.append(Paragraph("________________________________________<br/><b>Chief Building Inspector</b>, Town of Cedar Hollow", body_style))

    doc.build(story)


def generate_demo_pdfs():
    out_dir = Path("data_gen/out/pdfs")

    # 1. 14 Larkspur Legacy Appraisal (1,240 sq ft)
    p14_app = out_dir / "los/appraisal_legacy/DOC-APP-000014.pdf"
    create_appraisal_pdf(p14_app, "14 Larkspur Ln", "DOC-APP-000014", gla=1240, beds=3, baths=2.0, eff_date="2019-06-15")

    # 2. 14 Larkspur Inspection (Addition narrative on p. 2)
    p14_ins = out_dir / "servicing/inspection/DOC-INS-000014.pdf"
    create_inspection_pdf(p14_ins, "14 Larkspur Ln", "DOC-INS-000014", addition_narrative=True)

    # 3. 14 Larkspur Permit (Evidence file for reviewer upload!)
    p14_permit = out_dir / "evidence/DOC-PERMIT-CH-24-0817.pdf"
    create_permit_pdf(p14_permit, "CH-24-0817", "14 Larkspur Ln", sqft=840)

    # 4. 22 Hilltop Legacy Appraisal (2,450 sq ft - conflicts with county 1,950 sq ft)
    p22_app = out_dir / "los/appraisal_legacy/DOC-APP-000022.pdf"
    create_appraisal_pdf(p22_app, "22 Hilltop Rd", "DOC-APP-000022", gla=2450, beds=4, baths=3.0, eff_date="2025-08-20")

    print("Demo PDFs generated successfully in data_gen/out/pdfs/")


def generate_arrival_pdfs():
    """Documents that are on file but not parsed yet, for the live ingestion demo."""
    out_dir = Path("data_gen/out/pdfs")
    p18_ins = out_dir / "servicing/inspection/DOC-INS-001640.pdf"
    create_inspection_pdf(p18_ins, "18 Larkspur Ln", "DOC-INS-001640", water_damage=True, inspection_date="February 15, 2025")
    print(f"Arrival PDF generated: {p18_ins}")


if __name__ == "__main__":
    generate_demo_pdfs()
    generate_arrival_pdfs()
