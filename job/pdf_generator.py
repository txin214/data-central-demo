"""
PDF Generator for Job Contracts using ReportLab
"""
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from job.models import Job, JobQuoteProductNotes, PurchaseOrder
from job.utils import group_line_items_by_category, group_sitework_by_category, format_currency
from sitework.models import SiteworkQuote, SiteworkQuoteLine, SiteworkCat


def job_pdf_generate(request, job_id):
    """Generate professional PDF using ReportLab for contract-style documents"""
    job = get_object_or_404(Job, id=job_id)
    
    # Get hidden categories from request parameters
    hidden_categories = request.GET.get('hidden_categories', '').split(',') if request.GET.get('hidden_categories') else []
    # Normalize for robust matching (trim + lowercase)
    hidden_categories = {cat.strip().lower() for cat in hidden_categories if cat.strip()}
    
    # Get sitework hide prices flag
    hide_sitework_prices = request.GET.get('hide_sitework_prices', 'false').lower() == 'true'
    
    # Debug logging (remove in production)
    print(f"PDF Generator - Hidden categories received: {hidden_categories}")
    print(f"PDF Generator - Hide sitework prices: {hide_sitework_prices}")
    print(f"PDF Generator - Request GET params: {dict(request.GET)}")
    
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
        from django.conf import settings
    except ImportError:
        # Fallback to existing print preview if ReportLab not available
        return HttpResponseRedirect(reverse('job:job_print_preview', args=[job_id]))
    
    try:
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document with A4 page size and margins (increased top/bottom for header/footer)
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=A4,
            leftMargin=20*mm,
            rightMargin=20*mm,
            topMargin=50*mm,  # Increased for header
            bottomMargin=30*mm  # Increased for footer
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Header and Footer drawing functions
        def draw_header_footer(canvas, doc):
            """Draw header and footer on each page"""
            try:
                # Get page dimensions
                page_width, page_height = A4
                
                # Header
                canvas.saveState()
                
                # Draw logo (made bigger)
                logo_path = os.path.join(settings.BASE_DIR, 'crm', 'static', 'crm', 'nologo.png')
                if os.path.exists(logo_path):
                    try:
                        # Logo dimensions and position (increased size)
                        logo_width = 160  # Increased from 80
                        logo_height = 60  # Increased from 30
                        logo_x = 20*mm
                        # Align logo bottom with the last line of contact info (Brookfield line)
                        # Last line is at page_height - 60*mm, so logo bottom should be at that level
                        logo_y = (page_height - 15*mm) - logo_height  # Position so bottom aligns with last contact line
                        
                        # Draw logo
                        canvas.drawImage(logo_path, logo_x, logo_y, width=logo_width, height=logo_height)
                    except Exception as e:
                        print(f"Logo error: {e}")  # Debug
                        pass  # If logo fails to load, continue without it
                
                # Header text
                canvas.setFont("Helvetica-Bold", 10)
                canvas.setFillColor(colors.black)
                
                # Contact info arranged inline as requested
                # Calculate right margin to match left margin (20mm)
                # Logo is 160mm wide starting at 20mm, so it ends at 180mm
                # Page width is 210mm, so right margin should be 30mm
                # But we want 20mm margin, so text should start at 210 - 20 - text_width
                # For now, let's position text to end at 190mm (210 - 20)
                
                # Toll-free number
                phone_num = "800-227-8575"
                phone_width = canvas.stringWidth(phone_num, "Helvetica-Bold", 10)
                canvas.drawRightString(page_width - 20*mm, page_height - 20*mm, phone_num)
                
                # Madison address and phone inline
                madison_text = "2219 S. Stoughton Rd, Madison WI 53716    608-274-9933"
                canvas.drawRightString(page_width - 20*mm, page_height - 27*mm, madison_text)
                
                # Brookfield address and phone inline
                brookfield_text = "18525 W. Bluemound Rd,Brookfield WI 53045    262-395-7100"
                canvas.drawRightString(page_width - 20*mm, page_height - 34*mm, brookfield_text)
                
                canvas.restoreState()
                
                # Footer
                canvas.saveState()
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(colors.black)
                
                # Footer content
                footer_y = 15*mm  # Restored to original position
                
                # Left side - Company name
                canvas.drawString(20*mm, footer_y, "Div. Allen Construction Services, Inc.")
                
                # Center - Page number
                page_num = canvas.getPageNumber()
                canvas.drawCentredString(page_width/2, footer_y, f"{page_num}")
                
                # Right side - Date
                from datetime import datetime
                current_date = datetime.now().strftime("%m/%d/%Y")
                canvas.drawRightString(page_width - 20*mm, footer_y, f"Date: {current_date}")
                
                canvas.restoreState()
            except Exception as e:
                print(f"Header/Footer error: {e}")  # Debug
                pass  # Continue without header/footer if there's an error
        
        # Create custom styles
        # Main section title with grey background box
        main_section_box_style = ParagraphStyle(
            'MainSectionBox',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=8,  # Increased spacing to prevent content overlap
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            backColor=colors.lightgrey,
            borderWidth=0,  # Removed border
            borderPadding=4  # Reduced padding to make it thinner
        )
        
        # Section heading with thick gray underline
        section_heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=0,  # No space between title and line for tighter spacing
            spaceBefore=15,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderColor=colors.grey,
            borderPadding=0,
            leading=14  # Tight line height
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        # Key-value pair styles
        key_style = ParagraphStyle(
            'KeyStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            leftIndent=0
        )
        
        value_style = ParagraphStyle(
            'ValueStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica',
            leftIndent=20
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
        
        # Helper function to add section with underline
        def add_section_with_underline(story, title, content_items):
            """Add a section with title and thick gray underline, followed by key-value pairs"""
            # Add section title
            story.append(Paragraph(title, section_heading_style))
            
            # Add thick gray line under title using Table with border
            line_table = Table([['']], colWidths=[170*mm])
            line_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (0, 0), 4, colors.grey),  # Thicker line
                ('TOPPADDING', (0, 0), (0, 0), 0),  # No top padding
                ('BOTTOMPADDING', (0, 0), (0, 0), 0),  # No bottom padding
                ('LEFTPADDING', (0, 0), (0, 0), 0),  # No left padding
                ('RIGHTPADDING', (0, 0), (0, 0), 0),  # No right padding
            ]))
            story.append(line_table)
            # Add larger spacer after the line for better spacing
            story.append(Spacer(1, 4*mm))
            
            # Add content items as key-value pairs inline
            for key, value in content_items:
                if value:  # Only add if value exists
                    # Combine label and value on same line
                    inline_text = f"<b>{key}:</b> {str(value)}"
                    story.append(Paragraph(inline_text, value_style))
                    story.append(Spacer(1, 1*mm))
            
            story.append(Spacer(1, 10*mm))
        
        # Build PDF content
        story = []
        
        story.append(Spacer(1, -10*mm))
        story.append(Paragraph("Project Information", main_section_box_style))
        
        # Billing Information Section
        billing_info = [
            ('Builder', ''),
            ('Date', job.datesold.strftime('%m/%d/%Y') if job.datesold else ''),
            ('Customer', f"{job.customer.first_name} {job.customer.last_name}" if job.customer else ''),
            ('Address', f"{job.customer.address or ''}, {job.customer.city or ''}, {job.customer.state or ''} {job.customer.zip or ''}".strip(', ') if job.customer else ''),
            ('Phone', job.customer.home_phone if job.customer else ''),
        ]
        
        add_section_with_underline(story, "Billing Information", billing_info)
        
        # Job Contact Information Section
        job_contact_info = [
            ('Job Code', job.job_code or ''),
            ('Job Type', job.jobtype.name if job.jobtype else ''),
            ('Description', job.job_description or ''),
            ('Name', f"{job.customer.first_name} {job.customer.last_name}" if job.customer else ''),
            ('Address', f"{job.customer.address or ''}, {job.customer.city or ''}, {job.customer.state or ''} {job.customer.zip or ''}".strip(', ') if job.customer else ''),
            ('Phone', job.customer.home_phone if job.customer else ''),
            ('Sales Person', f"{job.soldby.first_name} {job.soldby.last_name}" if job.soldby else ''),
            ('Phone', job.soldby.phone if hasattr(job.soldby, 'phone') and job.soldby else ''),
            ('Carpenter', f"{job.carpenter.first_name} {job.carpenter.last_name}" if job.carpenter else ''),
            ('Phone', job.carpenter.phone if hasattr(job.carpenter, 'phone') and job.carpenter else ''),
            ('Week of', job.datesold.strftime('%m/%d/%Y') if job.datesold else ''),
            ('Permit Township', ''),
        ]
        
        add_section_with_underline(story, "Job Contact Information", job_contact_info)
        
        # 2. PRODUCT PROPOSED SECTION (only if primary product quote exists)
        primary_product_quote = job.product_quotes.filter(is_primary=True).first()
        if primary_product_quote:
            story.append(PageBreak())
            story.append(Spacer(1, -10*mm))
            story.append(Paragraph("Product Proposed", main_section_box_style))
            
            quote = primary_product_quote
            story.append(Paragraph(f"<b>Product Quote:</b> {quote.name}", normal_style))
            story.append(Spacer(1, 3*mm))
            
            # Group line items by category
            categories_data = group_line_items_by_category(quote.line_items.all(), quote.adhoc_line_items.all())
            
            for category in categories_data:
                # Check if this category should be hidden (case/whitespace-insensitive)
                category_key = f"{quote.name}_{category['name']}".strip().lower()
                is_hidden = category_key in hidden_categories
                # print(f"Product category: {category['name']}, quote: {quote.name}, key: {category_key}, is_hidden: {is_hidden}")
                                    
                if is_hidden:
                    story.append(Paragraph(f"<b>{category['name']}</b>", bold_style))
                    story.append(Spacer(1, 2*mm))
                    story.append(Paragraph(f"Section Subtotal: {category['subtotal']}", subtotal_style))
                else:
                    # Category header (only show when not hidden)
                    story.append(Paragraph(f"<b>{category['name']}</b>", bold_style))
                    story.append(Spacer(1, 2*mm))
                    
                    # If visible, show full product list
                    # Create table for items
                    table_data = [['Part Number', 'QTY', 'Description']]
                    
                    for item_type, item in category['items']:
                        if item_type == 'product':
                            part_no = item.product.part_no or ''
                            description = str(item.product.description or '')
                            # Pull job-level note for this product line, if any
                            note_text = ''
                            try:
                                note_obj = JobQuoteProductNotes.objects.filter(job=job, line_item=item).first()
                                if note_obj and note_obj.note:
                                    note_text = str(note_obj.note)
                            except Exception:
                                note_text = ''
                        else:
                            part_no = item.adhoc.part_no or ''
                            description = str(item.adhoc.description or '')
                            note_text = ''

                        # Description cell with optional note on a new line
                        from reportlab.platypus import Paragraph
                        desc_markup = description
                        if note_text:
                            desc_markup = f"{description}<br/><font size='8'><i>Note: {note_text}</i></font>"
                        desc_cell = Paragraph(desc_markup, styles['Normal'])

                        table_data.append([
                            part_no,
                            str(item.quantity),
                            desc_cell
                        ])
                    
                    # Add subtotal row
                    # table_data.append(['', '', f"Section Subtotal: {category['subtotal']}"])
                    
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
                story.append(Paragraph(f"Tax: {format_currency(tax_amount)}", total_style))
            
            # Total with Tax
            story.append(Paragraph(f"Total: {format_currency(total_with_tax)}", total_style))
        
        # 3. SITEWORK SECTION (only if primary sitework quote exists)
        primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
        
        if primary_sitework_quote:
            sitework_quote = primary_sitework_quote
            story.append(PageBreak())
            story.append(Spacer(1, -10*mm))
            story.append(Paragraph("Sitework Customer Copy", main_section_box_style))
            
            # Calculate prices using the same logic as sitework quote PDF
            from sitework.models import SiteworkQuoteLine, SiteworkCat
            SiteworkQuoteLine.objects.calc_price(sitework_quote.id)
            
            # Process sitework categories - same format as sitework quote PDF
            for category in SiteworkCat.objects.order_by('orderby'):
                # Get items with quantity > 0 for this category
                # Use quote object directly to ensure proper relationship
                # Refresh queryset after calc_price to get updated quantities
                items = list(SiteworkQuoteLine.objects.filter(
                    cat=category, 
                    quote=sitework_quote, 
                    quantity__gt=0
                ).order_by('orderby'))
                
                if not items:
                    continue
                
                # Calculate category total (always needed for Site Work Total)
                category_total = 0.0
                for item in items:
                    if item.editallowance == '1':
                        price = (item.allowance / item.profit) if item.profit > 0 else 0.0
                    else:
                        price = (item.quantity * item.unitamount) + item.basecost
                    if item.quantity > 0 and item.calckey == 558:
                        price = 100.0
                    category_total += float(price)
                
                # Category header
                story.append(Paragraph(f"<b>{category.name.upper()}</b>", bold_style))
                story.append(Spacer(1, 2*mm))
                
                if hide_sitework_prices:
                    # Show only item descriptions (no prices)
                    for item in items:
                        qty = str(item.quantity)
                        unit = item.quantitydesc or 'EA'
                        desc = item.workdesc or ''
                        desc_with_qty = f"{qty} {unit} {desc}"
                        story.append(Paragraph(desc_with_qty, normal_style))
                else:
                    # Category header with column headers on same line - uppercase (matching sitework quote PDF format)
                    col_widths = [100*mm, 25*mm, 25*mm, 25*mm]
                    
                    # Build combined table with header row and data rows
                    table_data = []
                    
                    # Header row: Category name on left, Base/Unit/Price on right
                    table_data.append([
                        Paragraph(f"<b>{category.name.upper()}</b>", normal_style),
                        'Base',
                        'Unit',
                        'Price'
                    ])
                    
                    # category_total already calculated above, reuse it
                    for item in items:
                        # Calculate price (for display only, total already calculated)
                        if item.editallowance == '1':
                            price = (item.allowance / item.profit) if item.profit > 0 else 0.0
                        else:
                            price = (item.quantity * item.unitamount) + item.basecost
                        
                        # BILLCODE override
                        if item.quantity > 0 and item.calckey == 558:
                            price = 100.0
                        
                        # Format values - combine qty, unit, and description inline in first column
                        qty = str(item.quantity)
                        unit = item.quantitydesc or 'EA'
                        desc = item.workdesc or ''
                        # Combine qty, unit, and description inline (matching sitework quote PDF format)
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
                    # Category Subtotal below table (matching sitework quote PDF format)
                    story.append(Spacer(1, 2*mm))
                    story.append(Paragraph(f"Category Sub Total: {category_total:.2f}", subtotal_style))
                
                story.append(Spacer(1, 8*mm))
            
            # Calculate totals (always needed)
            sitework_total = 0.0
            contingency_pct = 0.05
            overhead_pct = 0.28
            
            # Recalculate total from all categories
            for category in SiteworkCat.objects.order_by('orderby'):
                items = list(SiteworkQuoteLine.objects.filter(
                    cat=category, 
                    quote=sitework_quote, 
                    quantity__gt=0
                ).order_by('orderby'))
                
                for item in items:
                    if item.editallowance == '1':
                        price = (item.allowance / item.profit) if item.profit > 0 else 0.0
                    else:
                        price = (item.quantity * item.unitamount) + item.basecost
                    if item.quantity > 0 and item.calckey == 558:
                        price = 100.0
                    sitework_total += float(price)
            
            contingency = sitework_total * contingency_pct
            overhead = sitework_total * overhead_pct
            final_total = sitework_total + contingency + overhead
            
            # Display totals based on price visibility
            story.append(Spacer(1, 5*mm))
            total_style = ParagraphStyle(
                'TotalStyle',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=0,
                textColor=colors.black,
                alignment=TA_RIGHT,
                fontName='Helvetica-Bold'
            )
            
            if hide_sitework_prices:
                # When prices are hidden, show only Site Work Total
                story.append(Paragraph(f"Site Work Total: {final_total:.2f}", total_style))
            else:
                # When prices are shown, show breakdown: Sub Total, Contingency, Overhead, Total
                summary_data = [
                    [f"Site Work Sub Total: {sitework_total:.2f}"],
                    [f"Contingency Fund: {contingency:.2f}"],
                    [f"Over Head Fee: {overhead:.2f}"],
                    [f"Site Work Total: {final_total:.2f}"]
                ]
                
                summary_table = Table(summary_data, colWidths=[175*mm])
                summary_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (0, -1), 0),
                    ('RIGHTPADDING', (0, 0), (0, -1), 0),
                ]))
                
                story.append(summary_table)
        else:
            print("No sitework quote found for this job")
        
        # 4. CONTRACT SUMMARY
        story.append(PageBreak())
        story.append(Spacer(1, -10*mm))
        story.append(Paragraph("Contract Summary", main_section_box_style))
        story.append(Spacer(1, 3*mm))
        
        # Calculate total contract amount: Product Quote Total + Sitework Total + Change Orders
        total_contract_amount = Decimal('0')
        product_total = Decimal('0')
        sitework_final_total = Decimal('0')
        change_orders_total = Decimal('0')
        
        # Add product quote total
        if primary_product_quote:
            quote = primary_product_quote
            quote_total = quote.get_total_with_tax()
            product_total = Decimal(str(quote_total))
            total_contract_amount += product_total
        
        # Add sitework total
        if primary_sitework_quote:
            sitework_total = 0.0
            contingency_pct = 0.05
            overhead_pct = 0.28
            
            for category in SiteworkCat.objects.order_by('orderby'):
                items = list(SiteworkQuoteLine.objects.filter(
                    cat=category, 
                    quote=primary_sitework_quote, 
                    quantity__gt=0
                ).order_by('orderby'))
                
                for item in items:
                    if item.editallowance == '1':
                        price = (item.allowance / item.profit) if item.profit > 0 else 0.0
                    else:
                        price = (item.quantity * item.unitamount) + item.basecost
                    if item.quantity > 0 and item.calckey == 558:
                        price = 100.0
                    sitework_total += float(price)
            
            contingency = sitework_total * contingency_pct
            overhead = sitework_total * overhead_pct
            sitework_final_total = Decimal(str(sitework_total + contingency + overhead))
            total_contract_amount += sitework_final_total
        
        # Add change orders total (only include change orders with amounts)
        change_orders = job.change_orders.all()
        for co in change_orders:
            if co.amount is not None:
                change_orders_total += co.amount
        total_contract_amount += change_orders_total
        
        # Project Description Section
        # Use consistent first column width across all sections to align with "Total Attachments"
        available_width = 170*mm
        first_col_width = 60*mm  # Match "Total Attachments" column width
        second_col_width = available_width - first_col_width
        
        # Create title table to align with content table
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=2*mm,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold',
            leftIndent=0
        )
        title_table = Table([['Project Description']], colWidths=[available_width])
        title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(title_table)
        story.append(Spacer(1, 2*mm))
        
        # Calculate original sale amount (product + sitework without change orders)
        original_sale_amount = product_total + sitework_final_total
        
        desc_data = [
            ['Project ID:', job.job_code or 'N/A'],
            ['Original Sale:', format_currency(original_sale_amount)],
            ['Change Orders:', format_currency(change_orders_total)],
        ]
        
        if primary_product_quote:
            quote = primary_product_quote
            product_total_with_tax = quote.get_total_with_tax()
            desc_data.append(['Product Total:', format_currency(product_total_with_tax)])
        
        if primary_sitework_quote:
            desc_data.append(['Site Work Total:', format_currency(sitework_final_total)])
        
        desc_data.append(['Current Project Total:', format_currency(total_contract_amount)])
        
        desc_table = Table(desc_data, colWidths=[first_col_width, second_col_width])
        desc_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),  # No left padding to align with title
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            # Make Project ID (row 0) bold
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            # Make Original Sale, Change Orders, Product Total, Site Work Total regular font
            ('FONTNAME', (0, 1), (0, -2), 'Helvetica'),
            # Make Current Project Total (last row) bold
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        story.append(desc_table)
        story.append(Spacer(1, 5*mm))
        
        # Project Details Section
        title_table = Table([['Project Details']], colWidths=[available_width])
        title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(title_table)
        story.append(Spacer(1, 2*mm))
        
        # Use consistent first column width to align with "Total Attachments"
        # Remaining width split among 3 columns
        remaining_width = available_width - first_col_width
        col2_width = remaining_width * 0.4  # 40% of remaining
        col3_width = remaining_width * 0.3  # 30% of remaining
        col4_width = remaining_width * 0.3  # 30% of remaining
        
        details_data = [
            ['Job Type:', job.jobtype.name if job.jobtype else 'N/A', 'Date Sold:', job.datesold.strftime('%m/%d/%Y') if job.datesold else 'N/A'],
            ['Start Date:', job.startdate.strftime('%m/%d/%Y') if job.startdate else 'N/A', 'End Date:', job.completDate.strftime('%m/%d/%Y') if job.completDate else 'N/A'],
            ['Carpenter Assigned:', f"{job.carpenter.first_name} {job.carpenter.last_name}" if job.carpenter else 'N/A', 'Email:', job.carpenter.email if job.carpenter else ''],
            ['Cell:', '', 'Sales Designer:', f"{job.soldby.first_name} {job.soldby.last_name}" if job.soldby else 'N/A'],
            ['Sales Designer Email:', job.soldby.email if job.soldby else 'N/A', 'Work Phone:', job.customer.work_phone if job.customer.work_phone else 'N/A'],
        ]
        
        details_table = Table(details_data, colWidths=[first_col_width, col2_width, col3_width, col4_width])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Label columns left-aligned
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),  # Value columns left-aligned
            ('ALIGN', (2, 0), (2, -1), 'LEFT'),  # Label columns left-aligned
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),  # Value columns left-aligned
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # First column (labels) bold
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  # Third column (labels) bold
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),  # No left padding to align with title
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(details_table)
        story.append(Spacer(1, 5*mm))
        
        # Payment Schedule Section
        title_table = Table([['Payment Schedule']], colWidths=[available_width])
        title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(title_table)
        story.append(Spacer(1, 2*mm))
        
        payment_data = [
            ['Deposit Payment:', ''],
            ['Start Payment:', ''],
            ['Progress Payment 1 ADJ:', ''],
            ['Progress Payment 2:', ''],
            ['Progress Payment 3:', ''],
        ]
        
        payment_table = Table(payment_data, colWidths=[first_col_width, second_col_width])
        payment_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),  # No left padding to align with title
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(payment_table)
        story.append(Spacer(1, 5*mm))
        
        # Signatures Section
        title_table = Table([['Signatures']], colWidths=[available_width])
        title_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(title_table)
        story.append(Spacer(1, 2*mm))
        
        # Create signature lines matching the image format exactly
        date_line = '_____________________________________    _____ / _____ / _____'
        
        signature_data = [
            ['Total Attachments:', ''],  # Row 0: One line
            ['Plans Dated:', date_line],  # Row 1: Date only (no line after)
            ['Accepted By:', date_line],  # Row 2: Accepted By - date line
            # ['', date_line], # Row 3: Accepted By - signature line (date only)
            ['Sales Person:', date_line],  # Row 4: Sales Person - date only (no line after)
        ]
        
        signature_table = Table(signature_data, colWidths=[first_col_width, second_col_width])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),  # No left padding to align with title
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),  # Increased from 3 to 6 for more space
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),  # Increased from 3 to 6 for more space
            # Extra space between Total Attachments and Plans Dated
            ('TOPPADDING', (0, 1), (-1, 1), 12),  # Row 1 (Plans Dated) - extra top padding
            # Add bottom border to signature lines with consistent bold line
            ('LINEBELOW', (1, 0), (1, 0), 1.5, colors.black),  # Total Attachments - bolder line
        ]))
        story.append(signature_table)
        story.append(Spacer(1, 15*mm))
        
        # 5. CUSTOMER INFORMATION & TERMS (Force to same page)
        # Add page break to ensure this starts on a new page
        story.append(PageBreak())
        
        # Customer Information section
        story.append(Spacer(1, -10*mm))
        story.append(Paragraph("Customer Information", main_section_box_style))
        
        if job.customer:
            # Create customer data with Job Code and Job Type on one line, Customer and Address on another line
            customer_data = [
                ['Job Code:', job.job_code or 'N/A', 'Job Type:', job.jobtype.name if job.jobtype else 'N/A'],
                ['Customer:', f"{job.customer.first_name} {job.customer.last_name}", 'Address:', f"{job.customer.address or 'N/A'}, {job.customer.city or 'N/A'}, {job.customer.state or 'N/A'} {job.customer.zip or 'N/A'}"],
            ]
            
            customer_table = Table(customer_data, colWidths=[25*mm, 60*mm, 25*mm, 60*mm])
            customer_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 5*mm))
        
        # Terms and Conditions section (on same page)
        # Add a line between customer info and terms
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Terms and Conditions of Sale", main_section_box_style))
        
        terms_text = """
        This agreement sets forth the entire agreement between the parties and any and all prior agreements, warranties or representations
        made by either party are superseded by this contract. Any changes shall be made in writing and properly signed.
        Commencement and completion dates shall be deemed approximate and are subject to change. Allen Kitchen & Bath shall notify
        customer of changes as promptly as possible.<br/><br/>
        
        Allen Kitchen & Bath shall not be responsible for delays beyond its control.<br/><br/>
        
        <b>Changes and cancellations:</b> Many of the materials ordered for this project are custom and non-stock. Therefore, the return or
        cancellation of any item may be subject to restocking fees or may not be returnable for credit. Such restocking fees shall be
        consistent with the fees Allen Kitchen & Bath incurs from it's vendors. Some products, such as cabinets, are not returnable and are
        not cancelable after we place the order with our vendor.<br/><br/>
        
        <b>Limited warranty.</b> Each product sold in conjunction with this project is subject to the individual manufacturers warranty. Allen
        Kitchen & Bath warrants it's work to be of good quality, be free of defects and provide proper function for a period of two years from
        the date of installation. If service is required, it shall be at the sole discretion of Allen Kitchen & Bath or manufacturer to repair or
        replace said item or work. All warranties shall be void if product is misused, abused, improperly stored or installed by others not
        under the control of Allen Kitchen & Bath. Customer bears responsibility to inspect materials for defects prior to installation if install
        is not provided by Allen Kitchen & Bath.<br/><br/>
        
        <b>Storage.</b> Should customer delay the project or order custom products in advance of need, customer agrees to pay for 90% of such
        product within 10 days of receipt by Allen Kitchen & Bath. Allen Kitchen & Bath agrees to store product for a reasonable time and as
        space allows without charge to the customer.<br/><br/>
        
        <b>LIEN RIGHTS.</b> AS REQUIRED BY WISCONSIN LIEN LAW, CONTRACTOR HEREBY NOTIFIES OWNER THAT PERSONS OR
        COMPANIES FURNISHING LABOR OR MATERIALS FOR THE CONSTRUCTION ON OWNER'S LAND MAY HAVE LIEN RIGHTS
        ON THE OWNER'S LAND AND BUILDINGS IF NOT PAID. THOSE ENTITLED TO LIEN RIGHTS, IN ADDITION TO THE
        UNDERSIGNED CONTRACTOR, ARE THOSE WHO CONTRACT DIRECTLY WITH THE OWNER OR THOSE WHO GIVE THE
        OWNER NOTICE WITHIN 60 DAYS AFTER THEY FIRST FURNISH LABOR OR MATERIALS FOR THE CONSTRUCTION.
        ACCORDINGLY, OWNER MAY RECEIVE NOTICE FROM THOSE WHO FURNISH LABOR OR MATERIALS FOR THE
        CONSTRUCTION, AND SHOULD PROVIDE A COPY OF EACH NOTICE RECEIVED TO HIS MORTGAGE LENDER, IF ANY.
        CONTRACTOR AGREES TO COOPERATE WITH THE OWNER AND HIS LENDER, IF ANY, TO SEE THAT ALL POTENTIAL
        LIEN CLAIMANTS ARE DULY PAID.<br/><br/>
        
        <b>Insurance.</b> Allen Kitchen & Bath agrees to maintain Worker's Compensation Insurance, unemployment insurance and general liability
        insurance for the duration of this project. Customer agrees to maintain fire, tornado, theft and other necessary insurance to cover
        materials and work on premises.<br/><br/>
        
        <b>Change orders.</b> Should a change in this contract be necessary it will be made in writing and signed by both parties. Change orders
        are payable when issued.<br/><br/>
        
        <b>Payments.</b> Customer agrees to make prompt payment for this project according to the schedule set forth above. Payments shall be
        made within 3 days of completion of a phase and after notification of payment due by Allen Kitchen & Bath. If payments are not
        received as specified Allen Kitchen & Bath may suspend work until payments are current.<br/><br/>
        
        Accounts more than 30 days past due are subject to a service fee of 1% per month. Should it be necessary to employ services for
        collection customer shall be responsible for those collection costs.<br/><br/>
        
        This sale is based on terms and conditions specified on this and all pages of this sales contract.
        """
        
        # Create a style for terms text with proper formatting
        terms_style = ParagraphStyle(
            'TermsStyle',
            parent=styles['Normal'],
            fontSize=8,  # Reduced from 9 to 8
            spaceAfter=1,  # Reduced from 2 to 1
            spaceBefore=0,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica',
            leading=9  # Reduced from 11 to 9 for tighter spacing
        )
        
        story.append(Paragraph(terms_text, terms_style))
        story.append(Spacer(1, 3*mm))  # Added space between paragraph and initials
        
        # Signature fields as shown in the image
        signature_text = "Initial:___________ Initial:___________"
        
        # Create a centered style for initials with smaller font
        initials_style = ParagraphStyle(
            'InitialsStyle',
            parent=styles['Normal'],
            fontSize=10,  # Smaller font
            spaceAfter=0,
            spaceBefore=0,
            textColor=colors.black,
            alignment=TA_CENTER,  # Center alignment
            fontName='Helvetica'
        )
        
        story.append(Paragraph(signature_text, initials_style))
        
        
        # Build PDF with header and footer
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Return PDF response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"job_{job.job_code}_contract.pdf"
        
        # Check if this is a preview request (opened in new tab) or download request
        if request.GET.get('preview') == 'true':
            # For preview, show inline in browser
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        else:
            # For download, force attachment
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # If PDF generation fails, redirect to existing working print preview
        import traceback
        print(f"PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('job:job_print_preview', args=[job_id]))


def purchase_order_pdf_generate(request, job_id, po_id):
    """Generate PDF for purchase order with same header/footer as job print preview"""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
        return HttpResponseRedirect(reverse('job:job_purchase_order_detail', args=[job_id, po_id]))
    
    try:
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document with A4 page size and margins (same as job print preview)
        doc = SimpleDocTemplate(
            pdf_buffer, 
            pagesize=A4,
            leftMargin=20*mm,
            rightMargin=20*mm,
            topMargin=50*mm,  # Same as job print preview
            bottomMargin=30*mm  # Same as job print preview
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Header and Footer drawing functions (same as job print preview)
        def draw_header_footer(canvas, doc):
            """Draw header and footer on each page - same as job print preview"""
            try:
                # Get page dimensions
                page_width, page_height = A4
                
                # Header
                canvas.saveState()
                
                # Draw logo (same as job print preview)
                logo_path = os.path.join(settings.BASE_DIR, 'crm', 'static', 'crm', 'nologo.png')
                if os.path.exists(logo_path):
                    try:
                        # Logo dimensions and position (same as job print preview)
                        logo_width = 160
                        logo_height = 60
                        logo_x = 20*mm
                        logo_y = (page_height - 15*mm) - logo_height
                        
                        # Draw logo
                        canvas.drawImage(logo_path, logo_x, logo_y, width=logo_width, height=logo_height)
                    except Exception as e:
                        print(f"Logo error: {e}")
                        pass
                
                # Header text (same as job print preview)
                canvas.setFont("Helvetica-Bold", 10)
                canvas.setFillColor(colors.black)
                
                # Toll-free number
                phone_num = "800-227-8575"
                canvas.drawRightString(page_width - 20*mm, page_height - 20*mm, phone_num)
                
                # Madison address and phone inline
                madison_text = "2219 S. Stoughton Rd, Madison WI 53716    608-274-9933"
                canvas.drawRightString(page_width - 20*mm, page_height - 27*mm, madison_text)
                
                # Brookfield address and phone inline
                brookfield_text = "18525 W. Bluemound Rd,Brookfield WI 53045    262-395-7100"
                canvas.drawRightString(page_width - 20*mm, page_height - 34*mm, brookfield_text)
                
                canvas.restoreState()
                
                # Footer (same as job print preview)
                canvas.saveState()
                canvas.setFont("Helvetica", 9)
                canvas.setFillColor(colors.black)
                
                # Footer content
                footer_y = 15*mm
                
                # Left side - Company name
                canvas.drawString(20*mm, footer_y, "Div. Allen Construction Services, Inc.")
                
                # Center - Page number
                page_num = canvas.getPageNumber()
                canvas.drawCentredString(page_width/2, footer_y, f"{page_num}")
                
                # Right side - Date
                from datetime import datetime
                current_date = datetime.now().strftime("%m/%d/%Y")
                canvas.drawRightString(page_width - 20*mm, footer_y, f"Date: {current_date}")
                
                canvas.restoreState()
            except Exception as e:
                print(f"Header/Footer error: {e}")
                pass
        
        # Get confirmed items
        confirmed_items = purchase_order.items.filter(confirmed=True).order_by('ordered_date', 'part_number')
        
        # Create custom styles (similar to job print preview but slightly smaller)
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=8,  # Smaller font to fit in rows
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontSize=8,  # Smaller font
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        bold_right_style = ParagraphStyle(
            'CustomBoldRight',
            parent=styles['Normal'],
            fontSize=8,  # Smaller font
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_RIGHT,
            fontName='Helvetica-Bold'
        )
        
        note_style = ParagraphStyle(
            'NoteStyle',
            parent=styles['Normal'],
            fontSize=7,  # Even smaller for notes
            spaceAfter=2,
            textColor=colors.grey,
            alignment=TA_LEFT,
            fontName='Helvetica-Oblique',
            leftIndent=10
        )
        
        # Main section title style (similar to job print preview)
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
        
        # Build PDF content
        story = []
        
        # Add title
        story.append(Spacer(1, -10*mm))
        story.append(Paragraph("Purchase Order", main_section_box_style))
        story.append(Spacer(1, 5*mm))
        
        # Purchase Order Information
        po_info_style = ParagraphStyle(
            'POInfo',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=3,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        # Note paragraph style (larger font)
        note_paragraph_style = ParagraphStyle(
            'NoteParagraph',
            parent=styles['Normal'],
            fontSize=10,  # Larger font for the note paragraph
            spaceAfter=4,
            textColor=colors.black,
            alignment=TA_LEFT
        )
        
        story.append(Paragraph(f"<b>PO Number:</b> {purchase_order.po_number}", po_info_style))
        
        # Build vendor line with address information
        vendor = purchase_order.vendor
        vendor_name = vendor.vendor_name or ''
        
        # Collect address components if they exist
        address_parts = []
        if vendor.address1:
            address_parts.append(vendor.address1)
        if vendor.city:
            address_parts.append(vendor.city)
        if vendor.state:
            address_parts.append(vendor.state)
        if vendor.zip:
            address_parts.append(vendor.zip)
        
        # If address exists, append it to vendor name with non-breaking spaces and commas between address parts; otherwise just show vendor name
        if address_parts:
            address_string = ', '.join(address_parts)
            # Use &nbsp; (non-breaking space) so spaces render properly in PDF (4 spaces)
            vendor_line = f"{vendor_name}&nbsp;&nbsp;&nbsp;&nbsp;{address_string}"
        else:
            vendor_line = vendor_name
        
        story.append(Paragraph(f"<b>Vendor:</b> {vendor_line}", po_info_style))
        
        # Build Ship to line with location (Store) information
        if purchase_order.location:
            store = purchase_order.location
            ship_to_parts = [store.store_name or '']
            
            # Collect address components if they exist
            if store.address1:
                ship_to_parts.append(store.address1)
            if store.city:
                ship_to_parts.append(store.city)
            if store.state:
                ship_to_parts.append(store.state)
            if store.zipcode:
                ship_to_parts.append(store.zipcode)
            
            # If address exists, append it to store name with non-breaking spaces and commas
            if len(ship_to_parts) > 1:
                ship_to_string = ', '.join(part for part in ship_to_parts[1:] if part.strip())
                ship_to_line = f"{ship_to_parts[0]}&nbsp;&nbsp;&nbsp;&nbsp;{ship_to_string}"
            else:
                ship_to_line = ship_to_parts[0] if ship_to_parts else ''
            
            story.append(Paragraph(f"<b>Ship to:</b> {ship_to_line}", po_info_style))
        
        if purchase_order.notes:
            story.append(Paragraph(f"<b>Notes:</b> {purchase_order.notes}", po_info_style))
        story.append(Spacer(1, 5*mm))
        
        # Create table for confirmed items
        if confirmed_items.exists():
            from reportlab.platypus import Table, TableStyle
            
            # Table header
            table_data = [['QTY', 'Part Number', 'Description', 'Unit Price', 'Total Price']]
            
            total_po_price = 0
            
            # Create right-aligned style for prices (non-bold)
            price_style = ParagraphStyle(
                'PriceStyle',
                parent=styles['Normal'],
                fontSize=8,
                spaceAfter=4,
                textColor=colors.black,
                alignment=TA_RIGHT
            )
            
            # Add confirmed items
            for item in confirmed_items:
                # Format unit price
                unit_price_str = format_currency(item.cost) if item.cost else '-'
                unit_price = Paragraph(unit_price_str, price_style)
                
                # Calculate total price
                total_price = item.total_cost
                total_po_price += total_price
                total_price_str = format_currency(total_price) if total_price > 0 else '-'
                total_price_para = Paragraph(total_price_str, price_style)
                
                # Create description cell (allow wrapping)
                description = item.description or '-'
                desc_cell = Paragraph(description, normal_style)
                
                # Add item row
                table_data.append([
                    str(item.quantity),
                    item.part_number or '-',
                    desc_cell,
                    unit_price,
                    total_price_para
                ])
                
                # Add note row if note exists (in a separate row spanning all columns)
                if item.note and item.note.strip():
                    note_cell = Paragraph(f"<i>Note: {item.note}</i>", note_style)
                    # Create a row with note in first column (will span all 5 columns via SPAN)
                    note_row = [note_cell, '', '', '', '']
                    table_data.append(note_row)
            
            # Add total row
            table_data.append([
                '',
                '',
                Paragraph('<b>Total Purchase Order Price:</b>', bold_style),
                '',
                Paragraph(f'<b>{format_currency(total_po_price)}</b>', bold_right_style)
            ])
            
            # Create table with column widths
            # A4 width is 210mm, margins are 20mm each side = 170mm usable width
            # Distribute: QTY (15mm), Part Number (30mm), Description (80mm), Unit Price (20mm), Total Price (25mm)
            items_table = Table(table_data, colWidths=[15*mm, 30*mm, 80*mm, 20*mm, 25*mm])
            
            # Calculate total row index (last row)
            total_row_idx = len(table_data) - 1
            
            # Build table style
            table_style = [
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (3, 1), (4, -1), 'RIGHT'),  # Right align Unit Price (col 3) and Total Price (col 4) from row 1 to end
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),  # Smaller font
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('FONTNAME', (0, 0), (4, 0), 'Helvetica-Bold'),  # Header row
                ('FONTSIZE', (0, 0), (4, 0), 9),  # Slightly larger for header
                # Ensure total row price column is right-aligned
                ('ALIGN', (4, total_row_idx), (4, total_row_idx), 'RIGHT'),  # Right align only the price column in total row
                # Remove all borders from the entire table - use INNERGRID and BOX with 0 width
                ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),  # Remove all inner grid lines
                ('BOX', (0, 0), (-1, -1), 0, colors.white),  # Remove outer box borders
                ('GRID', (0, 0), (-1, -1), 0, colors.white),  # No grid lines
                ('LINEBELOW', (0, 0), (-1, -1), 0, colors.white),  # No bottom lines
                ('LINEABOVE', (0, 0), (-1, -1), 0, colors.white),  # No top lines
                ('LINELEFT', (0, 0), (-1, -1), 0, colors.white),  # No left lines
                ('LINERIGHT', (0, 0), (-1, -1), 0, colors.white),  # No right lines
                ('LINEAFTER', (0, 0), (-1, -1), 0, colors.white),  # No vertical lines between columns
            ]
            
            # Add SPAN for note rows to span all columns
            # Track which rows are note rows (they come after each item row)
            row_idx = 1  # Start after header (row 0)
            for item in confirmed_items:
                row_idx += 1  # Item row
                # Check if this item has a note
                if item.note and item.note.strip():
                    # Span note cell across all 5 columns (columns 0-4)
                    table_style.append(('SPAN', (0, row_idx), (4, row_idx)))
                    row_idx += 1  # Note row
            
            items_table.setStyle(TableStyle(table_style))
            
            story.append(items_table)
        else:
            # No confirmed items
            story.append(Paragraph("No confirmed items in this purchase order.", normal_style))
        
        # Add spacing before the note paragraph
        story.append(Spacer(1, 5*mm))
        
        # Add note paragraph below the table
        note_paragraph_text = (
            "This material is for resale under Wisconsin Permit #335468-01. "
            "Please do not add sales tax. Please confirm receipt of order, ship date and costs within 3 days"
        )
        story.append(Paragraph(note_paragraph_text, note_paragraph_style))
        
        # Build PDF with header and footer
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Get PDF bytes
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Return PDF response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"purchase_order_{purchase_order.po_number}.pdf"
        
        # For preview, show inline in browser
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # If PDF generation fails, redirect back to detail page
        import traceback
        print(f"Purchase Order PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('job:job_purchase_order_detail', args=[job_id, po_id]))


def sales_invoice_pdf_generate(request, job_id):
    """Generate PDF invoice for sales with same header/footer as job print preview"""
    job = get_object_or_404(Job, id=job_id)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfgen import canvas
        from io import BytesIO
        import os
        from django.conf import settings
        from collections import defaultdict
        from decimal import Decimal
    except ImportError:
        return HttpResponseRedirect(reverse('job:job_sales', args=[job_id]))
    
    try:
        # Get all sales for this job
        sales = job.sales.all().select_related('product_code').order_by('-sale_date', '-created_at')
        
        # Group sales by product_code (same logic as in job_sales view)
        grouped_sales = defaultdict(lambda: {
            'sales': [],
            'total': Decimal('0.00'),
            'total_cost': Decimal('0.00'),
            'total_tax': Decimal('0.00'),
            'product_code': None,
            'tax': None,
            'sale_date': None,
        })
        for sale in sales:
            product_code_id = sale.product_code_id if sale.product_code else None
            product_code_key = product_code_id if product_code_id else 'no_code'
            
            if grouped_sales[product_code_key]['product_code'] is None:
                grouped_sales[product_code_key]['product_code'] = sale.product_code
                grouped_sales[product_code_key]['tax'] = sale.tax
                grouped_sales[product_code_key]['sale_date'] = sale.sale_date
            
            grouped_sales[product_code_key]['sales'].append(sale)
            grouped_sales[product_code_key]['total'] += sale.sale_amount
            if sale.cost_amount is not None:
                grouped_sales[product_code_key]['total_cost'] += sale.cost_amount
            if sale.tax_amount is not None:
                grouped_sales[product_code_key]['total_tax'] += sale.tax_amount
        
        # Convert to list
        grouped_sales_list = []
        for key, group_data in grouped_sales.items():
            grouped_sales_list.append({
                'product_code': group_data['product_code'],
                'tax': group_data['tax'],
                'sale_date': group_data['sale_date'],
                'total': group_data['total'],
                'total_cost': group_data['total_cost'],
                'total_tax': group_data['total_tax'],
                'sales': group_data['sales'],
                'count': len(group_data['sales'])
            })
        
        # Sort by product code
        from datetime import date
        grouped_sales_list.sort(key=lambda x: (x['product_code'].code if x['product_code'] else 'zzz', x['sale_date'] or date.min), reverse=True)
        
        # Calculate totals
        total_sales_amount = sum(group['total'] for group in grouped_sales_list)
        total_sales_cost = sum(group['total_cost'] for group in grouped_sales_list)
        total_sales_tax = sum(group['total_tax'] for group in grouped_sales_list)
        
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document with A4 page size and margins
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
        
        # Header and Footer drawing functions (reuse from job_pdf_generate)
        def draw_header_footer(canvas, doc):
            """Draw header and footer on each page"""
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
                
                from datetime import datetime
                current_date = datetime.now().strftime("%m/%d/%Y")
                canvas.drawRightString(page_width - 20*mm, footer_y, f"Date: {current_date}")
                
                canvas.restoreState()
            except Exception:
                pass
        
        # Build story
        story = []
        
        # Title with gray background (same as print preview)
        title_style = ParagraphStyle(
            'Title',
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
        story.append(Paragraph("Sales Invoice", title_style))
        story.append(Spacer(1, 10*mm))
        
        # Customer and Job Info
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        customer_info = []
        if job.customer:
            customer_info.append(f"<b>Customer:</b> {job.customer.first_name} {job.customer.last_name}")
            if job.customer.address:
                customer_info.append(f"<b>Address:</b> {job.customer.address}")
            if job.customer.city and job.customer.state:
                city_state = f"{job.customer.city}, {job.customer.state}"
                if job.customer.zip:
                    city_state += f" {job.customer.zip}"
                customer_info.append(city_state)
        else:
            if job.address:
                customer_info.append(f"<b>Job Address:</b> {job.address}")
            if job.city and job.state:
                city_state = f"{job.city}, {job.state}"
                if job.zip:
                    city_state += f" {job.zip}"
                customer_info.append(city_state)
        
        customer_info.append(f"<b>Job Code:</b> {job.job_code}")
        
        for info in customer_info:
            story.append(Paragraph(info, normal_style))
        
        story.append(Spacer(1, 10*mm))
        
        # Sales Table
        # Create styles for consistent formatting
        header_left_style = ParagraphStyle(
            'HeaderLeft',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        header_right_style = ParagraphStyle(
            'HeaderRight',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        )
        
        cell_style = ParagraphStyle(
            'Cell',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT
        )
        
        tax_style = ParagraphStyle(
            'Tax',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )
        
        amount_style = ParagraphStyle(
            'Amount',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )
        
        total_style = ParagraphStyle(
            'Total',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        total_amount_style = ParagraphStyle(
            'TotalAmount',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        )
        
        # Header row: cost and dollar tax columns right-aligned
        table_data = [[
            Paragraph('Product Code', header_left_style),
            Paragraph('Description', header_left_style),
            Paragraph('Cost', header_right_style),
            Paragraph('Amount', header_right_style),
            Paragraph('Tax', header_right_style),
            Paragraph('Code', header_right_style),
        ]]
        
        for group in grouped_sales_list:
            product_code = group['product_code'].code if group['product_code'] else '-'
            tax_code = group['tax'] or '-'
            total = float(group['total'])
            
            # Get description from first sale's comment or product code description
            description = '-'
            if group['sales']:
                first_sale = group['sales'][0]
                if first_sale.comment:
                    description = first_sale.comment
                elif group['product_code'] and group['product_code'].description:
                    description = group['product_code'].description
            
            amount_str = f"${total:,.2f}"
            cost_str = format_currency(group['total_cost'])
            tax_amt_str = format_currency(group['total_tax'])
            table_data.append([
                Paragraph(str(product_code), cell_style),
                Paragraph(str(description), cell_style),
                Paragraph(cost_str, tax_style),
                Paragraph(amount_str, amount_style),
                Paragraph(tax_amt_str, tax_style),
                Paragraph(str(tax_code), tax_style),
            ])
        
        # Total row
        total_amount_str = f"${float(total_sales_amount):,.2f}"
        total_cost_str = format_currency(total_sales_cost)
        total_tax_str = format_currency(total_sales_tax)
        table_data.append([
            Paragraph('TOTAL', total_style),
            Paragraph('', cell_style),
            Paragraph(total_cost_str, total_amount_style),
            Paragraph(total_amount_str, total_amount_style),
            Paragraph(total_tax_str, total_amount_style),
            Paragraph('', cell_style),
        ])
        
        sales_table = Table(table_data, colWidths=[28*mm, 52*mm, 24*mm, 26*mm, 22*mm, 18*mm])
        sales_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (5, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical alignment middle for better appearance
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # Line below header
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),  # Line above total
        ]))
        
        story.append(sales_table)
        
        # Build PDF
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Get PDF data
        pdf_data = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Create response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="sales_invoice_{job.job_code}.pdf"'
        
        return response
        
    except Exception as e:
        import traceback
        print(f"Sales Invoice PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('job:job_sales', args=[job_id]))


def change_orders_pdf_generate(request, job_id):
    """Generate PDF for change orders list with same header/footer as job print preview"""
    job = get_object_or_404(Job, id=job_id)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfgen import canvas
        from io import BytesIO
        import os
        from django.conf import settings
        from decimal import Decimal
    except ImportError:
        return HttpResponseRedirect(reverse('job:job_change_orders', args=[job_id]))
    
    try:
        # Get all change orders for this job
        change_orders = job.change_orders.all().select_related('product_code', 'created_by').order_by('-order_date', '-created_at')
        
        # Calculate total (only include change orders with amounts)
        total_change_amount = sum(co.amount for co in change_orders if co.amount is not None) if change_orders else Decimal('0.00')
        
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document with A4 page size and margins
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
        
        # Header and Footer drawing functions (reuse from sales invoice)
        def draw_header_footer(canvas, doc):
            """Draw header and footer on each page"""
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
                
                from datetime import datetime
                current_date = datetime.now().strftime("%m/%d/%Y")
                canvas.drawRightString(page_width - 20*mm, footer_y, f"Date: {current_date}")
                
                canvas.restoreState()
            except Exception:
                pass
        
        # Build story
        story = []
        
        # Title with gray background (same as sales invoice)
        title_style = ParagraphStyle(
            'Title',
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
        story.append(Paragraph("Change Orders", title_style))
        story.append(Spacer(1, 10*mm))
        
        # Customer and Job Info
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        customer_info = []
        if job.customer:
            customer_info.append(f"<b>Customer:</b> {job.customer.first_name} {job.customer.last_name}")
            if job.customer.address:
                customer_info.append(f"<b>Address:</b> {job.customer.address}")
            if job.customer.city and job.customer.state:
                city_state = f"{job.customer.city}, {job.customer.state}"
                if job.customer.zip:
                    city_state += f" {job.customer.zip}"
                customer_info.append(city_state)
        else:
            if job.address:
                customer_info.append(f"<b>Job Address:</b> {job.address}")
            if job.city and job.state:
                city_state = f"{job.city}, {job.state}"
                if job.zip:
                    city_state += f" {job.zip}"
                customer_info.append(city_state)
        
        customer_info.append(f"<b>Job Code:</b> {job.job_code}")
        
        for info in customer_info:
            story.append(Paragraph(info, normal_style))
        
        story.append(Spacer(1, 10*mm))
        
        # Change Orders Table
        # Create styles for consistent formatting
        header_left_style = ParagraphStyle(
            'HeaderLeft',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        header_right_style = ParagraphStyle(
            'HeaderRight',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        )
        
        cell_style = ParagraphStyle(
            'Cell',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT
        )
        
        amount_style = ParagraphStyle(
            'Amount',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )
        
        tax_style = ParagraphStyle(
            'Tax',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )
        
        total_style = ParagraphStyle(
            'Total',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        total_amount_style = ParagraphStyle(
            'TotalAmount',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_RIGHT
        )
        
        # Header row with Paragraph objects
        table_data = [[
            Paragraph('Date', header_left_style),
            Paragraph('Product Code', header_left_style),
            Paragraph('Amount', header_right_style),
            Paragraph('Tax', header_right_style),
            Paragraph('Description', header_left_style)
        ]]
        
        for change_order in change_orders:
            order_date = change_order.order_date.strftime("%b %d, %Y") if change_order.order_date else '-'
            product_code = change_order.product_code.code if change_order.product_code else '-'
            
            # Format amount
            if change_order.amount is not None:
                amount_str = f"${change_order.amount:+,.2f}"
            else:
                amount_str = '-'
            
            # Format tax
            tax_str = change_order.get_tax_display() if change_order.tax else '-'
            
            # Description (truncate if too long)
            description = change_order.description[:50] + '...' if len(change_order.description) > 50 else change_order.description
            
            table_data.append([
                Paragraph(order_date, cell_style),
                Paragraph(product_code, cell_style),
                Paragraph(amount_str, amount_style),
                Paragraph(tax_str, tax_style),
                Paragraph(description, cell_style)
            ])
        
        # Add total row (only if there are change orders with amounts)
        if any(co.amount is not None for co in change_orders):
            total_amount_str = f"${float(total_change_amount):+,.2f}"
            table_data.append([
                Paragraph('TOTAL', total_style),
                Paragraph('', cell_style),
                Paragraph(total_amount_str, total_amount_style),
                Paragraph('', cell_style),
                Paragraph('', cell_style)
            ])
        
        # Create table with adjusted column widths
        change_orders_table = Table(table_data, colWidths=[35*mm, 30*mm, 30*mm, 20*mm, 55*mm])
        change_orders_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),  # Date and Product Code left-aligned
            ('ALIGN', (2, 0), (3, -1), 'RIGHT'),  # Amount and Tax right-aligned
            ('ALIGN', (4, 0), (4, -1), 'LEFT'),  # Description left-aligned
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # Line below header
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),  # Line above total (if exists)
        ]))
        
        story.append(change_orders_table)
        
        # Build PDF
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        # Get PDF data
        pdf_data = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        # Create response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="change_orders_{job.job_code}.pdf"'
        
        return response
        
    except Exception as e:
        import traceback
        print(f"Change Orders PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('job:job_change_orders', args=[job_id]))


def lien_waiver_pdf_generate(request, job_id, payment_id):
    """Generate PDF for lien waiver with same header/footer as other PDFs"""
    from job.models import Payment
    job = get_object_or_404(Job, id=job_id)
    payment = get_object_or_404(Payment, id=payment_id, job=job)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfgen import canvas
        from io import BytesIO
        import os
        from django.conf import settings
        from datetime import datetime
    except ImportError:
        return HttpResponseRedirect(reverse('job:job_payments', args=[job_id]))
    
    try:
        # Create PDF buffer
        pdf_buffer = BytesIO()
        
        # Create document with A4 page size and margins
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
        
        # Header and Footer drawing functions (same as other PDFs)
        def draw_header_footer(canvas, doc):
            """Draw header and footer on each page"""
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
        
        # Build story
        story = []
        
        # Owner information at top left
        owner_style = ParagraphStyle(
            'Owner',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=3,
            alignment=TA_LEFT
        )
        
        # Get customer information
        customer = job.customer
        if customer:
            # Owner name
            owner_name = f"{customer.first_name} {customer.last_name}"
            if customer.first_name2 and customer.last_name2:
                owner_name += f" and {customer.first_name2} {customer.last_name2}"
            story.append(Paragraph(owner_name, owner_style))
            
            # Address
            if customer.address:
                story.append(Paragraph(customer.address, owner_style))
            
            # City, State, Zip
            city_state_zip = customer.city
            if customer.state:
                city_state_zip += f", {customer.state}"
            if customer.zip:
                city_state_zip += f" {customer.zip}"
            story.append(Paragraph(city_state_zip, owner_style))
        
        story.append(Spacer(1, 10*mm))
        
        # Title
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph("RECEIPT AND WAIVER OF LIEN", title_style))
        
        # Main paragraph
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=10,
            alignment=TA_LEFT
        )
        
        main_text = "Allen Kitchen & Bath hereby acknowledges receipt of payment as follows and waives partial lien rights on land and on buildings about to be erected, being erected, altered or repaired and to the appurtenances thereunto for:"
        story.append(Paragraph(main_text, normal_style))
        story.append(Spacer(1, 8*mm))
        
        # Details section
        detail_label_style = ParagraphStyle(
            'DetailLabel',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        )
        
        detail_value_style = ParagraphStyle(
            'DetailValue',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT
        )
        
        # Owner
        if customer:
            owner_full = f"{customer.first_name} {customer.last_name}"
            if customer.first_name2 and customer.last_name2:
                owner_full += f" and {customer.first_name2} {customer.last_name2}"
            story.append(Paragraph(f"<b>Owner:</b> {owner_full}", normal_style))
        
        # Address
        if customer and customer.address:
            story.append(Paragraph(f"<b>Address:</b> {customer.address}", normal_style))
        
        # City
        if customer and customer.city:
            story.append(Paragraph(f"<b>City:</b> {customer.city}", normal_style))
        
        # County
        county_name = ""
        if customer and customer.county:
            county_name = customer.county.name
        elif job.county:
            county_name = job.county.name
        if county_name:
            story.append(Paragraph(f"<b>County:</b> {county_name}", normal_style))
        
        # Payment Amount
        payment_amount = f"${payment.amount:,.2f}"
        story.append(Paragraph(f"<b>Payment Amount:</b> {payment_amount}", normal_style))
        
        # Payment for
        payment_for = payment.comment if payment.comment else "-"
        story.append(Paragraph(f"<b>Payment for:</b> {payment_for}", normal_style))
        
        # Project
        project_code = job.job_code if job.job_code else "-"
        story.append(Paragraph(f"<b>Project:</b> {project_code}", normal_style))
        
        story.append(Spacer(1, 8*mm))
        
        # Lien waiver statement
        lien_statement = "Lien waiver covers labor performed and materials furnished for the construction, alteration or repair of above said building."
        bold_style = ParagraphStyle(
            'Bold',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            spaceAfter=10,
            alignment=TA_LEFT
        )
        story.append(Paragraph(lien_statement, bold_style))
        story.append(Spacer(1, 8*mm))
        
        # Date Issued
        date_issued = payment.date.strftime("%m/%d/%Y") if payment.date else datetime.now().strftime("%m/%d/%Y")
        story.append(Paragraph(f"<b>Date Issued:</b> {date_issued}", normal_style))
        
        # Issued by
        story.append(Paragraph("<b>Issued by:</b> Allen Kitchen & Bath", normal_style))
        
        story.append(Spacer(1, 15*mm))
        
        # Signature lines
        signature_style = ParagraphStyle(
            'Signature',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=5,
            alignment=TA_LEFT
        )
        story.append(Paragraph("Signed by: ________________________", signature_style))
        story.append(Paragraph("Title: ________________________", signature_style))
        
        # Build PDF
        doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
        
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"lien_waiver_{job.job_code}_{payment_id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
        
    except Exception as e:
        import traceback
        print(f"Lien Waiver PDF Generation Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return HttpResponseRedirect(reverse('job:job_payments', args=[job_id]))
