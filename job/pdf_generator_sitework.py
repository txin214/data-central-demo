"""
PDF Generator for Sitework Quotes using ReportLab
"""
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from job.models import Job
from sitework.models import SiteworkQuote, SiteworkQuoteLine, SiteworkCat
from datetime import datetime


def sitework_quote_pdf_generate(request, job_id, quote_id):
    """Generate PDF for sitework quote with same header/footer as job print preview"""
    job = get_object_or_404(Job, id=job_id)
    sitework_quote = get_object_or_404(SiteworkQuote, id=quote_id, job=job)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfgen import canvas
        from io import BytesIO
        import os
        from django.conf import settings
    except ImportError:
        # Fallback if ReportLab not available
        return HttpResponseRedirect(reverse('job:job_sitework', args=[job_id]))
    
    try:
        # Calculate prices
        SiteworkQuoteLine.objects.calc_price(sitework_quote.id)
        
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document with A4 page size and margins (same as job print preview)
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=A4,
            leftMargin=20*mm,
            rightMargin=20*mm,
            topMargin=50*mm,
            bottomMargin=30*mm
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Header and Footer drawing functions (same as job print preview)
        def draw_header_footer(canvas, doc):
            """Draw header and footer on each page - same as job print preview"""
            try:
                page_width, page_height = A4
                
                # Header
                canvas.saveState()
                
                # Draw logo
                logo_path = os.path.join(settings.BASE_DIR, 'crm', 'static', 'crm', 'nologo.png')
                if os.path.exists(logo_path):
                    try:
                        logo_width = 160
                        logo_height = 60
                        logo_x = 20*mm
                        logo_y = (page_height - 15*mm) - logo_height
                        canvas.drawImage(logo_path, logo_x, logo_y, width=logo_width, height=logo_height)
                    except Exception:
                        pass
                
                # Header text
                canvas.setFont("Helvetica-Bold", 10)
                canvas.setFillColor(colors.black)
                
                phone_num = "800-227-8575"
                canvas.drawRightString(page_width - 20*mm, page_height - 20*mm, phone_num)
                
                madison_text = "2219 S. Stoughton Rd, Madison WI 53716    608-274-9933"
                canvas.drawRightString(page_width - 20*mm, page_height - 27*mm, madison_text)
                
                brookfield_text = "18525 W. Bluemound Rd,Brookfield WI 53045    262-395-7100"
                canvas.drawRightString(page_width - 20*mm, page_height - 34*mm, brookfield_text)
                
                canvas.restoreState()
                
                # Footer
                canvas.saveState()
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(colors.black)
                
                footer_y = 15*mm
                canvas.drawString(20*mm, footer_y, "Div. Allen Construction Services, Inc.")
                
                page_num = canvas.getPageNumber()
                canvas.drawCentredString(page_width/2, footer_y, f"{page_num}")
                
                current_date = datetime.now().strftime("%m/%d/%Y")
                canvas.drawRightString(page_width - 20*mm, footer_y, f"Date: {current_date}")
                
                canvas.restoreState()
            except Exception:
                pass
        
        # Create custom styles
        # Main section box style (same as print preview template - grey background)
        main_section_box_style = ParagraphStyle(
            'MainSectionBox',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=8,
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            backColor=colors.lightgrey,
            borderWidth=0,
            borderPadding=4
        )
        
        category_style = ParagraphStyle(
            'CategoryStyle',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        subtotal_style = ParagraphStyle(
            'SubtotalStyle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=0,
            textColor=colors.black,
            alignment=TA_RIGHT,
            fontName='Helvetica'
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=2,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        # Build PDF content
        story = []
        
        # Title with grey background (same as print preview template)
        story.append(Spacer(1, -10*mm))
        title_text = "Cost Breakdown"
        if sitework_quote.customer:
            title_text += f" - {sitework_quote.customer.first_name} {sitework_quote.customer.last_name}"
        story.append(Paragraph(title_text, main_section_box_style))
        story.append(Spacer(1, 5*mm))
        
        # Two-column layout for quote information
        left_column_data = []
        right_column_data = []
        
        # Left column: Customer, Room, Description
        if sitework_quote.customer:
            customer_name = f"{sitework_quote.customer.first_name} {sitework_quote.customer.last_name}"
            left_column_data.append(Paragraph(f"<b>Customer:</b> {customer_name}", info_style))
        
        if sitework_quote.kbflag:
            kb_display = dict(SiteworkQuote.KBFLAG_CHOICES).get(sitework_quote.kbflag, sitework_quote.kbflag)
            left_column_data.append(Paragraph(f"<b>Room:</b> {kb_display}", info_style))
        
        if sitework_quote.quotedesc:
            left_column_data.append(Paragraph(f"<b>Description:</b> {sitework_quote.quotedesc}", info_style))
        
        # Right column: Quoted By, Quoted On
        if sitework_quote.quotedby:
            quoted_by_name = f"{sitework_quote.quotedby.first_name} {sitework_quote.quotedby.last_name}".strip() or sitework_quote.quotedby.username
            right_column_data.append(Paragraph(f"<b>Quoted By:</b> {quoted_by_name}", info_style))
        
        if sitework_quote.quotedate:
            right_column_data.append(Paragraph(f"<b>Quoted On:</b> {sitework_quote.quotedate.strftime('%m/%d/%Y %I:%M %p')}", info_style))
        
        # Create two-column table
        info_table_data = []
        max_rows = max(len(left_column_data), len(right_column_data))
        
        for i in range(max_rows):
            left_item = left_column_data[i] if i < len(left_column_data) else Paragraph('', info_style)
            right_item = right_column_data[i] if i < len(right_column_data) else Paragraph('', info_style)
            info_table_data.append([left_item, right_item])
        
        info_table = Table(info_table_data, colWidths=[85*mm, 85*mm])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 8*mm))
        
        # Process categories and items - using same style as Product Proposed section
        for category in SiteworkCat.objects.order_by('orderby'):
            # Get items with quantity > 0 for this category
            items = SiteworkQuoteLine.objects.filter(
                cat=category, 
                quote=sitework_quote.id, 
                quantity__gt=0
            ).order_by('orderby')
            
            if not items.exists():
                continue
            
            # Category header with column headers on same line - uppercase (matching image format)
            # Use fixed column widths for perfect alignment
            col_widths = [100*mm, 25*mm, 25*mm, 25*mm]
            
            # Build combined table with header row and data rows for perfect alignment
            table_data = []
            
            # Header row: Category name on left, Base/Unit/Price on right
            # Use plain strings for price columns to ensure alignment
            table_data = []
            table_data.append([
                Paragraph(f"<b>{category.name.upper()}</b>", normal_style),
                'Base',
                'Unit',
                'Price'
            ])
            
            category_total = 0
            for item in items:
                # Calculate price
                if item.editallowance == '1':
                    price = (item.allowance / item.profit) if item.profit > 0 else 0
                else:
                    price = (item.quantity * item.unitamount) + item.basecost
                
                # BILLCODE override
                if item.quantity > 0 and item.calckey == 558:
                    price = 100
                
                category_total += price
                
                # Format values - combine qty, unit, and description inline in first column
                qty = str(item.quantity)
                unit = item.quantitydesc or 'EA'
                desc = item.workdesc or ''
                # Combine qty, unit, and description inline (matching image format)
                desc_with_qty = f"{qty} {unit} {desc}"
                
                base = f"{item.basecost:.2f}"
                unit_price = f"{item.unitamount:.2f}"
                item_price = f"{price:.2f}"
                
                # Use Paragraph only for description (to handle wrapping), plain strings for prices
                desc_para = Paragraph(desc_with_qty, normal_style)
                table_data.append([desc_para, base, unit_price, item_price])
            
            # Create single table with header and data rows for perfect alignment
            item_table = Table(table_data, colWidths=col_widths, repeatRows=0)
            item_table.setStyle(TableStyle([
                # All rows use same alignment rules - consistent across header and data
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Description column left-aligned
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),  # Base, Unit, Price columns right-aligned
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Category name bold
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                # Add line below header row (first row)
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
            ]))
            
            story.append(item_table)
            # Category Subtotal below table (matching image format)
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(f"Category Sub Total: {category_total:.2f}", subtotal_style))
            story.append(Spacer(1, 8*mm))
        
        # Calculate totals
        sitework_total = 0
        for category in SiteworkCat.objects.order_by('orderby'):
            items = SiteworkQuoteLine.objects.filter(
                cat=category, 
                quote=sitework_quote.id, 
                quantity__gt=0
            )
            for item in items:
                if item.editallowance == '1':
                    price = (item.allowance / item.profit) if item.profit > 0 else 0
                else:
                    price = (item.quantity * item.unitamount) + item.basecost
                if item.quantity > 0 and item.calckey == 558:
                    price = 100
                sitework_total += price
        
        contingency_pct = 0.05
        overhead_pct = 0.28
        contingency = sitework_total * contingency_pct
        overhead = sitework_total * overhead_pct
        final_total = sitework_total + contingency + overhead
        
        # Summary totals - aligned to the right, labels and values very close together
        story.append(Spacer(1, 5*mm))
        # Combine label and value with one extra space between them
        summary_data = [
            [f"Site Work Sub Total:  {sitework_total:.2f}"],
            [f"Contingency Fund:  {contingency:.2f}"],
            [f"Over Head Fee:  {overhead:.2f}"],
            [f"Site Work Total:  {final_total:.2f}"]
        ]
        
        # Create single column table aligned to the right
        summary_table = Table(summary_data, colWidths=[175*mm])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),  # All text right-aligned
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (0, -1), 0),
            ('RIGHTPADDING', (0, 0), (0, -1), 0),
            # Removed LINEBELOW - no line above the summary section
        ]))
        
        story.append(summary_table)
        
        # Build PDF
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Get PDF content
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"sitework_quote_{sitework_quote.id}_{job.job_code}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
        
    except Exception as e:
        import traceback
        print(f"Sitework Quote PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('job:job_sitework', args=[job_id]))

