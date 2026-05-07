import json
from django.shortcuts import redirect, get_object_or_404, render
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.http import HttpResponseNotFound, HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from celery.result import AsyncResult
from allenkit1.celery import app as celery_app

#rom crm.models import Customer
from sitework.models import *
from sitework.forms import SiteworkQuoteForm, QtyForm
#from .sitework import Sitework
from .tasks import subcreate


@login_required
def home_view(request):
    return TemplateResponse(request,'sitework/home.html', {})


@login_required
def thankyou_view(request):
    return TemplateResponse(request,'sitework/thank_you.html', {})


#
# Quotes
# show the values
@login_required
def quote_show(request,qte:int):
    quote = get_object_or_404(SiteworkQuote.objects.filter(id=qte))
    form = SiteworkQuoteForm(instance=quote)
    #form.is_bound = True
    print ("quote show ", form.is_bound  )
    if request.method == 'POST':
        print ("quote show POST")
        form = SiteworkQuoteForm(request.POST, instance=quote)
        if form.is_valid():
            form.save()
            print ("quote show save ", form.is_bound  )
            return redirect('/sitework/list')
    print ("keep going after show form")
    print (form.is_bound  )

    template_name = 'sitework/quote_show.html'
    context = {'form' : form}
    return TemplateResponse(request,template_name, context)


# show the sitework calc results as a report.
# show the sitework calc results as a report.
@login_required
def report_show(request,qte:int):
    quote = get_object_or_404(SiteworkQuote.objects.filter(id=qte))
    #
    SiteworkQuoteLine.objects.calc_price(qte)
    # my verbosity control
    my_verbose=1

    ##
    context = {}
    my_total = 0
    catstuff={}
    report_rows = []
    contingency = 0
    overhead = 0
    contingency_pct = 0.05 # from globals someday
    overhead_pct = 0.27 # from globals someday

    group_desc_by_group = {
        g.group: g.desc
        for g in SiteworkSubCatGroup.objects.all()
    }

    mycatcount = {}
    for xcat in SiteworkCat.objects.order_by('orderby'):
        catcount=0
        xsetupfee_key = SiteworkQuoteLine.objects.filter(cat=xcat, quote=qte, workdesc__icontains='setup fee').first()
        if xsetupfee_key and xsetupfee_key.calckey != 558: #not the drywall setup fees, please.
            xsetupfee_key.quantity = 0
            xsetupfee_key.save()
    
        for lin in SiteworkQuoteLine.objects.filter(cat=xcat, quote=qte):
            if lin.quantity > 0:
                catcount += 1
                #print("catcount:",lin.quantity, " on ", lin.workdesc)
        
        if xsetupfee_key and catcount > 0:
            xsetupfee_key.quantity = 1
            xsetupfee_key.save()
            print("xsetupfee_key updated:", xsetupfee_key, catcount, xsetupfee_key.quantity)

    # that for loop should have given us a 1 in setupfees for each category.

    
    for xcat in SiteworkCat.objects.order_by('orderby'):
        cat_total=0
        current_group = None
        cat_rows = []
        for lin in SiteworkQuoteLine.objects.filter(cat=xcat, quote=qte, quantity__gt=0).order_by('orderby'): #was group,orderby 5/6/26
            temp=0
            if lin.quantity > 0:
                if lin.editallowance == '1':
                    temp = (lin.allowance / lin.profit)
                else:
                    #calc total price for this item
                    temp = (lin.quantity * lin.unitamount) + lin.basecost
                
                #BILLCODE
                #override the price to match behavior of old DC, despite what the code says. Hmmm.
                if lin.quantity > 0 and lin.calckey == 558:
                    temp=100
                #END BILLCODE

                if current_group != lin.group:
                    groupdesc = group_desc_by_group.get(lin.group, "")
                    if groupdesc:
                        cat_rows.append({
                            "row_type": "group_header",
                            "text": groupdesc,
                        })
                    current_group = lin.group

                cat_total += temp
                if my_verbose>0: print (lin.workdesc,"(",lin.calckey, ")=", temp) 

                cat_rows.append({
                    "row_type": "line_item",
                    "qty": lin.quantity,
                    "unit": lin.quantitydesc,
                    "desc": lin.workdesc,
                    "price": f"${temp:8,.2f}",
                    "basecost": f"${lin.basecost:8,.2f}",
                    "unitamount": f"${lin.unitamount:8,.2f}",
                    "note": lin.itemcomment,
                })
        
        if cat_total > 0:
            report_rows.append({
                "row_type": "cat_header",
                "text": xcat.name,
            })
            report_rows.extend(cat_rows)
            report_rows.append({
                "row_type": "cat_subtotal",
                "text": f"${cat_total:8,.2f}",
            })

            catstuff[xcat.id] = {"cat": xcat.name, "price": f"${cat_total:8,.2f}"}

        my_total += cat_total
        if cat_total>0:
            if my_verbose>0: print("cat_total = ", f"${cat_total:8,.2f}","\n")

    # calc contingency and overhead
    if my_verbose>0: print ("xxold total: ",f"${my_total:8,.2f}")
    contingency = my_total * contingency_pct
    overhead = my_total * overhead_pct
    my_total = my_total + contingency + overhead
    if my_verbose>0: print ("contingency: ",f"${contingency:8,.2f}")
    if my_verbose>0: print ("xxxoverhead: ",f"${overhead:8,.2f}")
    if my_verbose>0: print ("xxnew total: ",f"${my_total:8,.2f}")

    context['total'] = f"${my_total:8,.2f}"
    context['desc'] = quote.quotedesc
    if quote.kbflag == "Both": context['room'] = "Kitchen and Bath"
    if quote.kbflag == "K": context['room'] = "Kitchen"
    if quote.kbflag == "B": context['room'] = "Bath"
    context['quotedby'] = quote.quotedby.first_name + " " + quote.quotedby.last_name
    context['customer'] = quote.customer.first_name + " " + quote.customer.last_name
    context['customer2'] = ""
    if quote.customer.first_name2 or quote.customer.last_name2:
        context['customer2'] = quote.customer.first_name2 + " " + quote.customer.last_name2
        
    context['cat_stuff'] = catstuff.copy()
    context['report_rows'] = report_rows
    context['qte'] = qte
    context['overhead'] = f"${overhead:8,.2f}"
    context['contingency'] = f"${contingency:8,.2f}"
   
    template_name = 'sitework/report_show.html'
    return TemplateResponse(request,template_name, context)


