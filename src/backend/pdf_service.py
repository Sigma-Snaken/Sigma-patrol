"""
PDF Service - Server-side PDF generation using ReportLab
"""

import io
import os
import json
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from config import IMAGES_DIR
from database import get_db_connection

# Register CID font for Chinese support
try:
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    CJK_FONT = 'STSong-Light'
except Exception as e:
    logging.warning(f"Failed to register CJK font: {e}. Chinese characters may not display correctly.")
    CJK_FONT = 'Helvetica'

# Color scheme matching the web UI
CYAN_COLOR = colors.HexColor('#00bcd4')
DARK_BG = colors.HexColor('#1a1f25')
LIGHT_TEXT = colors.HexColor('#e8f4f8')
OK_GREEN = colors.HexColor('#00e676')
NG_RED = colors.HexColor('#ff3b30')
MUTED_TEXT = colors.HexColor('#888888')


def get_styles():
    """Create custom paragraph styles"""
    styles = getSampleStyleSheet()

    # Title style
    styles.add(ParagraphStyle(
        name='ReportTitle',
        fontName=CJK_FONT,
        fontSize=24,
        textColor=CYAN_COLOR,
        spaceAfter=12,
        alignment=1  # Center
    ))

    # Section header style
    styles.add(ParagraphStyle(
        name='SectionHeader',
        fontName=CJK_FONT,
        fontSize=14,
        textColor=CYAN_COLOR,
        spaceBefore=12,
        spaceAfter=8,
        borderWidth=1,
        borderColor=CYAN_COLOR,
        borderPadding=4
    ))

    # Normal text with CJK support
    styles.add(ParagraphStyle(
        name='CJKNormal',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=colors.black,
        spaceAfter=6,
        leading=14
    ))

    # Info label style
    styles.add(ParagraphStyle(
        name='InfoLabel',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=MUTED_TEXT
    ))

    # Info value style
    styles.add(ParagraphStyle(
        name='InfoValue',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=colors.black
    ))

    # Point name style
    styles.add(ParagraphStyle(
        name='PointName',
        fontName=CJK_FONT,
        fontSize=12,
        textColor=CYAN_COLOR,
        spaceBefore=8,
        spaceAfter=4
    ))

    # Small text style
    styles.add(ParagraphStyle(
        name='SmallText',
        fontName=CJK_FONT,
        fontSize=8,
        textColor=MUTED_TEXT
    ))

    return styles


def parse_ai_response(response_str):
    """Parse AI response to extract is_NG and Description"""
    is_ng = False
    description = response_str or ''

    try:
        data = json.loads(response_str)
        if isinstance(data, dict):
            is_ng = data.get('is_NG', False)
            description = data.get('Description', str(data))
    except (json.JSONDecodeError, TypeError):
        # Fallback: check if string contains 'ng'
        if isinstance(response_str, str):
            is_ng = 'ng' in response_str.lower()

    return is_ng, description


