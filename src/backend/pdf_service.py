"""
PDF Service - Server-side PDF generation using ReportLab with Markdown support
"""

import io
import os
import re
import json
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, KeepTogether, ListFlowable, ListItem, Preformatted
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
    logging.warning(f"Failed to register CJK font: {e}. Chinese may not display correctly.")
    CJK_FONT = 'Helvetica'

# Color scheme
CYAN_COLOR = colors.HexColor('#00bcd4')
OK_GREEN = colors.HexColor('#00e676')
NG_RED = colors.HexColor('#ff3b30')
MUTED_TEXT = colors.HexColor('#888888')
CODE_BG = colors.HexColor('#1a1f25')


def get_styles():
    """Create custom paragraph styles including markdown styles"""
    styles = getSampleStyleSheet()

    # Base styles
    styles.add(ParagraphStyle(
        name='ReportTitle',
        fontName=CJK_FONT,
        fontSize=24,
        textColor=CYAN_COLOR,
        spaceAfter=12,
        alignment=1
    ))

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

    styles.add(ParagraphStyle(
        name='CJKNormal',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=colors.black,
        spaceAfter=6,
        leading=14
    ))

    styles.add(ParagraphStyle(
        name='PointName',
        fontName=CJK_FONT,
        fontSize=12,
        textColor=CYAN_COLOR,
        spaceBefore=8,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name='SmallText',
        fontName=CJK_FONT,
        fontSize=8,
        textColor=MUTED_TEXT
    ))

    # Markdown styles
    styles.add(ParagraphStyle(
        name='MDH1',
        fontName=CJK_FONT,
        fontSize=16,
        textColor=CYAN_COLOR,
        spaceBefore=14,
        spaceAfter=8,
        leading=20
    ))

    styles.add(ParagraphStyle(
        name='MDH2',
        fontName=CJK_FONT,
        fontSize=14,
        textColor=CYAN_COLOR,
        spaceBefore=12,
        spaceAfter=6,
        leading=18
    ))

    styles.add(ParagraphStyle(
        name='MDH3',
        fontName=CJK_FONT,
        fontSize=12,
        textColor=CYAN_COLOR,
        spaceBefore=10,
        spaceAfter=4,
        leading=16
    ))

    styles.add(ParagraphStyle(
        name='MDH4',
        fontName=CJK_FONT,
        fontSize=11,
        textColor=colors.HexColor('#0099aa'),
        spaceBefore=8,
        spaceAfter=4,
        leading=14
    ))

    styles.add(ParagraphStyle(
        name='MDParagraph',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=colors.black,
        spaceBefore=4,
        spaceAfter=6,
        leading=14
    ))

    styles.add(ParagraphStyle(
        name='MDBlockquote',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=MUTED_TEXT,
        leftIndent=15,
        borderLeftWidth=2,
        borderLeftColor=CYAN_COLOR,
        borderLeftPadding=8,
        spaceBefore=6,
        spaceAfter=6,
        leading=14
    ))

    styles.add(ParagraphStyle(
        name='MDCode',
        fontName='Courier',
        fontSize=9,
        textColor=colors.HexColor('#00f0ff'),
        backColor=CODE_BG,
        borderWidth=1,
        borderColor=colors.HexColor('#333'),
        borderPadding=8,
        spaceBefore=6,
        spaceAfter=6,
        leading=12
    ))

    styles.add(ParagraphStyle(
        name='MDListItem',
        fontName=CJK_FONT,
        fontSize=10,
        textColor=colors.black,
        leftIndent=15,
        spaceBefore=2,
        spaceAfter=2,
        leading=14,
        bulletIndent=5
    ))

    return styles


def escape_xml(text):
    """Escape special XML characters for ReportLab Paragraph"""
    if not text:
        return ''
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def convert_inline_markdown(text):
    """Convert inline markdown (bold, italic, code) to ReportLab XML tags"""
    if not text:
        return ''

    # Escape XML first
    text = escape_xml(text)

    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'(?<![_])_([^_]+)_(?![_])', r'<i>\1</i>', text)

    # Inline code: `code`
    text = re.sub(r'`([^`]+)`', r'<font face="Courier" color="#00f0ff">\1</font>', text)

    return text