# show the sitework calc results as a simple report (no pricing in line items)
@login_required
def report_show_simple(request,qte:int):
    """Simple report showing quantity and descriptions only, pricing at summary end."""
    quote = get_object_or_404(SiteworkQuote.objects.filter(id=qte))
    #
    SiteworkQuoteLine.objects.calc_price(qte)
    # my verbosity control
    my_verbose=1

    ##
    context = {}
    my_total = 0
    catstuff={}
    report_rows = []
    contingency = 0
    overhead = 0
    contingency_pct = 0.05 # from globals someday
    overhead_pct = 0.27 # from globals someday

    group_desc_by_group = {
        g.group: g.desc
        for g in SiteworkSubCatGroup.objects.all()
    }

    for xcat in SiteworkCat.objects.order_by('orderby'):
        cat_total=0
        current_group = None
        cat_rows = []
        for lin in SiteworkQuoteLine.objects.filter(cat=xcat, quote=qte, quantity__gt=0).order_by('group', 'orderby'):
            temp=0
            if lin.quantity > 0:
                if lin.editallowance == '1':
                    temp = (lin.allowance / lin.profit)
                else:
                    #calc total price for this item
                    temp = (lin.quantity * lin.unitamount) + lin.basecost
                
                #BILLCODE
                #override the price to match behavior of old DC, despite what the code says. Hmmm.
                if lin.quantity > 0 and lin.calckey == 558:
                    temp=100
                #END BILLCODE

                if current_group != lin.group:
                    groupdesc = group_desc_by_group.get(lin.group, "")
                    if groupdesc:
                        cat_rows.append({
                            "row_type": "group_header",
                            "text": groupdesc,
                        })
                    current_group = lin.group

                cat_total += temp
                if my_verbose>0: print (lin.workdesc,"(",lin.calckey, ")=", temp) 

                cat_rows.append({
                    "row_type": "line_item",
                    "qty": lin.quantity,
                    "unit": lin.quantitydesc,
                    "desc": lin.workdesc,
                    "price": f"${temp:8,.2f}",
                    "basecost": f"${lin.basecost:8,.2f}",
                    "unitamount": f"${lin.unitamount:8,.2f}",
                    "note": lin.itemcomment,
                })
        
        if cat_total > 0:
            report_rows.append({
                "row_type": "cat_header",
                "text": xcat.name,
            })
            report_rows.extend(cat_rows)
            # No category subtotal in simple version
            report_rows.append({
                "row_type": "cat_subtotal",
                "text": f"${cat_total:8,.2f}",
            })

            catstuff[xcat.id] = {"cat": xcat.name, "price": f"${cat_total:8,.2f}"}

        my_total += cat_total
        if cat_total>0:
            if my_verbose>0: print("cat_total = ", f"${cat_total:8,.2f}","\n")

    # calc contingency and overhead
    if my_verbose>0: print ("xxold total: ",f"${my_total:8,.2f}")
    contingency = my_total * contingency_pct
    overhead = my_total * overhead_pct
    my_total = my_total + contingency + overhead
    if my_verbose>0: print ("contingency: ",f"${contingency:8,.2f}")
    if my_verbose>0: print ("xxxoverhead: ",f"${overhead:8,.2f}")
    if my_verbose>0: print ("xxnew total: ",f"${my_total:8,.2f}")

    context['total'] = f"${my_total:8,.2f}"
    context['desc'] = quote.quotedesc
    if quote.kbflag == "Both": context['room'] = "Kitchen and Bath"
    if quote.kbflag == "K": context['room'] = "Kitchen"
    if quote.kbflag == "B": context['room'] = "Bath"
    context['quotedby'] = quote.quotedby.first_name + " " + quote.quotedby.last_name
    context['customer'] = quote.customer.first_name + " " + quote.customer.last_name
    context['customer2'] = ""
    if quote.customer.first_name2 or quote.customer.last_name2:
        context['customer2'] = quote.customer.first_name2 + " " + quote.customer.last_name2
        
    context['cat_stuff'] = catstuff.copy()
    context['report_rows'] = report_rows
    context['qte'] = qte
    context['overhead'] = f"${overhead:8,.2f}"
    context['contingency'] = f"${contingency:8,.2f}"
   
    template_name = 'sitework/report_show_simple.html'
    return TemplateResponse(request,template_name, context)

@login_required
def quote_create(request):
    form = SiteworkQuoteForm()
    print ("quote create ", form.is_bound  )
    if request.method == 'POST':
        print ("quote create POST" , form.is_bound)
        form = SiteworkQuoteForm(request.POST)
        if form.is_valid():
            newquote=form.save()
            print ("quote create save ", form.is_bound  )
            # start the task to create subitems
            # first determine total count of items to be created
            count=0
            cats = SiteworkCat.objects.order_by('orderby')
            for c in cats:
                subcats = SiteworkSubCat.objects.filter(siteworkcat=c, status="A").order_by('orderby')
                for s in subcats:
                    count=count+1 
            print("BAFFLEGAB:", count)

            task = subcreate.delay(newquote.id, count)
            print(f"Task ID: {task.id}")
            # Store task_id in session for progress tracking
            request.session['last_task_id'] = task.id
            request.session['last_quote_id'] = newquote.id
            # Redirect to list with task info for progress bar
            return redirect(f"/sitework/list/?task_id={task.id}&quote_id={newquote.id}")
    print ("keep going after create form")
    template_name = 'sitework/quote_show.html'
    context = {'form' : form}

    return TemplateResponse(request,template_name, context)

# list of sitework quotes 
@login_required
def quote_list(request):
# Number of visits to this view, as counted in the session variable.
    num_visits = request.session.get('num_visits', 0)
    num_visits += 1
    request.session['num_visits'] = num_visits

    # Search functionality
    search_query = request.GET.get('q', '')
    if search_query:
        quotes = SiteworkQuote.objects.filter(
            Q(quotedesc__icontains=search_query) |
            Q(customer__last_name__icontains=search_query) |
            Q(customer__first_name__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(id__icontains=search_query)
        ).order_by('quotedesc')
    else:
        quotes = SiteworkQuote.objects.order_by('quotedesc')

    # Get task_id from query params (for progress bar after quote creation)
    task_id = request.GET.get('task_id')
    quote_id = request.GET.get('quote_id')

    template_name = 'sitework/quote_list.html'
    context = {
        'quotes': quotes,
        'num_visits': num_visits,
        'task_id': task_id,
        'new_quote_id': quote_id,
    }
    return TemplateResponse(request, template_name, context)

# delete sitework quote
@login_required
def quote_delete(request, quote_id):
    quote = get_object_or_404(SiteworkQuote, id=quote_id)
    
    if request.method == 'POST':
        # Delete the quote
        quote.delete()
        # Redirect to quote list
        return redirect('sitework:list_url')
    
    # If GET request, show confirmation page
    template_name = 'sitework/quote_confirm_delete.html'
    context = {'quote': quote}
    return TemplateResponse(request, template_name, context)

#
# subcat_form 
# shows the list of sitework items and allows editing the quantiy and comments for any item.
# need that all in one list to iterate through in one pass with desciptive date from
# the (static) siteworkCat and siteworkSubCat models, plus the quantity and comment info for the dynamic stuff.
# added logic for setupfees item in every subcat.
@login_required
def subcat_form(request,cat:int,qte:int):
    print("view:subcat_form", "cat=",cat,"qte=",qte)

    context = {}
    quote = get_object_or_404(SiteworkQuote.objects.filter(id=qte))
    print("view: subcat_form found the quote")
    print(request.path)
    #SESSION
    if 1 == 0:
        last_sitework  = request.session.get('last_sitework', 0)
        old_sitework = last_sitework
        last_sitework = quote.customer.last_name + " "+ quote.quotedesc
        request.session['last_sitework'] = last_sitework
        request.session['old_sitework'] = old_sitework


    group_desc_by_group = {
        g.group: g.desc
        for g in SiteworkSubCatGroup.objects.all()
    }
 

    second = list(
        SiteworkQuoteLine.objects.filter(cat=cat, quote=qte).order_by( 'orderby','group')
    )
    for sw in second:
        sw.groupdesc = group_desc_by_group.get(sw.group, "")
        #print("sw.group:", sw.group, "sw.groupdesc:", sw.groupdesc)
        # lookup the subcat by calckey
        sw.attached = SiteworkSubCatImage.objects.filter(calckey=sw.calckey).first()
        if sw.attached:
            sw.image_url = sw.attached.get_url()
            sw.image_thumb = sw.attached.get_url()
            if sw.image_url.endswith("pdf"):
                sw.image_thumb = "/media/sitework_images/PDF_file.png"
            print("BILLY sw.image_url:", sw.image_url," calckey:", sw.calckey)

    context = {
        "cat": cat,
        "qte": qte,
        # "last_sitework":last_sitework,
        # "old_sitework":old_sitework,
        "qdesc": quote.quotedesc,
        "qcust": quote.customer.last_name,
        "first":  SiteworkCat.objects.order_by('orderby'),
        "second": second,
    }

        
    # build list of quantities for all cats
    # also update the setupfee counter for each cat.
    ##
    mycatcount = {}
    for xcat in SiteworkCat.objects.order_by('orderby'):
        catcount=0
        xsetupfee_key = SiteworkQuoteLine.objects.filter(cat=xcat, quote=qte, workdesc__icontains='setup fee').first()
        if xsetupfee_key and xsetupfee_key.calckey != 558: #not the drywall setup fees, please.
            xsetupfee_key.quantity = 0
            xsetupfee_key.save()
    
        for lin in SiteworkQuoteLine.objects.filter(cat=xcat, quote=qte):
            if lin.quantity > 0:
                catcount += 1
                #print("catcount:",lin.quantity, " on ", lin.workdesc)
        
        mycatcount[xcat.id] = catcount
        if xsetupfee_key and catcount > 0:
            xsetupfee_key.quantity = 1
            xsetupfee_key.save()
            print("xsetupfee_key updated:", xsetupfee_key, catcount, xsetupfee_key.quantity)

    # add this dict to the context dictionary, make the deep copy.
    context['catcount'] = mycatcount.copy()
    ##

    template_name = 'sitework/subcat_form.html'
    return TemplateResponse(request,template_name,context)

# qty_form
# This is used to edit Qty in the row of the table.
def qty_form(request,qte:int,cat:int,subcat:int,quan:int,):
    print("view: qty_form, subcat",subcat)
    context_object_name = "data"
    myquan=0
    scat=subcat

    # Try to fetch the existing value, default to 0 if none.
    myline = SiteworkQuoteLine.objects.filter(id = scat, quote=qte).first()
    print(myline)
    if myline is None:
        myquan=0
    else:
        myquan = myline.quantity
    ##
    print("hi dad lineID=", scat,",quan ",myquan)

    myset = {
        "qte": qte,
        "quote": SiteworkQuote.objects.get(id=qte),
        "cat":  SiteworkCat.objects.get(id=cat),
        "subcat":  SiteworkQuoteLine.objects.get(id=scat),
        "quan": myquan,
        }
    if request.method == "POST":
        form = QtyForm(request.POST)
        print("dad got a POST")
        if form.is_valid():
            return HttpResponse(
                status=204,
                headers={
                    'HX-Trigger': json.dumps({
                        "showMessage": f"Sitework Updated."
                    })
                }
            )
    else:
        print("Dad got NO POST")
        form = QtyForm()
        print("returning the form with stuff")
        return render(request,'sitework/qty_form.html', {
            'data': myset,
        })
    
    print("HELP I have fallen")
    #context = {'data' : myset}
    #template_name = 'sitework/qty_form.html'
    #return TemplateResponse(request,template_name, context)


# qty_popup
# This is used to edit Qty in the row of the table.
def qty_popup(request,qte:int,cat:int,subcat:int,quan:int,):
    print("view: qty_popup, subcat",subcat)
    context_object_name = "data"
    myquan=0
    scat=subcat

    # Try to fetch the existing value, default to 0 if none.
    myline = SiteworkQuoteLine.objects.filter(id = scat, quote=qte).first()
    print(myline)
    if myline is None:
        myquan=0
    else:
        myquan = myline.quantity
    ##
    print("hi mom lineID=", scat,",quan ",myquan)

    myset = {
        "qte": qte,
        "quote": SiteworkQuote.objects.get(id=qte),
        "cat":  SiteworkCat.objects.get(id=cat),
        "subcat":  SiteworkQuoteLine.objects.get(id=scat),
        "quan": myquan,
        }

    context = {'data' : myset}
    template_name = 'sitework/qty_popup.html'
    return TemplateResponse(request,template_name, context)

# basecost_popup
# This is used to edit base cost in the row of the table.
def basecost_popup(request,qte:int,cat:int,subcat:int,basecost:str,):
    print("view: basecost_popup, subcat",subcat)
    context_object_name = "data"
    # Convert string to float
    try:
        basecost_float = float(basecost)
    except (ValueError, TypeError):
        basecost_float = 0.0
    
    myset = {
        "qte": qte,
        "cat": SiteworkCat.objects.get(id=cat),
        "subcat":  SiteworkQuoteLine.objects.get(id=subcat),
        "basecost": basecost_float,
        }
 
    context = {'data' : myset}
    template_name = 'sitework/basecost_popup.html'
    return TemplateResponse(request,template_name, context)

# unitamount_popup
# This is used to edit unit amount in the row of the table.
def unitamount_popup(request,qte:int,cat:int,subcat:int,unitamt:str,):
    print("view: unitamount_popup, subcat",subcat)
    context_object_name = "data"
    # Convert string to float
    try:
        unitamt_float = float(unitamt)
    except (ValueError, TypeError):
        unitamt_float = 0.0
    
    myset = {
        "qte": qte,
        "cat": SiteworkCat.objects.get(id=cat),
        "subcat":  SiteworkQuoteLine.objects.get(id=subcat),
        "unitamt": unitamt_float,
        }
 
    context = {'data' : myset}
    template_name = 'sitework/unitamount_popup.html'
    return TemplateResponse(request,template_name, context)

# qty_post
# qty_popup form will POST to this view.
def qty_post(request):
    context = {}
    x=0
    s=0
    q=0
    c=0
    print ("debug: QTY POST= ", request.method)
    if request.method == "POST":
        for key, value in request.POST.items():
            print(f'Key: {key}  Value: {value}')
            if key == 'qtyInput':
                x = int(value)
            if key == 'quoteid':
                q=value
            if key == 'subcat':
                s = value
            if key == 'cat':
                c = value

        context = {"x":x, "s":s, "q": q,"c": c,}

        # Store to the Database: qty, subid, quoteid,
        print("update_qty x,s,q",x,s,q)
        ql= SiteworkQuoteLine.objects.update_qty(x,s,q)
        # print("ql=",ql)
        return TemplateResponse(request,'sitework/qty_popup_results.html', context)

# basecost_post
# basecost_popup form will POST to this view.
def basecost_post(request):
    context = {}
    x=0.0
    s=0
    q=0
    c=0
    print ("debug: BASECOST POST= ", request.method)
    if request.method == "POST":
        for key, value in request.POST.items():
            print(f'Key: {key}  Value: {value}')
            if key == 'basecostInput':
                x = float(value)
            if key == 'quoteid':
                q=value
            if key == 'subcat':
                s = value
            if key == 'cat':
                c = value

        context = {"x":x, "s":s, "q": q,"c": c,}

        # Store to the Database: basecost, subid, quoteid,
        print("update_basecost x,s,q",x,s,q)
        try:
            sitework_line = SiteworkQuoteLine.objects.get(id=s)
            if sitework_line.quote_id != int(q):
                print("WARNING: Quote mismatch on update_basecost; line belongs to different quote")
            else:
                sitework_line.basecost = x
                sitework_line.save()
                print("Base cost updated successfully")
        except SiteworkQuoteLine.DoesNotExist:
            print("ERROR: SiteworkQuoteLine not found")
        except Exception as e:
            print(f"ERROR updating base cost: {e}")

        return TemplateResponse(request,'sitework/basecost_popup_results.html', context)

# unitamount_post
# unitamount_popup form will POST to this view.
def unitamount_post(request):
    context = {}
    x=0.0
    s=0
    q=0
    c=0
    print ("debug: UNITAMOUNT POST= ", request.method)
    if request.method == "POST":
        for key, value in request.POST.items():
            print(f'Key: {key}  Value: {value}')
            if key == 'unitamountInput':
                x = float(value)
            if key == 'quoteid':
                q=value
            if key == 'subcat':
                s = value
            if key == 'cat':
                c = value

        context = {"x":x, "s":s, "q": q,"c": c,}

        # Store to the Database: unitamount, subid, quoteid,
        print("update_unitamount x,s,q",x,s,q)
        try:
            sitework_line = SiteworkQuoteLine.objects.get(id=s)
            if sitework_line.quote_id != int(q):
                print("WARNING: Quote mismatch on update_unitamount; line belongs to different quote")
            else:
                sitework_line.unitamount = x
                sitework_line.save()
                print("Unit amount updated successfully")
        except SiteworkQuoteLine.DoesNotExist:
            print("ERROR: SiteworkQuoteLine not found")
        except Exception as e:
            print(f"ERROR updating unit amount: {e}")

        return TemplateResponse(request,'sitework/unitamount_popup_results.html', context)

def xcomment_popup(request,qte:int,subcat:int,comment:str,):
    myset = {
        "qte": 11,
        "subcat":  1326,
        "cat": 2 ,
        "comment": 'goonga la goonga',
        }
 
    context = {'data' : myset}

    template_name = 'sitework/mcomment_popup.html'
    return TemplateResponse(request,template_name, context)

# MODAL This is used to edit Comments in the row of the table.
# it will POST to comment_post.
#@ensure_csrf_cookie
def comment_popup(request, qte:int, subcat:int, comment:str,):
    #context_object_name = "data"
    mycomm=""
    print ("comment_popup: qte,subcat=",qte,subcat)
    # Try to fetch the existing comment, default to empty if none.
    # linecomm = SiteworkQuoteLineComment.objects.filter(subcat = subcat, quote=qte).first()
    linecomm = SiteworkQuoteLine.objects.filter(id = subcat, quote=qte).first()
    if linecomm is None:
        mycomm = ""
    else:
        mycomm = linecomm.itemcomment
    print ("old comment: ", mycomm)
    print ("qte,subcat=",qte,subcat)

    myset = {
        "qte": qte,
        "subcat":  SiteworkQuoteLine.objects.get(id=subcat),
        "cat": SiteworkQuoteLine.objects.get(id=subcat).cat ,
        "comment": mycomm,
        }
 
    context = {'data' : myset}
    print("context is ", context)

    template_name = 'sitework/mcomment_popup.html'
    ##return TemplateResponse(request,template_name, context)
    return render(request,template_name,context)


def xcomment_post(request):
    myset = {
        "qte": 11,
        "subcat": 1314,
        "x": 'dumb bill stuff',
    }
    context = {'data' : myset}   
    return TemplateResponse(request, 'sitework/comment_results.html', context)


# comment_post  
# after editing the comment.
#@ensure_csrf_cookie
def comment_post(request):
    #context_object_name = "data"
    context = {}
    x=''
    s=0
    q=0
    if request.method == "POST":
        print("comment_post:")
        for key, value in request.POST.items():
            print(f'Key: {key}   Value: {value}')
            if key == 'quoteid':
                q=value
                #print("quoteid ",q)
            if key == 'subcat':
                s = value
                #print("subcat ",s)
            if key == 'comment':
                x = value

    #print("mycomment:",x)
    #context = {"x":  x, }
    # new - fix variable names to match template expectations
    myset = {
        "q": q,
        "s": s,
        "x": x,
    }
    context = {'data' : myset}   
    # end new 
    ##context = {"x": x, }

    # Store to the Database: 
    try:
        sitework_line = SiteworkQuoteLine.objects.get(id=s)
        if sitework_line.quote_id != int(q):
            print("WARNING: Quote mismatch on update_comment; line belongs to different quote")
        else:
            sitework_line.itemcomment = x
            sitework_line.save()
            print("Comment updated successfully")
            # Add category to context for refresh
            myset["cat"] = sitework_line.cat.id
    except SiteworkQuoteLine.DoesNotExist:
        print("ERROR: SiteworkQuoteLine not found")
    except Exception as e:
        print(f"ERROR updating comment: {e}")

    return render(request,'sitework/comment_results.html',context)


@login_required
def task_status(request, task_id):
    """Return the status of a Celery task as JSON."""
    #print(f"DEBUG: task_status called for task_id={task_id}")
    #print(f"DEBUG: celery_app.backend={celery_app.backend}")
    try:
        result = celery_app.AsyncResult(task_id)
        # Safely get result info
        try:
            info = result.info
        except Exception as e:
            info = f"Error getting info: {e}"
        #print(f"DEBUG: result.state={result.state}, result.info={info}")
        response = {
            'state': result.state,
            'current': 0,
            'total': 0,
            'percent': 0,
            'status': result.state,
        }
        if result.state == 'PENDING':
            response['status'] = 'Pending...'
        elif result.state == 'PROGRESS':
            try:
                meta = result.info or {}
            except Exception:
                meta = {}
            response['current'] = meta.get('current', 0)
            response['total'] = meta.get('total', 0)
            response['percent'] = meta.get('percent', 0)
            response['status'] = f"Processing {meta.get('current', 0)} of {meta.get('total', 0)} items..."
        elif result.state == 'SUCCESS':
            try:
                task_result = result.result or {}
            except Exception:
                task_result = {}
            if isinstance(task_result, dict):
                response['current'] = task_result.get('current', 0)
                response['total'] = task_result.get('total', 0)
            response['percent'] = 100
            response['status'] = 'Completed!'
        elif result.state == 'FAILURE':
            response['status'] = 'Failed'
        else:
            response['status'] = result.state
        return JsonResponse(response)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'state': 'ERROR',
            'status': f'Error: {str(e)}'
        }, status=500)