def generate_patrol_report(run_id):
    """
    Generate a PDF report for a patrol run.

    Args:
        run_id: The patrol run ID

    Returns:
        bytes: PDF file content
    """
    # Fetch data from database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get patrol run info
    cursor.execute('SELECT * FROM patrol_runs WHERE id = ?', (run_id,))
    run = cursor.fetchone()

    if not run:
        conn.close()
        raise ValueError(f"Patrol run #{run_id} not found")

    run_dict = dict(run)

    # Get inspection results
    cursor.execute('SELECT * FROM inspection_results WHERE run_id = ? ORDER BY id', (run_id,))
    inspections = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # Create PDF buffer
    buffer = io.BytesIO()

    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=25*mm
    )

    styles = get_styles()
    story = []

    # === Title Page ===
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("SIGMA PATROL REPORT", styles['ReportTitle']))
    story.append(Spacer(1, 10*mm))

    # Report info
    story.append(Paragraph(f"Report #{run_id}", styles['CJKNormal']))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles['SmallText']
    ))
    story.append(Spacer(1, 20*mm))

    # === Patrol Information Section ===
    story.append(Paragraph("Patrol Information", styles['SectionHeader']))

    info_data = [
        ['Status:', run_dict.get('status', 'N/A')],
        ['Start Time:', run_dict.get('start_time', 'N/A')],
        ['End Time:', run_dict.get('end_time', 'N/A')],
        ['Robot Serial:', run_dict.get('robot_serial', 'N/A')],
        ['AI Model:', run_dict.get('model_id', 'N/A')],
        ['Total Tokens:', str(run_dict.get('total_tokens', 0))],
    ]

    info_table = Table(info_data, colWidths=[35*mm, 120*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), CJK_FONT),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), MUTED_TEXT),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10*mm))

    # === AI Summary Report Section ===
    story.append(Paragraph("AI Summary Report", styles['SectionHeader']))

    report_content = run_dict.get('report_content', 'No report generated.')
    if report_content:
        # Split by newlines and create paragraphs
        for line in report_content.split('\n'):
            if line.strip():
                story.append(Paragraph(line, styles['CJKNormal']))
    else:
        story.append(Paragraph("No report generated.", styles['CJKNormal']))

    story.append(Spacer(1, 10*mm))

    # === Inspection Points Section ===
    story.append(Paragraph(f"Inspection Points ({len(inspections)})", styles['SectionHeader']))

    if not inspections:
        story.append(Paragraph("No inspection records.", styles['CJKNormal']))
    else:
        for ins in inspections:
            # Create a KeepTogether group for each inspection
            inspection_elements = []

            # Point header with status
            is_ng, description = parse_ai_response(ins.get('ai_response', ''))
            status_color = NG_RED if is_ng else OK_GREEN
            status_text = 'NG' if is_ng else 'OK'

            point_name = ins.get('point_name', 'Unknown Point')
            inspection_elements.append(Paragraph(
                f"<font color='#00bcd4'>{point_name}</font> "
                f"<font color='{status_color.hexval()}'>[{status_text}]</font>",
                styles['PointName']
            ))

            # Timestamp and coordinates
            timestamp = ins.get('timestamp', 'N/A')
            coord_x = ins.get('coordinate_x')
            coord_y = ins.get('coordinate_y')
            coord_str = f"({coord_x:.2f}, {coord_y:.2f})" if coord_x is not None else "N/A"

            inspection_elements.append(Paragraph(
                f"Time: {timestamp} | Coordinates: {coord_str}",
                styles['SmallText']
            ))

            # Image (if available)
            image_path = ins.get('image_path')
            if image_path:
                full_image_path = os.path.join(IMAGES_DIR, image_path)
                if os.path.exists(full_image_path):
                    try:
                        img = Image(full_image_path)
                        # Scale image to fit (max width 140mm, maintain aspect ratio)
                        max_width = 140*mm
                        max_height = 80*mm

                        # Get original dimensions
                        img_width = img.drawWidth
                        img_height = img.drawHeight

                        # Calculate scale
                        width_ratio = max_width / img_width
                        height_ratio = max_height / img_height
                        scale = min(width_ratio, height_ratio, 1.0)

                        img.drawWidth = img_width * scale
                        img.drawHeight = img_height * scale

                        inspection_elements.append(Spacer(1, 3*mm))
                        inspection_elements.append(img)
                    except Exception as e:
                        logging.warning(f"Failed to load image {full_image_path}: {e}")

            # Prompt and Result
            inspection_elements.append(Spacer(1, 3*mm))
            prompt = ins.get('prompt', 'N/A')
            inspection_elements.append(Paragraph(
                f"<b>Prompt:</b> {prompt}",
                styles['CJKNormal']
            ))

            result_color = '#ff3b30' if is_ng else '#00e676'
            inspection_elements.append(Paragraph(
                f"<b>Result:</b> <font color='{result_color}'>{description}</font>",
                styles['CJKNormal']
            ))

            inspection_elements.append(Spacer(1, 5*mm))

            # Add horizontal line
            line_table = Table([['']],colWidths=[170*mm])
            line_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]))
            inspection_elements.append(line_table)
            inspection_elements.append(Spacer(1, 3*mm))

            # Try to keep inspection together, but allow split if needed
            story.append(KeepTogether(inspection_elements[:4]))  # Keep header and image together
            story.extend(inspection_elements[4:])  # Allow rest to flow

    # Build PDF
    def add_page_number(canvas, doc):
        """Add page number and footer to each page"""
        canvas.saveState()

        # Page number
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.setFont(CJK_FONT, 8)
        canvas.setFillColor(MUTED_TEXT)
        canvas.drawCentredString(A4[0] / 2, 15*mm, text)

        # Footer
        footer_text = f"SIGMA PATROL System - Report #{run_id}"
        canvas.drawCentredString(A4[0] / 2, 10*mm, footer_text)

        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    # Get PDF content
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