def markdown_to_flowables(markdown_text, styles):
    """
    Convert markdown text to ReportLab flowables.

    Supports: headers, bold, italic, code blocks, blockquotes, lists, paragraphs
    """
    if not markdown_text:
        return [Paragraph("No content.", styles['CJKNormal'])]

    flowables = []
    lines = markdown_text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Code block (```)
        if stripped.startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # Skip closing ```

            if code_lines:
                code_text = escape_xml('\n'.join(code_lines))
                flowables.append(Preformatted(code_text, styles['MDCode']))
            continue

        # Headers
        if stripped.startswith('#'):
            match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if match:
                level = len(match.group(1))
                header_text = convert_inline_markdown(match.group(2))
                style_name = f'MDH{min(level, 4)}'
                flowables.append(Paragraph(header_text, styles[style_name]))
                i += 1
                continue

        # Blockquote
        if stripped.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            quote_text = convert_inline_markdown(' '.join(quote_lines))
            flowables.append(Paragraph(quote_text, styles['MDBlockquote']))
            continue

        # Unordered list
        if stripped.startswith(('- ', '* ', '+ ')):
            list_items = []
            while i < len(lines):
                l = lines[i].strip()
                if l.startswith(('- ', '* ', '+ ')):
                    item_text = convert_inline_markdown(l[2:])
                    list_items.append(ListItem(Paragraph(item_text, styles['MDListItem'])))
                    i += 1
                elif l and not l.startswith('#') and not l.startswith('>'):
                    # Continuation of previous item
                    if list_items:
                        prev = list_items[-1]
                        prev_text = prev._flowables[0].text if hasattr(prev, '_flowables') else ''
                        list_items[-1] = ListItem(Paragraph(
                            prev_text + ' ' + convert_inline_markdown(l),
                            styles['MDListItem']
                        ))
                    i += 1
                else:
                    break

            if list_items:
                flowables.append(ListFlowable(
                    list_items,
                    bulletType='bullet',
                    bulletColor=CYAN_COLOR,
                    leftIndent=10
                ))
            continue

        # Ordered list
        if re.match(r'^\d+\.\s', stripped):
            list_items = []
            while i < len(lines):
                l = lines[i].strip()
                match = re.match(r'^\d+\.\s+(.+)$', l)
                if match:
                    item_text = convert_inline_markdown(match.group(1))
                    list_items.append(ListItem(Paragraph(item_text, styles['MDListItem'])))
                    i += 1
                else:
                    break

            if list_items:
                flowables.append(ListFlowable(
                    list_items,
                    bulletType='1',
                    bulletColor=CYAN_COLOR,
                    leftIndent=10
                ))
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            flowables.append(Spacer(1, 3*mm))
            hr = Table([['']],colWidths=[170*mm])
            hr.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]))
            flowables.append(hr)
            flowables.append(Spacer(1, 3*mm))
            i += 1
            continue

        # Regular paragraph
        para_lines = [stripped]
        i += 1
        while i < len(lines):
            next_line = lines[i].strip()
            if not next_line or next_line.startswith(('#', '>', '-', '*', '+', '```')) or re.match(r'^\d+\.', next_line):
                break
            para_lines.append(next_line)
            i += 1

        para_text = convert_inline_markdown(' '.join(para_lines))
        flowables.append(Paragraph(para_text, styles['MDParagraph']))

    return flowables if flowables else [Paragraph("No content.", styles['CJKNormal'])]


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
        if isinstance(response_str, str):
            is_ng = 'ng' in response_str.lower()

    return is_ng, description


