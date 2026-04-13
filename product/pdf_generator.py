"""
PDF Generator for Product Quotes using ReportLab
"""
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from product.models import ProductQuote
from job.utils import group_line_items_by_category, format_currency


def product_quote_pdf_generate(request, quote_id):
    """Generate PDF for product quote with same header/footer as job print preview"""
    quote = get_object_or_404(ProductQuote, id=quote_id)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from io import BytesIO
        import os
        from datetime import datetime
        from django.conf import settings
    except ImportError:
        # Fallback if ReportLab not available
        return HttpResponseRedirect(reverse('product:product_quote_list'))
    
    try:
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
        main_section_box_style = ParagraphStyle(
            'MainSectionBox',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=8,
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            backColor=colors.lightgrey,
            borderWidth=0,
            borderPadding=4
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        bold_style = ParagraphStyle(
            'BoldStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
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
        
        # Build PDF content
        story = []
        
        # Title
        story.append(Spacer(1, -10*mm))
        story.append(Paragraph("Product Quote", main_section_box_style))
        story.append(Spacer(1, 5*mm))
        
        # Quote information
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=2,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        if quote.name:
            story.append(Paragraph(f"<b>Quote Name:</b> {quote.name}", info_style))
        if quote.customer:
            customer_name = f"{quote.customer.first_name} {quote.customer.last_name}"
            story.append(Paragraph(f"<b>Customer:</b> {customer_name}", info_style))
        if quote.quoted_date:
            story.append(Paragraph(f"<b>Quote Date:</b> {quote.quoted_date.strftime('%m/%d/%Y %I:%M %p')}", info_style))
        
        story.append(Spacer(1, 8*mm))
        
        # Product Proposed Section
        story.append(Paragraph("Product Proposed", main_section_box_style))
        story.append(Paragraph(f"<b>Product Quote:</b> {quote.name or f'Quote #{quote.id}'}", normal_style))
        story.append(Spacer(1, 3*mm))
        
        # Group line items by category
        categories_data = group_line_items_by_category(quote.line_items.all(), quote.adhoc_line_items.all())
        
        for category in categories_data:
            # Category header
            story.append(Paragraph(f"<b>{category['name']}</b>", bold_style))
            story.append(Spacer(1, 2*mm))
            
            # Create table for items
            table_data = [['Part Number', 'QTY', 'Description']]
            
            for item_type, item in category['items']:
                if item_type == 'product':
                    part_no = item.product.part_no or ''
                    description = str(item.product.description or '')
                else:
                    part_no = item.adhoc.part_no or ''
                    description = str(item.adhoc.description or '')
                
                # Description cell
                desc_cell = Paragraph(description, styles['Normal'])
                
                table_data.append([
                    part_no,
                    str(item.quantity),
                    desc_cell
                ])
            
            items_table = Table(table_data, colWidths=[30*mm, 15*mm, 115*mm])
            items_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('FONTNAME', (0, 0), (2, 0), 'Helvetica-Bold'),  # Header row
            ]))
            
            story.append(items_table)
            story.append(Paragraph(f"Section Subtotal: {category['subtotal']}", subtotal_style))
            story.append(Spacer(1, 8*mm))
        
        # Quote Totals (Subtotal, Tax, Total with Tax)
        story.append(Spacer(1, 5*mm))
        total_style = ParagraphStyle(
            'TotalStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=2,
            textColor=colors.black,
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold'
        )
        
        # Calculate tax and total
        tax_rate = quote.get_tax_rate()
        tax_amount = quote.calculate_tax()
        total_with_tax = quote.get_total_with_tax()
        
        # Subtotal
        story.append(Paragraph(f"Subtotal: {format_currency(quote.subtotal)}", total_style))
        
        # Tax (only show if tax rate > 0)
        if tax_rate > 0:
            tax_rate_percent = tax_rate * 100
            story.append(Paragraph(f"Tax ({tax_rate_percent:.2f}%): {format_currency(tax_amount)}", total_style))
        
        # Total with Tax
        story.append(Paragraph(f"Total: {format_currency(total_with_tax)}", total_style))
        
        # Build PDF
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Get PDF content
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"product_quote_{quote.id}_{quote.name or 'quote'}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
        
    except Exception as e:
        import traceback
        print(f"Product Quote PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('product:product_quote_list'))