def generate_patrol_report(run_id):
    """Generate a PDF report for a patrol run with markdown support."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM patrol_runs WHERE id = ?', (run_id,))
    run = cursor.fetchone()

    if not run:
        conn.close()
        raise ValueError(f"Patrol run #{run_id} not found")

    run_dict = dict(run)

    cursor.execute('SELECT * FROM inspection_results WHERE run_id = ? ORDER BY id', (run_id,))
    inspections = [dict(row) for row in cursor.fetchall()]
    conn.close()

    buffer = io.BytesIO()
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
    story.append(Paragraph(f"Report #{run_id}", styles['CJKNormal']))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles['SmallText']
    ))
    story.append(Spacer(1, 20*mm))

    # === Patrol Information ===
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

    # === AI Summary Report (Markdown) ===
    story.append(Paragraph("AI Summary Report", styles['SectionHeader']))

    report_content = run_dict.get('report_content', '')
    if report_content:
        md_flowables = markdown_to_flowables(report_content, styles)
        story.extend(md_flowables)
    else:
        story.append(Paragraph("No report generated.", styles['CJKNormal']))

    story.append(Spacer(1, 10*mm))

    # === Inspection Points ===
    story.append(Paragraph(f"Inspection Points ({len(inspections)})", styles['SectionHeader']))

    if not inspections:
        story.append(Paragraph("No inspection records.", styles['CJKNormal']))
    else:
        for ins in inspections:
            inspection_elements = []

            is_ng, description = parse_ai_response(ins.get('ai_response', ''))
            status_color = NG_RED if is_ng else OK_GREEN
            status_text = 'NG' if is_ng else 'OK'

            point_name = ins.get('point_name', 'Unknown Point')
            inspection_elements.append(Paragraph(
                f"<font color='#00bcd4'>{escape_xml(point_name)}</font> "
                f"<font color='{status_color.hexval()}'>[{status_text}]</font>",
                styles['PointName']
            ))

            timestamp = ins.get('timestamp', 'N/A')
            coord_x = ins.get('coordinate_x')
            coord_y = ins.get('coordinate_y')
            coord_str = f"({coord_x:.2f}, {coord_y:.2f})" if coord_x is not None else "N/A"

            inspection_elements.append(Paragraph(
                f"Time: {timestamp} | Coordinates: {coord_str}",
                styles['SmallText']
            ))

            image_path = ins.get('image_path')
            if image_path:
                full_image_path = os.path.join(IMAGES_DIR, image_path)
                if os.path.exists(full_image_path):
                    try:
                        img = Image(full_image_path)
                        max_width = 140*mm
                        max_height = 80*mm
                        width_ratio = max_width / img.drawWidth
                        height_ratio = max_height / img.drawHeight
                        scale = min(width_ratio, height_ratio, 1.0)
                        img.drawWidth *= scale
                        img.drawHeight *= scale
                        inspection_elements.append(Spacer(1, 3*mm))
                        inspection_elements.append(img)
                    except Exception as e:
                        logging.warning(f"Failed to load image {full_image_path}: {e}")

            inspection_elements.append(Spacer(1, 3*mm))
            prompt = ins.get('prompt', 'N/A')
            inspection_elements.append(Paragraph(
                f"<b>Prompt:</b> {escape_xml(prompt)}",
                styles['CJKNormal']
            ))

            result_color = '#ff3b30' if is_ng else '#00e676'
            inspection_elements.append(Paragraph(
                f"<b>Result:</b> <font color='{result_color}'>{escape_xml(description)}</font>",
                styles['CJKNormal']
            ))

            inspection_elements.append(Spacer(1, 5*mm))

            line_table = Table([['']],colWidths=[170*mm])
            line_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ]))
            inspection_elements.append(line_table)
            inspection_elements.append(Spacer(1, 3*mm))

            story.append(KeepTogether(inspection_elements[:4]))
            story.extend(inspection_elements[4:])

    def add_page_number(canvas, doc):
        canvas.saveState()
        page_num = canvas.getPageNumber()
        canvas.setFont(CJK_FONT, 8)
        canvas.setFillColor(MUTED_TEXT)
        canvas.drawCentredString(A4[0] / 2, 15*mm, f"Page {page_num}")
        canvas.drawCentredString(A4[0] / 2, 10*mm, f"SIGMA PATROL System - Report #{run_id}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes
